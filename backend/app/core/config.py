from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import (
    AliasChoices,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    app_env: Literal["development", "test", "production"] = "development"
    # The worker shares the production settings contract but never constructs the web app.
    # Keep this explicit so web-only secrets do not become cron requirements.
    service_mode: Literal["web", "worker"] = "web"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: SecretStr
    migration_database_url: SecretStr | None = None
    database_runtime_role: str = "tandem_app"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    frontend_url: str = Field(
        default="http://localhost:5173",
        validation_alias=AliasChoices("APPLICATION_URL", "FRONTEND_URL"),
    )
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    oauth_session_secret: SecretStr | None = None
    session_cookie_name: str = "tandem_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    oauth_state_ttl_seconds: int = 600
    tmdb_api_token: SecretStr | None = None
    tmdb_base_url: str = "https://api.themoviedb.org/3"
    tmdb_image_base_url: str = "https://image.tmdb.org/t/p"
    geoapify_api_key: SecretStr | None = None
    geoapify_base_url: str = "https://api.geoapify.com/v1"
    provider_timeout_seconds: float = 5.0
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    s3_region: str | None = None
    media_max_bytes: int = 10 * 1024 * 1024
    media_max_dimension: int = 2400
    media_max_count: int = 10
    email_delivery_enabled: bool = False
    resend_api_key: SecretStr | None = None
    allow_non_production_emails: bool = False
    resend_from_address: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RESEND_FROM_EMAIL", "RESEND_FROM_ADDRESS"),
    )

    @property
    def application_url(self) -> str:
        return self.frontend_url

    @field_validator("provider_timeout_seconds")
    @classmethod
    def validate_provider_timeout(cls, value: float) -> float:
        if value <= 0 or value > 30:
            raise ValueError("PROVIDER_TIMEOUT_SECONDS must be between 0 and 30")
        return value

    @field_validator("media_max_bytes", "media_max_dimension", "media_max_count")
    @classmethod
    def validate_media_limits(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("media limits must be positive")
        return value

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return value
        try:
            url = make_url(value.get_secret_value())
            valid = (
                url.drivername == "postgresql+psycopg"
                and url.host
                and url.database
                and url.username
                and url.password
                and set(url.query).issubset({"sslmode", "channel_binding"})
            )
            # Force port parsing here as well.
            _ = url.port
        except Exception:
            valid = False
        if not valid:
            raise ValueError("DATABASE_URL must be a PostgreSQL psycopg URL with credentials")
        return value

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if self.app_env != "production":
            return self

        def configured(value) -> bool:
            raw = value.get_secret_value() if isinstance(value, SecretStr) else value
            return raw is not None and bool(str(raw).strip())

        required = {
            "APPLICATION_URL/FRONTEND_URL": self.frontend_url,
            "GOOGLE_CLIENT_ID": self.google_client_id,
            "GOOGLE_CLIENT_SECRET": self.google_client_secret,
            "GOOGLE_REDIRECT_URI": self.google_redirect_uri,
            "TMDB_API_TOKEN": self.tmdb_api_token,
            "GEOAPIFY_API_KEY": self.geoapify_api_key,
            "S3_ENDPOINT_URL": self.s3_endpoint_url,
            "S3_BUCKET": self.s3_bucket,
            "S3_ACCESS_KEY_ID": self.s3_access_key_id,
            "S3_SECRET_ACCESS_KEY": self.s3_secret_access_key,
            "S3_REGION": self.s3_region,
        }
        if self.service_mode == "web":
            required["OAUTH_SESSION_SECRET"] = self.oauth_session_secret
        if self.email_delivery_enabled:
            required.update(
                {
                    "RESEND_API_KEY": self.resend_api_key,
                    "RESEND_FROM_EMAIL/RESEND_FROM_ADDRESS": self.resend_from_address,
                }
            )
        missing = [name for name, value in required.items() if not configured(value)]
        if missing:
            raise ValueError("production configuration is missing: " + ", ".join(missing))

        for name, value in (
            ("APPLICATION_URL/FRONTEND_URL", self.frontend_url),
            ("GOOGLE_REDIRECT_URI", self.google_redirect_uri),
            ("S3_ENDPOINT_URL", self.s3_endpoint_url),
        ):
            parsed = urlsplit(str(value))
            if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
                raise ValueError(f"{name} must be an absolute HTTPS URL in production")
            if parsed.query or parsed.fragment:
                raise ValueError(f"{name} must not contain a query string or fragment")
        app_url = urlsplit(self.frontend_url)
        if app_url.path not in {"", "/"}:
            raise ValueError("APPLICATION_URL/FRONTEND_URL must point to the application origin")
        redirect = urlsplit(self.google_redirect_uri)
        if redirect.path != "/auth/google/callback":
            raise ValueError("GOOGLE_REDIRECT_URI must end in /auth/google/callback")
        if self.service_mode == "web":
            self.get_oauth_session_secret()
        return self

    def get_oauth_session_secret(self) -> str:
        """Return the Authlib-only session key without exposing it in settings output."""
        if self.oauth_session_secret is None:
            if self.app_env == "production" and self.service_mode == "web":
                raise ValueError("production configuration is missing: OAUTH_SESSION_SECRET")
            # This key is only for local/test transient OAuth bookkeeping. Production web
            # startup is rejected above unless an explicitly configured SecretStr is present.
            return "tandem-local-oauth-session-only-change-me"

        value = self.oauth_session_secret.get_secret_value()
        if not value.strip():
            raise ValueError("OAUTH_SESSION_SECRET must not be empty")
        if self.app_env == "production" and self.service_mode == "web":
            if self.google_client_secret and value == self.google_client_secret.get_secret_value():
                raise ValueError("OAUTH_SESSION_SECRET must be distinct from GOOGLE_CLIENT_SECRET")
            for database_secret in (self.database_url, self.migration_database_url):
                if database_secret is None:
                    continue
                database_value = database_secret.get_secret_value()
                if value == database_value or value == make_url(database_value).password:
                    raise ValueError(
                        "OAUTH_SESSION_SECRET must be distinct from database credentials"
                    )
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


def load_settings(*, service_mode: Literal["web", "worker"] = "web") -> Settings:
    try:
        settings = Settings(service_mode=service_mode)
        if service_mode == "web":
            settings.get_oauth_session_secret()
        return settings
    except (ValidationError, ValueError):
        # Settings validation can otherwise print secret environment inputs in tracebacks.
        raise RuntimeError(
            "Invalid application configuration; check environment names and formats"
        ) from None
