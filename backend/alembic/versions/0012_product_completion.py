"""Account lifecycle, enforced membership invariants, notifications and media cleanup."""

# Long policy and grant statements are intentionally SQL blocks.
# ruff: noqa: E501

import os
import re
from pathlib import Path

import sqlalchemy as sa

from alembic import op
from app.models import Notification, StorageCleanupFailure

revision = "0012_product_completion"
down_revision = "0011_nostalgia_notifications"
branch_labels = None
depends_on = None

ACTORS = (
    ("tandems", "created_by"),
    ("invitations", "invited_by"),
    ("invitations", "accepted_by"),
    ("memories", "created_by"),
    ("activity_events", "actor_user_id"),
    ("memory_media", "created_by"),
)


def _role() -> str:
    value = os.getenv("DATABASE_RUNTIME_ROLE", "tandem_app")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise RuntimeError("DATABASE_RUNTIME_ROLE must be a simple PostgreSQL role name")
    return value


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.add_column(
        "users", sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False)
    )
    op.add_column("users", sa.Column("deactivated_at", sa.DateTime(timezone=True)))
    # Permanent deletion removes the row; this nullable field is reserved for historic imports.
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.alter_column("users", "google_subject", nullable=True)
    op.alter_column("users", "email", nullable=True)
    op.add_column(
        "auth_sessions",
        sa.Column("reactivation_only", sa.Boolean(), server_default="false", nullable=False),
    )
    for table, column in ACTORS:
        op.drop_constraint(f"fk_{table}_{column}_users", table, type_="foreignkey")
        op.alter_column(table, column, nullable=True)
        op.create_foreign_key(
            f"fk_{table}_{column}_users", table, "users", [column], ["id"], ondelete="SET NULL"
        )
    op.drop_constraint(
        "fk_memory_participants_membership", "memory_participants", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_memory_participants_membership",
        "memory_participants",
        "tandem_members",
        ["tandem_id", "user_id"],
        ["tandem_id", "user_id"],
        ondelete="CASCADE",
    )
    Notification.__table__.create(op.get_bind())
    StorageCleanupFailure.__table__.create(op.get_bind())
    op.execute(Path(__file__).with_name("0012_product_up.sql").read_text())
    role = _role()
    op.execute(
        f"""
        DO $grant$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE format(
                    'GRANT SELECT, UPDATE, DELETE ON notifications TO %I',
                    '{role}'
                );
                EXECUTE format(
                    'GRANT SELECT, INSERT, UPDATE, DELETE ON storage_cleanup_failures TO %I',
                    '{role}'
                );
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION app.insert_notification(uuid,text,uuid,uuid,uuid,uuid,jsonb,text) TO %I',
                    '{role}'
                );
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION app.cancel_user_tandem_notifications(uuid,uuid) TO %I',
                    '{role}'
                );
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION app.clear_user_delivery_state(uuid) TO %I',
                    '{role}'
                );
            ELSE
                EXECUTE 'GRANT SELECT, UPDATE, DELETE ON notifications TO ' || quote_ident(current_user);
                EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON storage_cleanup_failures TO ' || quote_ident(current_user);
            END IF;
        END
        $grant$;
        """
    )


def downgrade():
    op.execute(Path(__file__).with_name("0012_product_down.sql").read_text())
    StorageCleanupFailure.__table__.drop(op.get_bind())
    Notification.__table__.drop(op.get_bind())
    op.drop_constraint(
        "fk_memory_participants_membership", "memory_participants", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_memory_participants_membership",
        "memory_participants",
        "tandem_members",
        ["tandem_id", "user_id"],
        ["tandem_id", "user_id"],
        ondelete="RESTRICT",
    )
    # Downgrade cannot recreate erased identities: require an empty disposable DB or restore backup.
    for table, column in ACTORS:
        op.drop_constraint(f"fk_{table}_{column}_users", table, type_="foreignkey")
        if column != "accepted_by":
            op.alter_column(table, column, nullable=False)
        op.create_foreign_key(
            f"fk_{table}_{column}_users", table, "users", [column], ["id"], ondelete="RESTRICT"
        )
    op.drop_column("auth_sessions", "reactivation_only")
    op.alter_column("users", "google_subject", nullable=False)
    op.alter_column("users", "email", nullable=False)
    for column in ("deleted_at", "deactivated_at", "is_active"):
        op.drop_column("users", column)
