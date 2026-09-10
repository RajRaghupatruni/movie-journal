from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.core.security import SameOriginMiddleware, SecurityHeadersMiddleware
from app.integrations.resend import EmailDeliveryError, ResendEmailAdapter
from app.main import add_oauth_session_middleware
from app.web import SPAStaticFiles


def production_values() -> dict:
    return {
        "_env_file": None,
        "app_env": "production",
        "database_url": "postgresql+psycopg://app:pass@neon.example/db?sslmode=require",
        "frontend_url": "https://tandem.example.com",
        "google_client_id": "client-id",
        "google_client_secret": SecretStr("client-secret"),
        "google_redirect_uri": "https://tandem.example.com/auth/google/callback",
        "oauth_session_secret": SecretStr("oauth-session-secret"),
        "tmdb_api_token": SecretStr("tmdb-token"),
        "geoapify_api_key": SecretStr("geo-token"),
        "s3_endpoint_url": "https://s3.us-west-004.backblazeb2.com",
        "s3_bucket": "private-bucket",
        "s3_access_key_id": SecretStr("access-key"),
        "s3_secret_access_key": SecretStr("secret-key"),
        "s3_region": "us-west-004",
        "email_delivery_enabled": True,
        "resend_api_key": SecretStr("resend-token"),
        "resend_from_address": "Tandem <hello@example.com>",
    }


def test_production_configuration_accepts_neon_and_provider_settings():
    settings = Settings(**production_values())
    assert settings.application_url == "https://tandem.example.com"


def test_production_configuration_rejects_missing_required_provider():
    values = production_values()
    values.pop("tmdb_api_token")
    try:
        Settings(**values)
    except ValidationError as error:
        assert "TMDB_API_TOKEN" in str(error)
    else:
        raise AssertionError("missing production provider configuration was accepted")


def test_production_configuration_requires_a_dedicated_oauth_session_secret():
    values = production_values()
    values.pop("oauth_session_secret")
    with pytest.raises(ValidationError, match="OAUTH_SESSION_SECRET"):
        Settings(**values)


def test_worker_production_configuration_does_not_require_web_oauth_secret():
    values = production_values()
    values.pop("oauth_session_secret")
    values["service_mode"] = "worker"
    settings = Settings(**values)
    assert settings.service_mode == "worker"


def test_production_oauth_session_cookie_is_secure_and_transient():
    settings = Settings(**production_values())
    app = FastAPI()

    @app.get("/oauth-session")
    def oauth_session(request: Request):
        request.session["authlib"] = "transient"
        return {"ok": True}

    add_oauth_session_middleware(app, settings)
    with TestClient(app) as client:
        response = client.get("/oauth-session")

    cookie = response.headers["set-cookie"].lower()
    assert "tandem_oauth_session=" in cookie
    assert "max-age=600" in cookie
    assert "path=/" in cookie
    assert "secure" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "tandem_session" not in cookie


def test_oauth_session_secret_cannot_reuse_provider_or_database_credentials():
    values = production_values()
    values["oauth_session_secret"] = SecretStr("client-secret")
    with pytest.raises(ValidationError, match="distinct from GOOGLE_CLIENT_SECRET"):
        Settings(**values)

    values = production_values()
    values["oauth_session_secret"] = SecretStr("pass")
    with pytest.raises(ValidationError, match="distinct from database credentials"):
        Settings(**values)


def test_production_configuration_does_not_require_resend_when_email_is_disabled():
    values = production_values()
    values["email_delivery_enabled"] = False
    values.pop("resend_api_key")
    values.pop("resend_from_address")
    settings = Settings(**values)
    assert settings.email_delivery_enabled is False


@pytest.mark.parametrize("missing", ["resend_api_key", "resend_from_address"])
def test_enabling_email_requires_resend_credentials(missing):
    values = production_values()
    values.pop(missing)
    with pytest.raises(ValidationError, match="production configuration is missing"):
        Settings(**values)


def test_non_production_email_delivery_is_disabled_by_default():
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+psycopg://app:pass@127.0.0.1:1/db",
        resend_api_key=SecretStr("would-be-production-key"),
        resend_from_address="Tandem <hello@example.com>",
    )
    with pytest.raises(EmailDeliveryError, match="disabled"):
        ResendEmailAdapter(settings).send(
            recipient="test@example.com", subject="test", html="<p>test</p>", text="test"
        )


def test_spa_fallback_does_not_hide_missing_assets_or_api_routes():
    static_dir = Path(__file__).resolve().parents[2]
    app = FastAPI()
    app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="frontend")
    with TestClient(app) as client:
        route = client.get("/timeline")
        asset = client.get("/public/vite.svg")
        assert '<div id="root"></div>' in route.text
        assert route.headers["cache-control"].startswith("no-cache")
        assert asset.status_code == 200
        assert asset.headers["cache-control"] == "public, max-age=3600"
        assert client.get("/public/missing.svg").status_code == 404
        assert client.get("/api/missing").status_code == 404


def test_security_headers_and_same_origin_protection():
    settings = Settings(
        **production_values(),
    )
    app = FastAPI()

    @app.post("/write")
    def write():
        return {"ok": True}

    @app.get("/api/private")
    def private():
        return {"secret": True}

    app.add_middleware(SameOriginMiddleware, settings=settings)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    with TestClient(app) as client:
        blocked = client.post("/write", headers={"Origin": "https://evil.example"})
        missing_origin = client.post("/write")
        malformed_origin = client.post("/write", headers={"Origin": "https://evil.example:bad"})
        allowed = client.post("/write", headers={"Origin": "https://tandem.example.com"})
        private = client.get("/api/private")
    assert blocked.status_code == 403
    assert missing_origin.status_code == 403
    assert malformed_origin.status_code == 403
    assert allowed.status_code == 200
    assert allowed.headers["x-content-type-options"] == "nosniff"
    assert allowed.headers["strict-transport-security"].startswith("max-age=31536000")
    assert private.headers["cache-control"] == "no-store"
    assert "https://*.backblazeb2.com" not in private.headers["content-security-policy"]
