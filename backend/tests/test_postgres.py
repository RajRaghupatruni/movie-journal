"""PostgreSQL smoke checks use the shared disposable integration fixture."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings
from app.main import create_app


@pytest.mark.integration
def test_health_against_postgres(postgres_engines):
    runtime_engine, _ = postgres_engines
    app = create_app(
        Settings(
            _env_file=None,
            database_url=os.environ["TEST_DATABASE_URL"],
            app_env="test",
        )
    )
    with TestClient(app) as client, runtime_engine.connect() as connection:
        response = client.get("/api/health")
        role = connection.execute(
            text(
                "SELECT current_user, rolsuper, rolbypassrls "
                "FROM pg_roles WHERE rolname = current_user"
            )
        ).one()
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
    assert role.rolsuper is False
    assert role.rolbypassrls is False
