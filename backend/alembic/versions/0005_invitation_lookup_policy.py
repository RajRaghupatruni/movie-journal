"""Let an authenticated reference holder receive a wrong-recipient denial."""

from alembic import op

revision = "0005_invitation_lookup_policy"
down_revision = "0004_membership_returning_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
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
