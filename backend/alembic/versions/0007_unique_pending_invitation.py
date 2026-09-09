"""Prevent concurrent duplicate pending invitations."""

import sqlalchemy as sa

from alembic import op

revision = "0007_pending_invite_uq"
down_revision = "0006_membership_pk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_invitations_active_recipient")
    op.create_index(
        "uq_invitations_pending_recipient",
        "invitations",
        ["tandem_id", "invited_email"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_invitations_pending_recipient")
    op.create_index(
        "ix_invitations_active_recipient",
        "invitations",
        ["tandem_id", "invited_email", "status"],
    )
