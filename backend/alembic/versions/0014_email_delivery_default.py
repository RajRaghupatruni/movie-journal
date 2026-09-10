"""Default anniversary email preference to disabled for new users."""

from alembic import op

revision = "0014_email_delivery_default"
down_revision = "0013_security_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows keep their explicit preference; only future rows use the
    # launch-safe default. Global delivery is separately disabled by config.
    op.alter_column(
        "user_notification_preferences",
        "anniversary_email_enabled",
        server_default="false",
    )


def downgrade() -> None:
    op.alter_column(
        "user_notification_preferences",
        "anniversary_email_enabled",
        server_default="true",
    )
