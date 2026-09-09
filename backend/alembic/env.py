from alembic import context
from app import models  # noqa: F401 -- register future mapped classes
from app.core.config import load_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import create_db_engine

settings = load_settings()
configure_logging(settings.log_level)
target_metadata = Base.metadata
database_url = (
    settings.migration_database_url.get_secret_value()
    if settings.migration_database_url
    else settings.database_url.get_secret_value()
)


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if settings.migration_database_url:
        from pydantic import SecretStr

        migration_settings = settings.model_copy(
            update={"database_url": SecretStr(database_url), "migration_database_url": None}
        )
    else:
        migration_settings = settings
    engine = create_db_engine(migration_settings)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
