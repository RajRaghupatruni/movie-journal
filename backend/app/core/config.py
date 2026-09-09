from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: SecretStr
    migration_database_url: SecretStr | None = None
    database_runtime_role: str = "tandem_app"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    frontend_url: str = "http://localhost:5173"
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    session_cookie_name: str = "tandem_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    oauth_state_ttl_seconds: int = 600

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = (
                url.drivername == "postgresql+psycopg"
                and url.host
                and url.database
                and url.username
                and url.password
                and len(url.query) == 0
            )
            # Force port parsing here as well.
            _ = url.port
        except Exception:
            valid = False
        if not valid:
            raise ValueError("DATABASE_URL must be a PostgreSQL psycopg URL with credentials")
        return value

    @field_validator("cors_origins")
    @classmethod
    def local_origins_only(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme != "http"
                or parsed.hostname not in {"localhost", "127.0.0.1"}
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CORS origins must be explicit local HTTP origins")
            _ = parsed.port
        return origins

    @field_validator("database_runtime_role")
    @classmethod
    def validate_database_runtime_role(cls, role: str) -> str:
        if not role or not role.replace("_", "").isalnum():
            raise ValueError("DATABASE_RUNTIME_ROLE must be a simple PostgreSQL role name")
        return role

    @field_validator("session_ttl_seconds", "oauth_state_ttl_seconds")
    @classmethod
    def validate_positive_ttl(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("expiration settings must be positive")
        return value


def load_settings() -> Settings:
    try:
        return Settings()
    except (ValidationError, ValueError):
        # Settings validation can otherwise print secret environment inputs in tracebacks.
        raise RuntimeError(
            "Invalid application configuration; check environment names and formats"
        ) from None
