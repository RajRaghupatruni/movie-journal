from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AuthSession, User
from app.services.auth import hash_secret


def provision_test_user(
    owner_engine, email: str, display_name: str | None = None
) -> tuple[UUID, str]:
    """Create a deterministic test identity and raw session outside the app package."""

    user_id = uuid5(NAMESPACE_URL, f"https://tests.tandem.local/users/{email.casefold()}")
    raw_session = f"test-session-{user_id.hex}"
    with Session(owner_engine) as db, db.begin():
        user = db.scalar(select(User).where(User.id == user_id))
        if user is None:
            db.add(
                User(
                    id=user_id,
                    google_subject=f"test-subject-{user_id}",
                    email=email.casefold(),
                    display_name=display_name or email.split("@", 1)[0],
                )
            )
        else:
            user.email = email.casefold()
        db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
        db.add(
            AuthSession(
                user_id=user_id,
                token_hash=hash_secret(raw_session),
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
    return user_id, raw_session
