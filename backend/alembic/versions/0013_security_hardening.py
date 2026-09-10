"""Tighten invitation row visibility for the runtime role."""

from alembic import op

revision = "0013_security_hardening"
down_revision = "0012_product_completion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A previous compatibility policy allowed every authenticated runtime session
    # to SELECT every invitation row. Owners see their Tandem's invitations and
    # invitees see only invitations addressed to their verified email.
    op.execute("DROP POLICY invitations_select ON invitations")
    op.execute(
        """
        CREATE POLICY invitations_select ON invitations FOR SELECT
            USING (
                app.is_tandem_member(tandem_id, app.current_user_id())
                OR app.user_email_matches(app.current_user_id(), invited_email)
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY invitations_select ON invitations")
    op.execute(
        """
        CREATE POLICY invitations_select ON invitations FOR SELECT
            USING (
                app.is_tandem_member(tandem_id, app.current_user_id())
                OR app.current_user_id() IS NOT NULL
            )
        """
    )
