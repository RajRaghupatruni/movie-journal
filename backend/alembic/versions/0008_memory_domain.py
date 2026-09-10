"""Add the Tandem memory domain, participant/tag joins, activity events and RLS."""

# Long SQL/grant statements are intentionally kept as SQL blocks.
# ruff: noqa: E501

from __future__ import annotations

import os
import re

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0008_memory_domain"
down_revision = "0007_pending_invite_uq"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tandem_id", UUID, nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("local_date", sa.Date, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("rating", sa.Integer, nullable=True),
        sa.Column("created_by", UUID, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("version", sa.Integer, server_default="1", nullable=False),
        sa.Column("nostalgia_eligible", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("schema_version", sa.Integer, server_default="1", nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR,
            sa.Computed(
                "to_tsvector('simple'::regconfig, title || ' ' || coalesce(notes, '') || ' ' || coalesce(metadata::text, ''))",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('movie', 'place', 'trip', 'activity', 'custom')",
            name="category",
        ),
        sa.CheckConstraint("char_length(btrim(title)) BETWEEN 1 AND 180", name="title_length"),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 10", name="rating_range"),
        sa.CheckConstraint("version >= 1", name="positive_version"),
        sa.ForeignKeyConstraint(["tandem_id"], ["tandems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_memories"),
        sa.UniqueConstraint("id", "tandem_id", name="uq_memories_id_tandem"),
    )
    op.create_index("ix_memories_tandem_local_date", "memories", ["tandem_id", "local_date", "id"])
    op.create_index("ix_memories_tandem_category", "memories", ["tandem_id", "category"])
    op.create_index("ix_memories_tandem_updated_at", "memories", ["tandem_id", "updated_at"])
    op.create_index(
        "ix_memories_search_vector", "memories", ["search_vector"], postgresql_using="gin"
    )

    op.create_table(
        "tags",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tandem_id", UUID, nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("normalized_name", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tandem_id"], ["tandems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_tags"),
        sa.UniqueConstraint("id", "tandem_id", name="uq_tags_id_tandem"),
        sa.UniqueConstraint("tandem_id", "normalized_name", name="uq_tags_tandem_normalized_name"),
    )
    op.create_index("ix_tags_tandem_name", "tags", ["tandem_id", "name"])

    op.create_table(
        "memory_participants",
        sa.Column("memory_id", UUID, nullable=False),
        sa.Column("tandem_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(
            ["memory_id", "tandem_id"],
            ["memories.id", "memories.tandem_id"],
            ondelete="CASCADE",
            name="fk_memory_participants_memory_tandem",
        ),
        sa.ForeignKeyConstraint(
            ["tandem_id", "user_id"],
            ["tandem_members.tandem_id", "tandem_members.user_id"],
            ondelete="RESTRICT",
            name="fk_memory_participants_membership",
        ),
        sa.PrimaryKeyConstraint("memory_id", "user_id", name="pk_memory_participants"),
    )
    op.create_index(
        "ix_memory_participants_tandem_user", "memory_participants", ["tandem_id", "user_id"]
    )

    op.create_table(
        "memory_tags",
        sa.Column("memory_id", UUID, nullable=False),
        sa.Column("tag_id", UUID, nullable=False),
        sa.Column("tandem_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(
            ["memory_id", "tandem_id"],
            ["memories.id", "memories.tandem_id"],
            ondelete="CASCADE",
            name="fk_memory_tags_memory_tandem",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id", "tandem_id"],
            ["tags.id", "tags.tandem_id"],
            ondelete="CASCADE",
            name="fk_memory_tags_tag_tandem",
        ),
        sa.PrimaryKeyConstraint("memory_id", "tag_id", name="pk_memory_tags"),
    )
    op.create_index("ix_memory_tags_tandem_tag", "memory_tags", ["tandem_id", "tag_id"])

    op.create_table(
        "activity_events",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tandem_id", UUID, nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", UUID, nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor_user_id", UUID, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("correlation_id", sa.String(36), nullable=True),
        sa.Column(
            "payload", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.CheckConstraint("octet_length(payload::text) <= 4096", name="payload_size"),
        sa.ForeignKeyConstraint(["tandem_id"], ["tandems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_activity_events"),
    )
    op.create_index(
        "ix_activity_events_tandem_created_at", "activity_events", ["tandem_id", "created_at", "id"]
    )
    op.create_index(
        "ix_activity_events_entity", "activity_events", ["entity_type", "entity_id", "created_at"]
    )

    op.execute(
        """
        CREATE TRIGGER memories_set_updated_at BEFORE UPDATE ON memories
            FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

        ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
        ALTER TABLE memories FORCE ROW LEVEL SECURITY;
        ALTER TABLE memory_participants ENABLE ROW LEVEL SECURITY;
        ALTER TABLE memory_participants FORCE ROW LEVEL SECURITY;
        ALTER TABLE tags ENABLE ROW LEVEL SECURITY;
        ALTER TABLE tags FORCE ROW LEVEL SECURITY;
        ALTER TABLE memory_tags ENABLE ROW LEVEL SECURITY;
        ALTER TABLE memory_tags FORCE ROW LEVEL SECURITY;
        ALTER TABLE activity_events ENABLE ROW LEVEL SECURITY;
        ALTER TABLE activity_events FORCE ROW LEVEL SECURITY;

        CREATE POLICY memories_select ON memories FOR SELECT
            USING (app.is_tandem_member(tandem_id, app.current_user_id()));
        CREATE POLICY memories_insert ON memories FOR INSERT
            WITH CHECK (
                app.is_tandem_member(tandem_id, app.current_user_id())
                AND created_by = app.current_user_id()
            );
        CREATE POLICY memories_update ON memories FOR UPDATE
            USING (app.is_tandem_member(tandem_id, app.current_user_id()))
            WITH CHECK (app.is_tandem_member(tandem_id, app.current_user_id()));
        CREATE POLICY memories_delete ON memories FOR DELETE
            USING (app.is_tandem_member(tandem_id, app.current_user_id()));

        CREATE POLICY memory_participants_select ON memory_participants FOR SELECT
            USING (app.is_tandem_member(tandem_id, app.current_user_id()));
        CREATE POLICY memory_participants_insert ON memory_participants FOR INSERT
            WITH CHECK (
                app.is_tandem_member(tandem_id, app.current_user_id())
                AND app.is_tandem_member(tandem_id, user_id)
            );
        CREATE POLICY memory_participants_delete ON memory_participants FOR DELETE
            USING (app.is_tandem_member(tandem_id, app.current_user_id()));

        CREATE POLICY tags_select ON tags FOR SELECT
            USING (app.is_tandem_member(tandem_id, app.current_user_id()));
        CREATE POLICY tags_insert ON tags FOR INSERT
            WITH CHECK (app.is_tandem_member(tandem_id, app.current_user_id()));

        CREATE POLICY memory_tags_select ON memory_tags FOR SELECT
            USING (app.is_tandem_member(tandem_id, app.current_user_id()));
        CREATE POLICY memory_tags_insert ON memory_tags FOR INSERT
            WITH CHECK (app.is_tandem_member(tandem_id, app.current_user_id()));
        CREATE POLICY memory_tags_delete ON memory_tags FOR DELETE
            USING (app.is_tandem_member(tandem_id, app.current_user_id()));

        CREATE POLICY activity_events_select ON activity_events FOR SELECT
            USING (app.is_tandem_member(tandem_id, app.current_user_id()));
        CREATE POLICY activity_events_insert ON activity_events FOR INSERT
            WITH CHECK (
                app.is_tandem_member(tandem_id, app.current_user_id())
                AND actor_user_id = app.current_user_id()
            );
        """
    )

    runtime_role = os.getenv("DATABASE_RUNTIME_ROLE", "tandem_app")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", runtime_role):
        raise RuntimeError("DATABASE_RUNTIME_ROLE must be a simple PostgreSQL role name")
    op.execute(
        f"""
        DO $grant$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{runtime_role}') THEN
                EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON memories, tags, memory_participants, memory_tags TO %I', '{runtime_role}');
                EXECUTE format('GRANT SELECT, INSERT ON activity_events TO %I', '{runtime_role}');
                EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO %I', '{runtime_role}');
            ELSE
                EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON memories, tags, memory_participants, memory_tags TO %I', current_user);
                EXECUTE format('GRANT SELECT, INSERT ON activity_events TO %I', current_user);
            END IF;
        END
        $grant$;
        """
    )


def downgrade() -> None:
    for table in ("activity_events", "memory_tags", "memory_participants", "tags", "memories"):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_activity_events_entity", table_name="activity_events")
    op.drop_index("ix_activity_events_tandem_created_at", table_name="activity_events")
    op.drop_table("activity_events")
    op.drop_index("ix_memory_tags_tandem_tag", table_name="memory_tags")
    op.drop_table("memory_tags")
    op.drop_index("ix_memory_participants_tandem_user", table_name="memory_participants")
    op.drop_table("memory_participants")
    op.drop_index("ix_tags_tandem_name", table_name="tags")
    op.drop_table("tags")
    op.drop_index("ix_memories_search_vector", table_name="memories")
    op.drop_index("ix_memories_tandem_updated_at", table_name="memories")
    op.drop_index("ix_memories_tandem_category", table_name="memories")
    op.drop_index("ix_memories_tandem_local_date", table_name="memories")
    op.drop_table("memories")
