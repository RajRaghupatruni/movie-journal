from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker

from app.api.auth import build_google_oauth
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.invitations import router as invitation_router
from app.api.tandems import router as tandem_router
from app.core.config import Settings, load_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.db.session import assert_runtime_role, create_db_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_db_engine(settings)
        if settings.app_env == "production":
            assert_runtime_role(engine, settings.database_runtime_role)
        app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Tandem API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.google_oauth = build_google_oauth(settings)
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router)
    app.include_router(tandem_router, prefix="/api")
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
    app.add_middleware(RequestContextMiddleware)
    return app
