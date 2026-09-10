"""Add timezone/preferences and the transactional anniversary email outbox."""

# Long policy and grant statements are intentionally SQL blocks.
# ruff: noqa: E501

from __future__ import annotations

import os
import re

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0011_nostalgia_notifications"
down_revision = "0010_tandem_member_limit"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)


def _role() -> str:
    value = os.getenv("DATABASE_RUNTIME_ROLE", "tandem_app")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise RuntimeError("DATABASE_RUNTIME_ROLE must be a simple PostgreSQL role name")
    return value


def upgrade() -> None:
    op.create_table(
        "user_notification_preferences",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("timezone", sa.String(64), server_default="UTC", nullable=False),
        sa.Column(
            "anniversary_notifications_enabled",
            sa.Boolean,
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "anniversary_email_enabled", sa.Boolean, server_default=sa.text("true"), nullable=False
        ),
        sa.Column("notification_hour", sa.Integer, server_default="9", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("notification_hour BETWEEN 0 AND 23", name="notification_hour_range"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_user_notification_preferences"),
        sa.UniqueConstraint("user_id", name="uq_user_notification_preferences_user"),
    )
    op.create_table(
        "notification_outbox",
        sa.Column("id", UUID, nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("tandem_id", UUID, nullable=False),
        sa.Column("memory_id", UUID, nullable=False),
        sa.Column("anniversary_year", sa.Integer, nullable=False),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("payload", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("idempotency_key", sa.String(300), nullable=False),
        sa.Column("status", sa.String(16), server_default="PENDING", nullable=False),
        sa.Column("attempts", sa.Integer, server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(2000), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SENT', 'FAILED', 'CANCELLED')",
            name="notification_outbox_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="notification_outbox_attempts_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tandem_id"], ["tandems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_notification_outbox"),
        sa.UniqueConstraint("idempotency_key", name="uq_notification_outbox_idempotency"),
        sa.UniqueConstraint(
            "tandem_id",
            "user_id",
            "memory_id",
            "anniversary_year",
            "channel",
            name="uq_notification_outbox_anniversary_delivery",
        ),
    )
    op.create_index(
        "ix_notification_outbox_pending",
        "notification_outbox",
        ["status", "next_attempt_at", "created_at"],
    )
    op.create_index(
        "ix_notification_outbox_recipient_anniversary",
        "notification_outbox",
        ["user_id", "anniversary_year", "channel"],
    )
    op.execute(
        """
        CREATE TRIGGER user_notification_preferences_set_updated_at
            BEFORE UPDATE ON user_notification_preferences
            FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

        ALTER TABLE user_notification_preferences ENABLE ROW LEVEL SECURITY;
        ALTER TABLE user_notification_preferences FORCE ROW LEVEL SECURITY;
        CREATE POLICY user_notification_preferences_select ON user_notification_preferences
            FOR SELECT USING (user_id = app.current_user_id());
        CREATE POLICY user_notification_preferences_insert ON user_notification_preferences
            FOR INSERT WITH CHECK (user_id = app.current_user_id());
        CREATE POLICY user_notification_preferences_update ON user_notification_preferences
            FOR UPDATE USING (user_id = app.current_user_id())
            WITH CHECK (user_id = app.current_user_id());
        CREATE POLICY user_notification_preferences_worker ON user_notification_preferences
            USING (current_setting('app.worker_mode', true) = 'true')
            WITH CHECK (current_setting('app.worker_mode', true) = 'true');

        CREATE POLICY tandem_members_worker ON tandem_members
            FOR SELECT USING (current_setting('app.worker_mode', true) = 'true');
        CREATE POLICY memories_worker ON memories
            FOR SELECT USING (current_setting('app.worker_mode', true) = 'true');

        ALTER TABLE notification_outbox ENABLE ROW LEVEL SECURITY;
        ALTER TABLE notification_outbox FORCE ROW LEVEL SECURITY;
        CREATE POLICY notification_outbox_worker ON notification_outbox
            USING (current_setting('app.worker_mode', true) = 'true')
            WITH CHECK (current_setting('app.worker_mode', true) = 'true');
        """
    )
    role = _role()
    op.execute(
        f"""
        DO $grant$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE format(
                    'GRANT SELECT, INSERT, UPDATE ON user_notification_preferences TO %I',
                    '{role}'
                );
            ELSE
                EXECUTE 'GRANT SELECT, INSERT, UPDATE ON user_notification_preferences TO ' || quote_ident(current_user);
            END IF;
        END
        $grant$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE notification_outbox DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_notification_preferences DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_notification_outbox_recipient_anniversary", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_pending", table_name="notification_outbox")
    op.drop_table("notification_outbox")
    op.drop_table("user_notification_preferences")
