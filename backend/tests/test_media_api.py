import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import set_current_user_id
from app.main import create_app
from app.models import MemoryMedia
from tests.helpers import provision_test_user

pytestmark = pytest.mark.integration


class FakeStorage:
    def __init__(self):
        self.objects = {}
        self.deleted = []

    def put_object(self, object_key, body, content_type):
        self.objects[object_key] = (body, content_type)

    def delete_object(self, object_key):
        self.deleted.append(object_key)
        self.objects.pop(object_key, None)

    def create_read_url(self, object_key, expires_seconds=300):
        return f"https://private.test/{object_key}?expires={expires_seconds}"


def _photo_bytes():
    stream = io.BytesIO()
    Image.new("RGB", (40, 30), "#8f4357").save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture
def media_clients(postgres_engines, monkeypatch):
    runtime_engine, owner_engine = postgres_engines
    user_a, session_a = provision_test_user(owner_engine, "media-a@example.test", "Media A")
    user_b, session_b = provision_test_user(owner_engine, "media-b@example.test", "Media B")
    user_c, session_c = provision_test_user(owner_engine, "media-c@example.test", "Media C")
    storage = FakeStorage()
    monkeypatch.setattr("app.main.build_object_storage", lambda settings: storage)
    runtime_url = os.environ["TEST_DATABASE_URL"]

    def client(raw_session):
        app = create_app(
            Settings(
                _env_file=None,
                app_env="test",
                database_url=runtime_url,
            )
        )
        result = TestClient(app)
        result.cookies.set("tandem_session", raw_session)
        return result

    return runtime_engine, owner_engine, (user_a, user_b, user_c), storage, (
        client(session_a),
        client(session_b),
        client(session_c),
    )


def test_member_media_is_private_and_memory_delete_cleans_objects(media_clients):
    runtime_engine, owner_engine, users, storage, clients = media_clients
    user_a, user_b, user_c = users
    client_a, client_b, client_c = clients
    with client_a as a, client_b as b, client_c as c:
        tandem = a.post("/api/tandems", json={"name": "Media Tandem", "timezone": "UTC"})
        tandem_id = tandem.json()["id"]
        invitation = a.post(
            f"/api/tandems/{tandem_id}/invitations",
            json={"invited_email": "media-b@example.test"},
        )
        accepted = b.post(f"/api/invitations/{invitation.json()['reference']}/accept")
        assert accepted.status_code == 200
        memory = a.post(
            f"/api/tandems/{tandem_id}/memories",
            json={
                "category": "custom",
                "title": "A private photo",
                "local_date": "2026-09-09",
                "timezone": "UTC",
                "metadata": {},
            },
        ).json()
        memory_id = memory["id"]
        upload = a.post(
            f"/api/tandems/{tandem_id}/memories/{memory_id}/media",
            files={"files": ("holiday.png", _photo_bytes(), "image/png")},
        )
        assert upload.status_code == 201, upload.text
        media_id = upload.json()[0]["id"]
        assert b.get(f"/api/tandems/{tandem_id}/memories/{memory_id}/media").status_code == 200
        assert c.get(f"/api/tandems/{tandem_id}/memories/{memory_id}/media").status_code == 404
        assert c.post(
            f"/api/tandems/{tandem_id}/memories/{memory_id}/media",
            files={"files": ("holiday.png", _photo_bytes(), "image/png")},
        ).status_code == 404
        assert a.delete(
            f"/api/tandems/{tandem_id}/memories/{memory_id}/media/{media_id}"
        ).status_code == 204
        assert not storage.objects

    with Session(runtime_engine) as db, db.begin():
        set_current_user_id(db, str(user_c))
        assert db.scalars(select(MemoryMedia)).all() == []


def test_memory_delete_removes_associated_object(media_clients):
    _, _, _, storage, clients = media_clients
    with clients[0] as client:
        tandem = client.post("/api/tandems", json={"name": "Cleanup Tandem", "timezone": "UTC"})
        tandem_id = tandem.json()["id"]
        memory = client.post(
            f"/api/tandems/{tandem_id}/memories",
            json={
                "category": "custom",
                "title": "Delete me",
                "local_date": "2026-09-09",
                "timezone": "UTC",
                "metadata": {},
            },
        ).json()
        upload = client.post(
            f"/api/tandems/{tandem_id}/memories/{memory['id']}/media",
            files={"files": ("delete.png", _photo_bytes(), "image/png")},
        )
        assert upload.status_code == 201
        assert client.delete(
            f"/api/tandems/{tandem_id}/memories/{memory['id']}",
            params={"expected_version": memory["version"]},
        ).status_code == 204
        assert storage.deleted
