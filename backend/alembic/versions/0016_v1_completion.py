"""Tandem V1 retention, personal reflections, and member preferences.

This migration deliberately preserves the existing shared-memory columns.  The
legacy rating/notes fields remain readable for old clients; new writes use the
personal reflection table and the API exposes both during the transition.
"""
# ruff: noqa: E501

from __future__ import annotations

import os
import re

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0016_v1_completion"
down_revision = "0015_rls_helper_role"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)


def _role() -> str:
    value = os.getenv("DATABASE_RUNTIME_ROLE", "tandem_app")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise RuntimeError("DATABASE_RUNTIME_ROLE must be a simple PostgreSQL role name")
    return value


def upgrade() -> None:
    op.add_column("memories", sa.Column("end_date", sa.Date(), nullable=True))
    op.add_column("memories", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "memories", sa.Column("deletion_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("memory_participants", sa.Column("participant_display_name", sa.String(200)))
    op.add_column("oauth_states", sa.Column("return_path", sa.String(512), nullable=True))
    op.execute(
        """
        UPDATE memories
           SET end_date = NULLIF(metadata ->> 'end_date', '')::date
         WHERE category = 'trip' AND metadata ->> 'end_date' IS NOT NULL;
        UPDATE memory_participants mp
           SET participant_display_name = u.display_name
          FROM users u
         WHERE u.id = mp.user_id AND mp.participant_display_name IS NULL;
        DROP INDEX IF EXISTS uq_memories_movie_provider_date;
        ALTER TABLE memory_participants DROP CONSTRAINT IF EXISTS fk_memory_participants_membership;
        """
    )
    op.create_table(
        "memory_reflections",
        sa.Column("id", UUID, nullable=False),
        sa.Column("memory_id", UUID, nullable=False),
        sa.Column("tandem_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=True),
        sa.Column("rating", sa.Integer, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("reaction", sa.String(24), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "rating IS NULL OR rating BETWEEN 1 AND 10", name="reflection_rating_range"
        ),
        sa.CheckConstraint(
            "reaction IS NULL OR reaction IN ('loved', 'nostalgic', 'funny', 'favorite')",
            name="reflection_reaction_values",
        ),
        sa.ForeignKeyConstraint(
            ["memory_id", "tandem_id"], ["memories.id", "memories.tandem_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("memory_id", "user_id", name="uq_memory_reflections_memory_user"),
    )
    op.create_index(
        "ix_memory_reflections_memory", "memory_reflections", ["memory_id", "created_at"]
    )
    op.execute(
        """
        INSERT INTO memory_reflections (id, memory_id, tandem_id, user_id, rating, note)
        SELECT gen_random_uuid(), id, tandem_id, created_by, rating, notes
          FROM memories
         WHERE created_by IS NOT NULL AND (rating IS NOT NULL OR notes IS NOT NULL)
        ON CONFLICT (memory_id, user_id) DO NOTHING;
        """
    )
    op.create_table(
        "tandem_user_preferences",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tandem_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column(
            "resurfacing_enabled", sa.Boolean, server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "routine_notifications_enabled",
            sa.Boolean,
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tandem_id"], ["tandems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tandem_id", "user_id", name="uq_tandem_user_preferences"),
    )
    op.execute(
        """
        ALTER TABLE memory_reflections ENABLE ROW LEVEL SECURITY;
        ALTER TABLE memory_reflections FORCE ROW LEVEL SECURITY;
        CREATE POLICY memory_reflections_select ON memory_reflections FOR SELECT
            USING (app.is_tandem_member(tandem_id, app.current_user_id()));
        CREATE POLICY memory_reflections_insert ON memory_reflections FOR INSERT
            WITH CHECK (
                app.is_tandem_member(tandem_id, app.current_user_id())
                AND user_id = app.current_user_id()
            );
        CREATE POLICY memory_reflections_update ON memory_reflections FOR UPDATE
            USING (user_id = app.current_user_id())
            WITH CHECK (user_id = app.current_user_id());
        CREATE POLICY memory_reflections_delete ON memory_reflections FOR DELETE
            USING (user_id = app.current_user_id() OR app.is_tandem_owner(tandem_id, app.current_user_id()));

        ALTER TABLE tandem_user_preferences ENABLE ROW LEVEL SECURITY;
        ALTER TABLE tandem_user_preferences FORCE ROW LEVEL SECURITY;
        CREATE POLICY tandem_user_preferences_select ON tandem_user_preferences FOR SELECT
            USING (user_id = app.current_user_id() AND app.is_tandem_member(tandem_id, app.current_user_id()));
        CREATE POLICY tandem_user_preferences_insert ON tandem_user_preferences FOR INSERT
            WITH CHECK (user_id = app.current_user_id() AND app.is_tandem_member(tandem_id, app.current_user_id()));
        CREATE POLICY tandem_user_preferences_update ON tandem_user_preferences FOR UPDATE
            USING (user_id = app.current_user_id()) WITH CHECK (user_id = app.current_user_id());

        CREATE TRIGGER memory_reflections_set_updated_at BEFORE UPDATE ON memory_reflections
            FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();
        CREATE TRIGGER tandem_user_preferences_set_updated_at BEFORE UPDATE ON tandem_user_preferences
            FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();
        """
    )
    role = _role()
    op.execute(
        f"""
        GRANT SELECT, INSERT, UPDATE, DELETE ON memory_reflections, tandem_user_preferences TO {role};
        GRANT SELECT, UPDATE ON memories TO {role};
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS tandem_user_preferences_set_updated_at ON tandem_user_preferences"
    )
    op.execute("DROP TRIGGER IF EXISTS memory_reflections_set_updated_at ON memory_reflections")
    op.execute("DROP TABLE tandem_user_preferences")
    op.drop_index("ix_memory_reflections_memory", table_name="memory_reflections")
    op.drop_table("memory_reflections")
    op.drop_column("memory_participants", "participant_display_name")
    op.drop_column("oauth_states", "return_path")
    op.drop_column("memories", "deletion_expires_at")
    op.drop_column("memories", "deleted_at")
    op.drop_column("memories", "end_date")
    op.create_foreign_key(
        "fk_memory_participants_membership",
        "memory_participants",
        "tandem_members",
        ["tandem_id", "user_id"],
        ["tandem_id", "user_id"],
        ondelete="CASCADE",
    )
