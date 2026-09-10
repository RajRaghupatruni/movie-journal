import json
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.logging import request_id
from app.db.session import get_db
from app.main import create_app


def test_health_success(settings):
    app = create_app(settings)
    session = MagicMock()
    session.execute.return_value.scalar_one.return_value = 1
    app.dependency_overrides[get_db] = lambda: session
    correlation = str(uuid4())
    with TestClient(app) as client:
        response = client.get("/api/health", headers={"X-Request-ID": correlation})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "application": "ok", "database": "ok"}
    assert response.headers["X-Request-ID"] == correlation
    assert response.headers["Cache-Control"] == "no-store"
    assert str(session.execute.call_args.args[0]) == "SELECT 1"


def test_database_failure_is_redacted(settings, capsys):
    app = create_app(settings)
    session = MagicMock()
    session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("private-canary"))
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as client:
        response = client.get("/api/health", headers={"X-Request-ID": "untrusted-private-canary"})
    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "application": "ok",
        "database": "unavailable",
    }
    assert UUID(response.headers["X-Request-ID"])
    assert "private-canary" not in response.text + capsys.readouterr().out


def test_unexpected_error_has_safe_response_and_correlated_json_log(settings, capsys):
    app = create_app(settings)

    @app.get("/failure")
    def fail():
        raise RuntimeError("private-canary")

    with TestClient(app) as client:
        response = client.get("/failure")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    output = capsys.readouterr().out
    assert "private-canary" not in output
    records = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    completed = next(record for record in records if record["message"] == "request_completed")
    assert completed["request_id"] == response.headers["X-Request-ID"]
    assert completed["status_code"] == 500
    assert request_id.get() is None


def test_local_cors_only(settings):
    settings.app_env = "development"
    app = create_app(settings)
    with TestClient(app) as client:
        allowed = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        rejected = client.options(
            "/api/health",
            headers={
                "Origin": "https://outside.example",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers


def test_production_does_not_enable_local_cors(settings, monkeypatch):
    # The unit test intentionally uses an unreachable fixture database; runtime-role
    # validation is covered by the PostgreSQL integration suite.
    monkeypatch.setattr("app.main.assert_runtime_role", lambda *_args: None)
    settings.app_env = "production"
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert "access-control-allow-origin" not in response.headers
