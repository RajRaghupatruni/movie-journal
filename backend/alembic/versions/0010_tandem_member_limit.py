"""Add an RLS-safe member count for transactional invitation acceptance."""

# Long SQL/grant statements are intentionally kept as SQL blocks.
# ruff: noqa: E501

from __future__ import annotations

import os
import re

from alembic import op

revision = "0010_tandem_member_limit"
down_revision = "0009_private_memory_media"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Invitees are intentionally allowed to see only the rows needed to
    # complete an invitation. A definer-owned count keeps capacity enforcement
    # correct without weakening the tandem_members SELECT policy.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.tandem_member_count(target_tandem_id uuid)
        RETURNS integer
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public, app AS $$
            SELECT count(*)::integer
            FROM public.tandem_members m
            WHERE m.tandem_id = target_tandem_id
        $$;
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
                EXECUTE format('GRANT EXECUTE ON FUNCTION app.tandem_member_count(uuid) TO %I', '{runtime_role}');
            ELSE
                EXECUTE format('GRANT EXECUTE ON FUNCTION app.tandem_member_count(uuid) TO %I', current_user);
            END IF;
        END
        $grant$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app.tandem_member_count(uuid)")
