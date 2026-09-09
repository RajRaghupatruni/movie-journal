import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_db, set_current_user_id
from app.models import AuthSession, OAuthState, User
from app.schemas.auth import TandemResponse, UserResponse
from app.services.auth import (
    create_auth_session,
    get_current_user,
    hash_secret,
    new_secret,
    normalize_email,
)

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)
OAUTH_STATE_COOKIE = "tandem_oauth_state"
GOOGLE_DISCOVERY = "https://accounts.google.com/.well-known/openid-configuration"


def build_google_oauth(settings: Settings) -> OAuth:
    oauth = OAuth()
    if settings.google_client_id and settings.google_client_secret:
        oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret.get_secret_value(),
            server_metadata_url=GOOGLE_DISCOVERY,
            client_kwargs={"scope": "openid email profile"},
        )
    return oauth


def _set_cookie(
    response: Response, name: str, value: str, settings: Settings, max_age: int
) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
    )


@router.get("/auth/google/login")
async def google_login(request: Request, db: Session = Depends(get_db)):
    settings: Settings = request.app.state.settings
    google = getattr(request.app.state.google_oauth, "google", None)
    if google is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google authentication is not configured",
        )

    raw_state = new_secret()
    db.add(
        OAuthState(
            state_hash=hash_secret(raw_state),
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.oauth_state_ttl_seconds),
        )
    )
    db.commit()
    response = await google.authorize_redirect(
        request, settings.google_redirect_uri, state=raw_state
    )
    _set_cookie(response, OAUTH_STATE_COOKIE, raw_state, settings, settings.oauth_state_ttl_seconds)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    settings: Settings = request.app.state.settings
    query_state = request.query_params.get("state")
    cookie_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if not query_state or not cookie_state or query_state != cookie_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    oauth_state = db.scalar(
        select(OAuthState).where(
            OAuthState.state_hash == hash_secret(query_state),
            OAuthState.consumed_at.is_(None),
            OAuthState.expires_at > datetime.now(UTC),
        ).with_for_update()
    )
    if oauth_state is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    google = getattr(request.app.state.google_oauth, "google", None)
    if google is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google authentication is not configured",
        )
    try:
        token = await google.authorize_access_token(request)
        profile = token.get("userinfo")
        if not isinstance(profile, Mapping):
            profile = await google.userinfo(token=token)
    except Exception:
        logger.warning("google_authentication_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google authentication failed",
        ) from None

    subject = str(profile.get("sub", "")).strip()
    email = normalize_email(str(profile.get("email", "")))
    email_verified = profile.get("email_verified")
    if not subject or not email or email_verified not in {True, "true", "1"}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account does not provide a verified identity",
        )

    user = db.scalar(select(User).where(User.google_subject == subject))
    if user is None:
        email_match = db.scalar(select(User).where(User.email == email))
        if email_match is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Google identity is already associated with another account",
            )
        user = User(
            google_subject=subject,
            email=email,
            display_name=str(profile.get("name") or email)[:200],
            avatar_url=str(profile["picture"])[:2048] if profile.get("picture") else None,
        )
        db.add(user)
    else:
        user.email = email
        user.display_name = str(profile.get("name") or user.display_name)[:200]
        user.avatar_url = str(profile["picture"])[:2048] if profile.get("picture") else None

    oauth_state.consumed_at = datetime.now(UTC)
    db.flush()
    raw_session = create_auth_session(db, user.id, settings)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Account conflict"
        ) from None

    response = RedirectResponse(settings.frontend_url, status_code=status.HTTP_303_SEE_OTHER)
    _set_cookie(
        response,
        settings.session_cookie_name,
        raw_session,
        settings,
        settings.session_ttl_seconds,
    )
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    settings: Settings = request.app.state.settings
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_secret(raw_token)))
        db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/api/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get("/api/me/tandems", response_model=list[TandemResponse])
def my_tandems(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[TandemResponse]:
    set_current_user_id(db, str(current_user.id))
    from app.models import Tandem, TandemMember

    tandems = db.scalars(
        select(Tandem)
        .join(TandemMember, TandemMember.tandem_id == Tandem.id)
        .where(TandemMember.user_id == current_user.id)
        .order_by(Tandem.created_at, Tandem.id)
    ).all()
    return [TandemResponse.model_validate(tandem) for tandem in tandems]
