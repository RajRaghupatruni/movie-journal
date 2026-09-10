"""Add private processed media attached to memories."""

from __future__ import annotations

import os
import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_private_memory_media"
down_revision = "0008_memory_domain"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "memory_media",
        sa.Column("id", UUID, nullable=False),
        sa.Column("memory_id", UUID, nullable=False),
        sa.Column("tandem_id", UUID, nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer, nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("created_by", UUID, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("display_order", sa.Integer, server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["memory_id", "tandem_id"], ["memories.id", "memories.tandem_id"], ondelete="CASCADE",
            name="fk_memory_media_memory_tandem",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_memory_media"),
        sa.UniqueConstraint("object_key", name="uq_memory_media_object_key"),
        sa.CheckConstraint("content_type IN ('image/jpeg', 'image/png', 'image/webp')", name="content_type"),
        sa.CheckConstraint("byte_size > 0", name="positive_byte_size"),
        sa.CheckConstraint("width > 0 AND height > 0", name="positive_dimensions"),
        sa.CheckConstraint("display_order >= 0", name="nonnegative_display_order"),
    )
    op.create_index("ix_memory_media_tandem_memory_order", "memory_media", ["tandem_id", "memory_id", "display_order"])
    op.create_index("ix_memory_media_tandem_created_at", "memory_media", ["tandem_id", "created_at"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_memories_movie_provider_date
        ON memories (tandem_id, ((metadata ->> 'provider_movie_id')), local_date)
        WHERE category = 'movie' AND metadata ->> 'provider_movie_id' IS NOT NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE memory_media ENABLE ROW LEVEL SECURITY;
        ALTER TABLE memory_media FORCE ROW LEVEL SECURITY;
        CREATE POLICY memory_media_select ON memory_media FOR SELECT
            USING (app.is_tandem_member(tandem_id, app.current_user_id()));
        CREATE POLICY memory_media_insert ON memory_media FOR INSERT
            WITH CHECK (
                app.is_tandem_member(tandem_id, app.current_user_id())
                AND created_by = app.current_user_id()
            );
        CREATE POLICY memory_media_update ON memory_media FOR UPDATE
            USING (app.is_tandem_member(tandem_id, app.current_user_id()))
            WITH CHECK (app.is_tandem_member(tandem_id, app.current_user_id()));
        CREATE POLICY memory_media_delete ON memory_media FOR DELETE
            USING (app.is_tandem_member(tandem_id, app.current_user_id()));
        """
    )
    runtime_role = os.getenv("DATABASE_RUNTIME_ROLE", "tandem_app")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", runtime_role):
        raise RuntimeError("DATABASE_RUNTIME_ROLE must be a simple PostgreSQL role name")
    op.execute(
        f"""
        DO $grant$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{runtime_role}') THEN
                EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON memory_media TO %I', '{runtime_role}');
            ELSE
                EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON memory_media TO %I', current_user);
            END IF;
        END $grant$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_memories_movie_provider_date")
    op.execute("ALTER TABLE memory_media DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_memory_media_tandem_created_at", table_name="memory_media")
    op.drop_index("ix_memory_media_tandem_memory_order", table_name="memory_media")
    op.drop_table("memory_media")
