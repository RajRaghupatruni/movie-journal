from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import build_google_oauth
from app.api.auth import router as auth_router
from app.api.global_views import router as global_view_router
from app.api.health import liveness_router
from app.api.health import router as health_router
from app.api.integrations import router as integration_router
from app.api.invitations import router as invitation_router
from app.api.media import router as media_router
from app.api.memories import router as memory_router
from app.api.nostalgia import router as nostalgia_router
from app.api.notifications import router as notification_router
from app.api.rediscovery import router as rediscovery_router
from app.api.tandems import router as tandem_router
from app.core.config import Settings, load_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.rate_limit import InProcessRateLimitMiddleware
from app.core.security import SameOriginMiddleware, SecurityHeadersMiddleware
from app.db.session import assert_runtime_role, create_db_engine
from app.services.media_storage import build_object_storage
from app.web import SPAStaticFiles

OAUTH_SESSION_COOKIE = "tandem_oauth_session"


def add_oauth_session_middleware(app: FastAPI, settings: Settings) -> None:
    """Provide Authlib's transient request.session storage, not application auth."""
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.get_oauth_session_secret(),
        session_cookie=OAUTH_SESSION_COOKIE,
        max_age=settings.oauth_state_ttl_seconds,
        https_only=settings.app_env == "production",
        same_site="lax",
        path="/",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    settings.get_oauth_session_secret()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_db_engine(settings)
        if settings.app_env == "production":
            assert_runtime_role(engine, settings.database_runtime_role)
        app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        app.state.object_storage = build_object_storage(settings)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Tandem API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.google_oauth = build_google_oauth(settings)
    app.include_router(health_router, prefix="/api")
    app.include_router(liveness_router)
    app.include_router(auth_router)
    app.include_router(tandem_router, prefix="/api")
    app.include_router(memory_router, prefix="/api")
    app.include_router(nostalgia_router, prefix="/api")
    app.include_router(notification_router)
    app.include_router(rediscovery_router)
    app.include_router(global_view_router)
    app.include_router(integration_router, prefix="/api")
    app.include_router(media_router, prefix="/api")
    app.include_router(invitation_router)
    if settings.app_env == "development" and settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Content-Type", "X-Request-ID"],
            expose_headers=["X-Request-ID"],
        )
    add_oauth_session_middleware(app, settings)
    app.add_middleware(SameOriginMiddleware, settings=settings)
    app.add_middleware(InProcessRateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    app.add_middleware(RequestContextMiddleware)

    # The Docker image copies Vite's output to /app/dist. The second candidate keeps the
    # same app usable from a source checkout after `npm run build` during local verification.
    candidates = [
        Path.cwd() / "dist",
        Path(__file__).resolve().parents[2] / "dist",
    ]
    static_dir = next((candidate for candidate in candidates if candidate.is_dir()), None)
    if settings.app_env == "production" and static_dir is None:
        raise RuntimeError("Production frontend assets are missing; run the frontend build")
    if settings.app_env != "test" and static_dir is not None:
        app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="frontend")
    return app
