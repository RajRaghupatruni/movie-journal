import pytest
from pydantic import ValidationError

from app.core.config import Settings, load_settings


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///local.db",
        "postgresql://user:password@localhost/db",
        "not-a-url",
        "postgresql+psycopg://user@localhost/db",
    ],
)
def test_rejects_invalid_database_configuration(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=url)


@pytest.mark.parametrize("origin", ["*", "https://outside.example", "http://localhost.evil:5173"])
def test_rejects_nonlocal_cors(settings, origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=settings.database_url, cors_origins=[origin])


def test_database_is_required(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="Invalid application configuration"):
        load_settings()


def test_startup_error_does_not_echo_environment(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("DATABASE_URL", "private-canary")
    with pytest.raises(RuntimeError) as error:
        load_settings()
    assert "private-canary" not in str(error.value)


def test_settings_repr_hides_credentials(settings):
    assert settings.database_url.get_secret_value() not in repr(settings)
