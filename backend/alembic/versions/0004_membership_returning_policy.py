"""Allow a newly inserted membership to be returned to its creator/invitee."""

from alembic import op

revision = "0004_membership_returning_policy"
down_revision = "0003_creator_returning_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP POLICY tandem_members_select ON tandem_members")
    op.execute(
        """
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
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY tandem_members_select ON tandem_members")
    op.execute(
        """
        CREATE POLICY tandem_members_select ON tandem_members FOR SELECT
            USING (app.is_tandem_member(tandem_id, app.current_user_id()))
        """
    )
