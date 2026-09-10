import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_db, set_current_user_id
from app.models import (
    AuthSession,
    Invitation,
    Memory,
    MemoryMedia,
    OAuthState,
    Tandem,
    TandemMember,
    User,
    UserNotificationPreference,
)
from app.schemas.auth import (
    AccountAction,
    NotificationPreferencePatch,
    NotificationPreferenceResponse,
    TandemResponse,
    UserResponse,
)
from app.services.auth import (
    create_auth_session,
    get_current_user,
    get_current_user_including_inactive,
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
        select(OAuthState)
        .where(
            OAuthState.state_hash == hash_secret(query_state),
            OAuthState.consumed_at.is_(None),
            OAuthState.expires_at > datetime.now(UTC),
        )
        .with_for_update()
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
    was_inactive = user is not None and not user.is_active
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

    db.flush()
    if not was_inactive:
        set_current_user_id(db, str(user.id))
        if (
            db.scalar(
                select(UserNotificationPreference).where(
                    UserNotificationPreference.user_id == user.id
                )
            )
            is None
        ):
            db.add(UserNotificationPreference(user_id=user.id))

    oauth_state.consumed_at = datetime.now(UTC)
    db.flush()
    raw_session = create_auth_session(db, user.id, settings, reactivation_only=was_inactive)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Account conflict"
        ) from None

    redirect_target = (
        f"{settings.frontend_url.rstrip('/')}/reactivate" if was_inactive else settings.frontend_url
    )
    response = RedirectResponse(redirect_target, status_code=status.HTTP_303_SEE_OTHER)
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


def _owner_blockers(db: Session, user_id):
    rows = db.execute(
        select(Tandem.id, Tandem.name)
        .join(TandemMember, TandemMember.tandem_id == Tandem.id)
        .where(TandemMember.user_id == user_id, TandemMember.role == "OWNER")
    ).all()
    blockers = []
    for tandem_id, name in rows:
        owners = (
            db.scalar(
                select(func.count())
                .select_from(TandemMember)
                .where(TandemMember.tandem_id == tandem_id, TandemMember.role == "OWNER")
            )
            or 0
        )
        if owners <= 1:
            blockers.append({"id": str(tandem_id), "name": name})
    return blockers


@router.post("/api/me/deactivate", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_account(
    payload: AccountAction,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if payload.confirmation != "DEACTIVATE":
        raise HTTPException(status_code=422, detail="Type DEACTIVATE to confirm")
    blockers = _owner_blockers(db, current_user.id)
    if blockers:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Promote another owner or delete these Tandems before deactivating",
                "tandems": blockers,
            },
        )
    db.execute(
        text("SELECT app.clear_user_delivery_state(:user_id)"), {"user_id": str(current_user.id)}
    )
    db.execute(delete(TandemMember).where(TandemMember.user_id == current_user.id))
    current_user.is_active = False
    current_user.deactivated_at = datetime.now(UTC)
    db.commit()
    settings: Settings = request.app.state.settings
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/api/me/reactivation", response_model=UserResponse)
def reactivation_status(
    current_user: User = Depends(get_current_user_including_inactive),
) -> UserResponse:
    if current_user.is_active:
        raise HTTPException(status_code=409, detail="Account is already active")
    return UserResponse.model_validate(current_user)


@router.post("/api/me/reactivate", response_model=UserResponse)
def reactivate_account(
    current_user: User = Depends(get_current_user_including_inactive), db: Session = Depends(get_db)
) -> UserResponse:
    if current_user.is_active:
        return UserResponse.model_validate(current_user)
    current_user.is_active = True
    current_user.deactivated_at = None
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == current_user.id)
        .values(reactivation_only=False)
    )
    db.commit()
    set_current_user_id(db, str(current_user.id))
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.post("/api/me/delete", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: AccountAction,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if payload.confirmation != "DELETE":
        raise HTTPException(
            status_code=422, detail="Type DELETE to permanently remove your account"
        )
    blockers = _owner_blockers(db, current_user.id)
    if blockers:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Promote another owner or delete these Tandems before deleting your account"
                ),
                "tandems": blockers,
            },
        )
    user_id = current_user.id
    email = current_user.email
    now = datetime.now(UTC)
    if email:
        db.execute(
            update(Invitation)
            .where(Invitation.invited_email == email, Invitation.status == "PENDING")
            .values(status="REVOKED", responded_at=now)
        )
    db.execute(update(Tandem).where(Tandem.created_by == user_id).values(created_by=None))
    db.execute(update(Memory).where(Memory.created_by == user_id).values(created_by=None))
    db.execute(update(MemoryMedia).where(MemoryMedia.created_by == user_id).values(created_by=None))
    db.execute(update(Invitation).where(Invitation.invited_by == user_id).values(invited_by=None))
    db.execute(update(Invitation).where(Invitation.accepted_by == user_id).values(accepted_by=None))
    db.execute(text("SELECT app.clear_user_delivery_state(:user_id)"), {"user_id": str(user_id)})
    db.execute(delete(TandemMember).where(TandemMember.user_id == user_id))
    db.execute(
        delete(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
    )
    current_user.google_subject = None
    current_user.email = None
    current_user.display_name = "Former member"
    current_user.avatar_url = None
    current_user.is_active = False
    current_user.deleted_at = now
    db.delete(current_user)
    db.commit()
    settings: Settings = request.app.state.settings
    response.delete_cookie(settings.session_cookie_name, path="/")


def _preferences(db: Session, user_id) -> UserNotificationPreference:
    preference = db.scalar(
        select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
    )
    if preference is None:
        preference = UserNotificationPreference(user_id=user_id)
        db.add(preference)
        db.flush()
    return preference


@router.get("/api/me/preferences", response_model=NotificationPreferenceResponse)
def get_preferences(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> NotificationPreferenceResponse:
    preference = _preferences(db, current_user.id)
    db.commit()
    return NotificationPreferenceResponse.model_validate(preference)


@router.patch("/api/me/preferences", response_model=NotificationPreferenceResponse)
def update_preferences(
    payload: NotificationPreferencePatch,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreferenceResponse:
    preference = _preferences(db, current_user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(preference, key, value)
    db.commit()
    set_current_user_id(db, str(current_user.id))
    db.refresh(preference)
    return NotificationPreferenceResponse.model_validate(preference)


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
