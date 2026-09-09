"""Allow tandem creators to receive their INSERT ... RETURNING row."""

from alembic import op

revision = "0003_creator_returning_policy"
down_revision = "0002_identity_tandems"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP POLICY tandems_select ON tandems")
    op.execute(
        """
        CREATE POLICY tandems_select ON tandems FOR SELECT
            USING (
                app.can_view_tandem(id, app.current_user_id())
                OR created_by = app.current_user_id()
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY tandems_select ON tandems")
    op.execute(
        """
        CREATE POLICY tandems_select ON tandems FOR SELECT
            USING (app.can_view_tandem(id, app.current_user_id()))
        """
    )
