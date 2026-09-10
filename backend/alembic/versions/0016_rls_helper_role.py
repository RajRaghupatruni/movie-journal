"""Run RLS authorization helpers under a non-login BYPASSRLS role.

FORCE ROW LEVEL SECURITY applies to the table owner as well as ordinary roles.
The helper role is therefore deliberately separate from the migration role:
it has no login, no superuser or role-management privileges, and is only used
as the owner of narrowly scoped SECURITY DEFINER functions.
"""

from __future__ import annotations

import os
import re

from alembic import op

revision = "0016_rls_helper_role"
down_revision = "0015_rls_helper_ownership"
branch_labels = None
depends_on = None


RLS_HELPERS = (
    "app.is_tandem_member(uuid, uuid)",
    "app.is_tandem_owner(uuid, uuid)",
    "app.is_tandem_creator(uuid, uuid)",
    "app.user_email_matches(uuid, text)",
    "app.can_join_via_invitation(uuid, uuid)",
    "app.can_view_tandem(uuid, uuid)",
    "app.can_leave_tandem(uuid, uuid)",
    "app.tandem_member_count(uuid)",
    "app.insert_notification(uuid, text, uuid, uuid, uuid, uuid, jsonb, text)",
    "app.cancel_user_tandem_notifications(uuid, uuid)",
    "app.clear_user_delivery_state(uuid)",
)


def _role(name: str, default: str) -> str:
    value = os.getenv(name, default)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise RuntimeError(f"{name} must be a simple PostgreSQL role name")
    return value


def _sql_identifier(value: str) -> str:
    return value.replace("'", "''")


def upgrade() -> None:
    runtime_role = _role("DATABASE_RUNTIME_ROLE", "tandem_app")
    helper_role = _role("DATABASE_RLS_OWNER_ROLE", "tandem_rls_owner")
    if helper_role == runtime_role:
        raise RuntimeError("DATABASE_RLS_OWNER_ROLE must differ from DATABASE_RUNTIME_ROLE")

    helper_values = ", ".join(f"({helper!r})" for helper in RLS_HELPERS)
    helper_literal = _sql_identifier(helper_role)
    runtime_literal = _sql_identifier(runtime_role)
    op.execute(
        f"""
        DO $rls_helper_role$
        DECLARE
            helper regprocedure;
            helper_is_superuser boolean;
            helper_can_login boolean;
            helper_can_create_db boolean;
            helper_can_create_role boolean;
            helper_can_replicate boolean;
            helper_bypasses_rls boolean;
        BEGIN
            SELECT r.rolsuper, r.rolcanlogin, r.rolcreatedb, r.rolcreaterole,
                   r.rolreplication, r.rolbypassrls
              INTO helper_is_superuser, helper_can_login, helper_can_create_db,
                   helper_can_create_role, helper_can_replicate, helper_bypasses_rls
              FROM pg_roles r
             WHERE r.rolname = '{helper_literal}';

            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'required RLS helper owner role % does not exist; provision it as a '
                    'NOLOGIN BYPASSRLS role before migrating',
                    '{helper_literal}';
            END IF;
            IF helper_is_superuser OR helper_can_login OR helper_can_create_db
               OR helper_can_create_role OR helper_can_replicate OR NOT helper_bypasses_rls THEN
                RAISE EXCEPTION
                    'RLS helper owner role % must be NOLOGIN, NOSUPERUSER, NOCREATEDB, '
                    'NOCREATEROLE, NOREPLICATION, BYPASSRLS',
                    '{helper_literal}';
            END IF;
            IF NOT pg_has_role(current_user, '{helper_literal}', 'USAGE') THEN
                RAISE EXCEPTION
                    'migration role % must be a member of RLS helper owner role %',
                    current_user, '{helper_literal}';
            END IF;
            IF pg_has_role('{runtime_literal}', '{helper_literal}', 'USAGE') THEN
                RAISE EXCEPTION
                    'runtime role % must not inherit the RLS helper owner role %',
                    '{runtime_literal}', '{helper_literal}';
            END IF;

            -- The helper owner can read only the authorization inputs and perform
            -- the bounded notification operations implemented by these functions.
            EXECUTE format('GRANT USAGE ON SCHEMA public, app TO %I', '{helper_literal}');
            EXECUTE format(
                'GRANT SELECT ON public.users, public.tandems, public.tandem_members, '
                'public.invitations TO %I',
                '{helper_literal}'
            );
            EXECUTE format(
                'GRANT SELECT, INSERT, DELETE ON public.notifications TO %I',
                '{helper_literal}'
            );
            EXECUTE format(
                'GRANT SELECT, DELETE ON public.notification_outbox, public.auth_sessions TO %I',
                '{helper_literal}'
            );

            -- PostgreSQL requires CREATE on the target schema for an ownership
            -- transfer. Grant it only for the transfer, then remove it below.
            EXECUTE format('GRANT CREATE ON SCHEMA app TO %I', '{helper_literal}');
            FOR helper IN
                SELECT signature::regprocedure FROM (VALUES {helper_values}) AS h(signature)
            LOOP
                EXECUTE format('ALTER FUNCTION %s OWNER TO %I', helper, '{helper_literal}');
                EXECUTE format('ALTER FUNCTION %s SECURITY DEFINER', helper);
                EXECUTE format(
                    'ALTER FUNCTION %s SET search_path = pg_catalog, public, app',
                    helper
                );
                EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', helper);
                EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO %I', helper, '{runtime_literal}');
            END LOOP;
            EXECUTE format('REVOKE CREATE ON SCHEMA app FROM %I', '{helper_literal}');
        END
        $rls_helper_role$;
        """
    )


def downgrade() -> None:
    runtime_role = _role("DATABASE_RUNTIME_ROLE", "tandem_app")
    helper_role = _role("DATABASE_RLS_OWNER_ROLE", "tandem_rls_owner")
    helper_values = ", ".join(f"({helper!r})" for helper in RLS_HELPERS)
    helper_literal = _sql_identifier(helper_role)
    runtime_literal = _sql_identifier(runtime_role)
    op.execute(
        f"""
        DO $rls_helper_downgrade$
        DECLARE
            helper regprocedure;
        BEGIN
            EXECUTE format('GRANT CREATE ON SCHEMA app TO %I', '{helper_literal}');
            FOR helper IN
                SELECT signature::regprocedure FROM (VALUES {helper_values}) AS h(signature)
            LOOP
                EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', helper);
                EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO %I', helper, '{runtime_literal}');
                EXECUTE format('ALTER FUNCTION %s OWNER TO %I', helper, current_user);
            END LOOP;
            EXECUTE format('REVOKE CREATE ON SCHEMA app FROM %I', '{helper_literal}');
            EXECUTE format(
                'REVOKE SELECT ON public.users, public.tandems, public.tandem_members, '
                'public.invitations FROM %I',
                '{helper_literal}'
            );
            EXECUTE format(
                'REVOKE SELECT, INSERT, DELETE ON public.notifications FROM %I',
                '{helper_literal}'
            );
            EXECUTE format(
                'REVOKE SELECT, DELETE ON public.notification_outbox, public.auth_sessions FROM %I',
                '{helper_literal}'
            );
        END
        $rls_helper_downgrade$;
        """
    )
