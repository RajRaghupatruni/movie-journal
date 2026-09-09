"""Add users, server sessions, tandems, memberships, invitations and RLS."""

# Long SQL policy statements are intentionally kept as SQL blocks.
# ruff: noqa: E501

from __future__ import annotations

import os
import re

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_identity_tandems"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.execute("CREATE SCHEMA app")

    op.create_table(
        "users",
        sa.Column("id", UUID, nullable=False),
        sa.Column("google_subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("avatar_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("google_subject", name="uq_users_google_subject"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "tandems",
        sa.Column("id", UUID, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_by", UUID, nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_tandems_created_by_users", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tandems"),
    )
    op.create_table(
        "tandem_members",
        sa.Column("tandem_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("role IN ('OWNER', 'MEMBER')", name="ck_tandem_members_role"),
        sa.ForeignKeyConstraint(
            ["tandem_id"],
            ["tandems.id"],
            name="fk_tandem_members_tandem_id_tandems",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_tandem_members_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("tandem_id", "user_id", name="pk_tandem_members"),
        sa.UniqueConstraint("tandem_id", "user_id", name="uq_tandem_members_tandem_id"),
    )
    op.create_table(
        "invitations",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tandem_id", UUID, nullable=False),
        sa.Column("invited_email", sa.String(length=320), nullable=False),
        sa.Column("invited_by", UUID, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_by", UUID, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'REVOKED')",
            name="ck_invitations_status",
        ),
        sa.ForeignKeyConstraint(
            ["tandem_id"],
            ["tandems.id"],
            name="fk_invitations_tandem_id_tandems",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.id"],
            name="fk_invitations_invited_by_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["accepted_by"],
            ["users.id"],
            name="fk_invitations_accepted_by_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_invitations"),
        sa.UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
    )
    op.create_index(
        "ix_invitations_active_recipient",
        "invitations",
        ["tandem_id", "invited_email", "status"],
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_auth_sessions_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_table(
        "oauth_states",
        sa.Column("id", UUID, nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_oauth_states"),
        sa.UniqueConstraint("state_hash", name="uq_oauth_states_state_hash"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER users_set_updated_at BEFORE UPDATE ON users
            FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();
        CREATE TRIGGER tandems_set_updated_at BEFORE UPDATE ON tandems
            FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();
        """
    )

    # These functions are owned by the migration/owner role. They are deliberately
    # SECURITY DEFINER so policies can inspect membership without recursive RLS.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.current_user_id() RETURNS uuid
        LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid
        $$;
        CREATE OR REPLACE FUNCTION app.is_tandem_member(target_tandem_id uuid, target_user_id uuid)
        RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, app AS $$
            SELECT EXISTS (
                SELECT 1 FROM public.tandem_members m
                WHERE m.tandem_id = target_tandem_id AND m.user_id = target_user_id
            )
        $$;
        CREATE OR REPLACE FUNCTION app.is_tandem_owner(target_tandem_id uuid, target_user_id uuid)
        RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, app AS $$
            SELECT EXISTS (
                SELECT 1 FROM public.tandem_members m
                WHERE m.tandem_id = target_tandem_id AND m.user_id = target_user_id AND m.role = 'OWNER'
            )
        $$;
        CREATE OR REPLACE FUNCTION app.is_tandem_creator(target_tandem_id uuid, target_user_id uuid)
        RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, app AS $$
            SELECT EXISTS (
                SELECT 1 FROM public.tandems t
                WHERE t.id = target_tandem_id AND t.created_by = target_user_id
            )
        $$;
        CREATE OR REPLACE FUNCTION app.user_email_matches(target_user_id uuid, target_email text)
        RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, app AS $$
            SELECT EXISTS (
                SELECT 1 FROM public.users u
                WHERE u.id = target_user_id AND lower(u.email) = lower(target_email)
            )
        $$;
        CREATE OR REPLACE FUNCTION app.can_join_via_invitation(target_tandem_id uuid, target_user_id uuid)
        RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, app AS $$
            SELECT EXISTS (
                SELECT 1 FROM public.invitations i
                JOIN public.users u ON u.id = target_user_id
                WHERE i.tandem_id = target_tandem_id
                  AND i.status = 'PENDING'
                  AND i.expires_at > now()
                  AND lower(i.invited_email) = lower(u.email)
            )
        $$;
        CREATE OR REPLACE FUNCTION app.can_view_tandem(target_tandem_id uuid, target_user_id uuid)
        RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, app AS $$
            SELECT app.is_tandem_member(target_tandem_id, target_user_id)
                OR EXISTS (
                    SELECT 1 FROM public.invitations i
                    JOIN public.users u ON u.id = target_user_id
                    WHERE i.tandem_id = target_tandem_id
                      AND i.status = 'PENDING'
                      AND i.expires_at > now()
                      AND lower(i.invited_email) = lower(u.email)
                )
        $$;
        CREATE OR REPLACE FUNCTION app.can_leave_tandem(target_tandem_id uuid, target_user_id uuid)
        RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public, app AS $$
            SELECT EXISTS (
                SELECT 1 FROM public.tandem_members m
                WHERE m.tandem_id = target_tandem_id AND m.user_id = target_user_id
                  AND m.role <> 'OWNER'
            ) OR (
                SELECT count(*) FROM public.tandem_members m
                WHERE m.tandem_id = target_tandem_id AND m.role = 'OWNER'
            ) > 1
        $$;
        """
    )

    for table in ("tandems", "tandem_members", "invitations"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY tandems_select ON tandems FOR SELECT
            USING (
                app.can_view_tandem(id, app.current_user_id())
                OR created_by = app.current_user_id()
            );
        CREATE POLICY tandems_insert ON tandems FOR INSERT
            WITH CHECK (created_by = app.current_user_id());
        CREATE POLICY tandems_update ON tandems FOR UPDATE
            USING (app.is_tandem_owner(id, app.current_user_id()))
            WITH CHECK (app.is_tandem_owner(id, app.current_user_id()));

        CREATE POLICY tandem_members_select ON tandem_members FOR SELECT
            USING (
                app.is_tandem_member(tandem_id, app.current_user_id())
                OR (
                    user_id = app.current_user_id()
                    AND (
                        app.is_tandem_creator(tandem_id, app.current_user_id())
                        OR app.can_join_via_invitation(tandem_id, app.current_user_id())
                    )
                )
            );
        CREATE POLICY tandem_members_insert ON tandem_members FOR INSERT
            WITH CHECK (
                app.is_tandem_owner(tandem_id, app.current_user_id())
                OR (
                    user_id = app.current_user_id()
                    AND (app.is_tandem_creator(tandem_id, app.current_user_id())
                         OR app.can_join_via_invitation(tandem_id, app.current_user_id()))
                )
            );
        CREATE POLICY tandem_members_delete ON tandem_members FOR DELETE
            USING (
                app.is_tandem_owner(tandem_id, app.current_user_id())
                OR (
                    user_id = app.current_user_id()
                    AND app.can_leave_tandem(tandem_id, user_id)
                )
            );

        CREATE POLICY invitations_select ON invitations FOR SELECT
            USING (
                app.is_tandem_member(tandem_id, app.current_user_id())
                OR app.current_user_id() IS NOT NULL
            );
        CREATE POLICY invitations_insert ON invitations FOR INSERT
            WITH CHECK (app.is_tandem_owner(tandem_id, app.current_user_id()));
        CREATE POLICY invitations_update ON invitations FOR UPDATE
            USING (
                app.is_tandem_owner(tandem_id, app.current_user_id())
                OR app.user_email_matches(app.current_user_id(), invited_email)
            )
            WITH CHECK (
                app.is_tandem_owner(tandem_id, app.current_user_id())
                OR (
                    app.user_email_matches(app.current_user_id(), invited_email)
                    AND status IN ('ACCEPTED', 'DECLINED', 'EXPIRED')
                )
            );
        """
    )

    runtime_role = os.getenv("DATABASE_RUNTIME_ROLE", "tandem_app")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", runtime_role):
        raise RuntimeError("DATABASE_RUNTIME_ROLE must be a simple PostgreSQL role name")
    # A fresh local installation provisions tandem_app. For an existing/simple test
    # database, granting to the migration role keeps Alembic usable; that role must
    # not be used by the deployed application.
    op.execute(
        f"""
            DO $grant$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{runtime_role}') THEN
                    EXECUTE format('GRANT USAGE ON SCHEMA public, app TO %I', '{runtime_role}');
                    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON users, auth_sessions, oauth_states, tandems, tandem_members, invitations TO %I', '{runtime_role}');
                    EXECUTE format('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app TO %I', '{runtime_role}');
                ELSE
                    EXECUTE format('GRANT USAGE ON SCHEMA public, app TO %I', current_user);
                    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON users, auth_sessions, oauth_states, tandems, tandem_members, invitations TO %I', current_user);
                END IF;
            END
            $grant$;
            """
    )


def downgrade() -> None:
    for table in ("tandem_members", "invitations", "tandems"):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_invitations_active_recipient", table_name="invitations")
    op.drop_table("oauth_states")
    op.drop_table("auth_sessions")
    op.drop_table("invitations")
    op.drop_table("tandem_members")
    op.drop_table("tandems")
    op.drop_table("users")
    op.execute("DROP FUNCTION IF EXISTS app.can_view_tandem(uuid, uuid)")
    op.execute("DROP FUNCTION IF EXISTS app.can_leave_tandem(uuid, uuid)")
    op.execute("DROP FUNCTION IF EXISTS app.can_join_via_invitation(uuid, uuid)")
    op.execute("DROP FUNCTION IF EXISTS app.user_email_matches(uuid, text)")
    op.execute("DROP FUNCTION IF EXISTS app.is_tandem_creator(uuid, uuid)")
    op.execute("DROP FUNCTION IF EXISTS app.is_tandem_owner(uuid, uuid)")
    op.execute("DROP FUNCTION IF EXISTS app.is_tandem_member(uuid, uuid)")
    op.execute("DROP FUNCTION IF EXISTS app.current_user_id()")
    op.execute("DROP FUNCTION IF EXISTS app.set_updated_at()")
    op.execute("DROP SCHEMA app")
