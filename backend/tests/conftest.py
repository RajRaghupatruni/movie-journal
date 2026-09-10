import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine

from alembic import command
from app.core.config import Settings


@pytest.fixture
def settings():
    # Non-secret, isolated test fixture. Unit tests never connect to this address.
    return Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+psycopg://fixture:fixture@127.0.0.1:1/fixture",
    )


@pytest.fixture(scope="session")
def postgres_urls():
    runtime_url = os.getenv("TEST_DATABASE_URL")
    owner_url = os.getenv("TEST_DATABASE_OWNER_URL")
    if not runtime_url or not owner_url:
        pytest.fail(
            "TEST_DATABASE_URL and TEST_DATABASE_OWNER_URL are required; "
            "start the disposable PostgreSQL test Compose project first",
            pytrace=False,
        )
    return runtime_url, owner_url


@pytest.fixture(scope="session")
def migrated_postgres(postgres_urls):
    _, owner_url = postgres_urls
    old_database_url = os.environ.get("DATABASE_URL")
    old_migration_url = os.environ.get("MIGRATION_DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = owner_url
        os.environ.pop("MIGRATION_DATABASE_URL", None)
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        command.upgrade(config, "head")
    finally:
        if old_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_database_url
        if old_migration_url is None:
            os.environ.pop("MIGRATION_DATABASE_URL", None)
        else:
            os.environ["MIGRATION_DATABASE_URL"] = old_migration_url
    yield


@pytest.fixture(scope="session")
def postgres_engines(postgres_urls, migrated_postgres):
    runtime_url, owner_url = postgres_urls
    owner_engine = create_engine(owner_url, pool_pre_ping=True)
    runtime_engine = create_engine(runtime_url, pool_pre_ping=True)
    try:
        yield runtime_engine, owner_engine
    finally:
        runtime_engine.dispose()
        owner_engine.dispose()
