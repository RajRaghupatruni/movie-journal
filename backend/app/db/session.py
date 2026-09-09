from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.core.config import Settings


def create_db_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=5,
        hide_parameters=True,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
    )


def set_current_user_id(session: Session, user_id: str) -> None:
    """Set the request identity for this transaction without interpolating SQL."""

    session.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": user_id},
    )


def assert_runtime_role(engine: Engine, expected_role: str) -> None:
    """Fail closed if production is connected with a role that defeats RLS."""

    with engine.connect() as connection:
        role_name, is_superuser, bypasses_rls = connection.execute(
            text(
                """
                SELECT current_user, r.rolsuper, r.rolbypassrls
                FROM pg_roles r
                WHERE r.rolname = current_user
                """
            )
        ).one()
    if role_name != expected_role or is_superuser or bypasses_rls:
        raise RuntimeError("DATABASE_URL must use a dedicated non-bypass-RLS runtime role")


def get_db(request: Request) -> Iterator[Session]:
    # Callers own commit boundaries; close rolls back uncommitted work, including errors.
    with request.app.state.session_factory() as session:
        yield session
