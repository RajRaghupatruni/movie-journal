"""Harden RLS helper ownership against recursive policy evaluation."""

from __future__ import annotations

import os
import re

from alembic import op

revision = "0015_rls_helper_ownership"
down_revision = "0014_email_delivery_default"
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


def _role() -> str:
    value = os.getenv("DATABASE_RUNTIME_ROLE", "tandem_app")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise RuntimeError("DATABASE_RUNTIME_ROLE must be a simple PostgreSQL role name")
    return value


def upgrade() -> None:
    runtime_role = _role()
    helper_values = ", ".join(f"({helper!r})" for helper in RLS_HELPERS)
    op.execute(
        f"""
        DO $rls_helper_owner$
        DECLARE
            helper regprocedure;
        BEGIN
            FOR helper IN
                SELECT signature::regprocedure FROM (VALUES {helper_values}) AS h(signature)
            LOOP
                EXECUTE format('ALTER FUNCTION %s OWNER TO %I', helper, current_user);
                EXECUTE format('ALTER FUNCTION %s SECURITY DEFINER', helper);
                EXECUTE format(
                    'ALTER FUNCTION %s SET search_path = pg_catalog, public, app',
                    helper
                );
                EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', helper);
                EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO %I', helper, '{runtime_role}');
            END LOOP;
        END
        $rls_helper_owner$;
        """
    )


def downgrade() -> None:
    # Do not restore PUBLIC execution. The pre-migration state was unsafe when helpers were
    # accidentally owned by the runtime role, and keeping explicit grants is backward compatible.
    runtime_role = _role()
    helper_values = ", ".join(f"({helper!r})" for helper in RLS_HELPERS)
    op.execute(
        f"""
        DO $rls_helper_grants$
        DECLARE
            helper regprocedure;
        BEGIN
            FOR helper IN
                SELECT signature::regprocedure FROM (VALUES {helper_values}) AS h(signature)
            LOOP
                EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', helper);
                EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO %I', helper, '{runtime_role}');
            END LOOP;
        END
        $rls_helper_grants$;
        """
    )
