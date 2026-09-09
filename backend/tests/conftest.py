import pytest

from app.core.config import Settings


@pytest.fixture
def settings():
    # Non-secret, isolated test fixture. Unit tests never connect to this address.
    return Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+psycopg://fixture:fixture@127.0.0.1:1/fixture",
    )
