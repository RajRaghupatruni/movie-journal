"""Use the composite membership primary key as the uniqueness constraint."""

from alembic import op

revision = "0006_membership_pk"
down_revision = "0005_invitation_lookup_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF EXISTS keeps this compatible with databases initialized from an
    # earlier development revision that already relied on the composite PK.
    op.execute(
        "ALTER TABLE tandem_members "
        "DROP CONSTRAINT IF EXISTS uq_tandem_members_tandem_id"
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_tandem_members_tandem_id", "tandem_members", ["tandem_id", "user_id"]
    )
