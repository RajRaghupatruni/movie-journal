"""OAuth compatibility tests for Authlib's transient Starlette session."""

import os
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import OAUTH_STATE_COOKIE
from app.core.config import Settings
from app.main import create_app
from app.models import AuthSession, OAuthState
from app.services.auth import hash_secret

pytestmark = pytest.mark.integration


@pytest.fixture
def oauth_environment(postgres_engines, monkeypatch):
    _, owner_engine = postgres_engines
    app = create_app(
        Settings(
            _env_file=None,
            app_env="test",
            database_url=os.environ["TEST_DATABASE_URL"],
            database_runtime_role=os.getenv("DATABASE_RUNTIME_ROLE", "tandem_app"),
            google_client_id="test-client-id",
            google_client_secret=SecretStr("test-client-secret"),
            oauth_session_secret=SecretStr("test-oauth-session-secret"),
        )
    )
    google = app.state.google_oauth.google

    async def fake_authorize_redirect(request: Request, redirect_uri: str, **kwargs):
        # This is the exact access Authlib needs from SessionMiddleware.
        request.session["authlib_transient_marker"] = "present"
        return RedirectResponse(f"{redirect_uri}?state={kwargs['state']}", status_code=307)

    async def fake_authorize_access_token(request: Request):
        assert request.session["authlib_transient_marker"] == "present"
        return {
            "userinfo": {
                "sub": "oauth-test-subject",
                "email": "oauth-test@example.test",
                "email_verified": True,
                "name": "OAuth Test User",
            }
        }

    monkeypatch.setattr(google, "authorize_redirect", fake_authorize_redirect)
    monkeypatch.setattr(google, "authorize_access_token", fake_authorize_access_token)
    return app, owner_engine


def _start_login(client: TestClient) -> str:
    response = client.get("/auth/google/login", follow_redirects=False)
    assert response.status_code == 307, response.text
    location_state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
    cookie_state = client.cookies.get("tandem_oauth_state")
    assert location_state == cookie_state
    return cookie_state


def test_google_login_has_authlib_session_without_replacing_db_state(oauth_environment):
    app, owner_engine = oauth_environment
    with TestClient(app) as client:
        state = _start_login(client)
        assert client.cookies.get("tandem_oauth_session")

    with Session(owner_engine) as db:
        record = db.scalar(select(OAuthState).where(OAuthState.state_hash == hash_secret(state)))
        assert record is not None
        assert record.consumed_at is None
        assert record.state_hash != state


def test_missing_or_forged_oauth_state_is_rejected(oauth_environment):
    app, _ = oauth_environment
    with TestClient(app) as client:
        assert client.get("/auth/google/callback?state=forged").status_code == 400
        client.cookies.set("tandem_oauth_state", "cookie-state")
        response = client.get("/auth/google/callback?state=query-state")
        assert response.status_code == 400


def test_successful_callback_uses_opaque_db_auth_session_and_logout_unchanged(
    oauth_environment,
):
    app, owner_engine = oauth_environment
    with TestClient(app) as client:
        state = _start_login(client)
        response = client.get(
            f"/auth/google/callback?state={state}&code=fake-code", follow_redirects=False
        )
        assert response.status_code == 303
        assert client.get("/api/me").status_code == 200
        raw_session = client.cookies.get("tandem_session")
        assert raw_session
        assert not client.cookies.get("tandem_oauth_session")
        assert "tandem_oauth_session=null" in response.headers.get("set-cookie", "")

        with Session(owner_engine) as db:
            oauth_state = db.scalar(
                select(OAuthState).where(OAuthState.state_hash == hash_secret(state))
            )
            assert oauth_state is not None
            assert oauth_state.consumed_at is not None
            auth_session = db.scalar(
                select(AuthSession).where(AuthSession.token_hash == hash_secret(raw_session))
            )
            assert auth_session is not None

        assert client.post("/auth/logout").status_code == 204
        assert client.get("/api/me").status_code == 401
        client.cookies.set(OAUTH_STATE_COOKIE, state)
        assert client.get(f"/auth/google/callback?state={state}&code=fake-code").status_code == 400
        with Session(owner_engine) as db:
            assert (
                db.scalar(
                    select(AuthSession).where(AuthSession.token_hash == hash_secret(raw_session))
                )
                is None
            )
