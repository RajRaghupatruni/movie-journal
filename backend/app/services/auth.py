import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_db, set_current_user_id
from app.models import AuthSession, User


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    settings: Settings = request.app.state.settings
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_secret(raw_token),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    # This is transaction-local. get_db rolls the transaction back when the request ends,
    # so a pooled connection cannot carry this identity to a later request.
    set_current_user_id(db, str(session.user_id))
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    return user


def create_auth_session(db: Session, user_id, settings: Settings) -> str:
    raw_token = new_secret()
    db.add(
        AuthSession(
            user_id=user_id,
            token_hash=hash_secret(raw_token),
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds),
        )
    )
    return raw_token
