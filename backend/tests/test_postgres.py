"""Opt in using TEST_DATABASE_URL pointing at a disposable PostgreSQL database."""

import os

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.mark.integration
def test_health_against_postgres():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    app = create_app(Settings(_env_file=None, database_url=url, app_env="test"))
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
