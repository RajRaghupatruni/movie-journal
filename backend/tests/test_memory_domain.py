import os
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import set_current_user_id
from app.main import create_app
from app.models import ActivityEvent, Memory
from tests.helpers import provision_test_user

pytestmark = pytest.mark.integration


@pytest.fixture
def memory_clients(postgres_engines):
    runtime_engine, owner_engine = postgres_engines
    user_a, session_a = provision_test_user(owner_engine, "memory-a@example.test", "Memory A")
    user_b, session_b = provision_test_user(owner_engine, "memory-b@example.test", "Memory B")
    user_c, session_c = provision_test_user(owner_engine, "memory-c@example.test", "Memory C")
    runtime_url = os.environ["TEST_DATABASE_URL"]

    def client(raw_session: str) -> TestClient:
        app = create_app(
            Settings(
                _env_file=None,
                app_env="test",
                database_url=runtime_url,
                database_runtime_role=os.getenv("DATABASE_RUNTIME_ROLE", "tandem_app"),
            )
        )
        result = TestClient(app)
        result.cookies.set("tandem_session", raw_session)
        return result

    return (
        runtime_engine,
        owner_engine,
        (user_a, user_b, user_c),
        (client(session_a), client(session_b), client(session_c)),
    )


def _create_shared_tandem(client_a: TestClient, client_b: TestClient) -> str:
    tandem = client_a.post("/api/tandems", json={"name": "Memory Tandem", "timezone": "UTC"})
    assert tandem.status_code == 201, tandem.text
    tandem_id = tandem.json()["id"]
    invitation = client_a.post(
        f"/api/tandems/{tandem_id}/invitations", json={"invited_email": "memory-b@example.test"}
    )
    assert invitation.status_code == 201, invitation.text
    accepted = client_b.post(f"/api/invitations/{invitation.json()['reference']}/accept")
    assert accepted.status_code == 200, accepted.text
    return tandem_id


def test_memory_vertical_slice_is_member_scoped_and_versioned(memory_clients):
    (
        runtime_engine,
        owner_engine,
        (user_a, user_b, user_c),
        (client_a, client_b, client_c),
    ) = memory_clients
    with client_a as a, client_b as b, client_c as c:
        tandem_id = _create_shared_tandem(a, b)
        created = a.post(
            f"/api/tandems/{tandem_id}/memories",
            json={
                "category": "custom",
                "title": "The tiny blue door",
                "local_date": "2024-06-10",
                "timezone": "America/Chicago",
                "notes": "We almost walked past it.",
                "participant_ids": [str(user_b)],
                "tags": [" NYC "],
                "metadata": {},
            },
        )
        assert created.status_code == 201, created.text
        memory = created.json()
        memory_id = memory["id"]
        assert memory["version"] == 1
        assert memory["tags"] == ["nyc"]
        assert {participant["user_id"] for participant in memory["participants"]} == {str(user_b)}

        assert b.get(f"/api/tandems/{tandem_id}/memories").json()["items"][0]["id"] == memory_id
        updated = b.patch(
            f"/api/tandems/{tandem_id}/memories/{memory_id}",
            json={"expected_version": 1, "notes": "We stopped and took the long way home."},
        )
        assert updated.status_code == 403, updated.text
        assert updated.json()["detail"] == "You can only edit memories you created"

        updated = a.patch(
            f"/api/tandems/{tandem_id}/memories/{memory_id}",
            json={"expected_version": 1, "notes": "We stopped and took the long way home."},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["version"] == 2
        assert a.get(f"/api/tandems/{tandem_id}/memories/{memory_id}").json()["version"] == 2

        stale = a.patch(
            f"/api/tandems/{tandem_id}/memories/{memory_id}",
            json={"expected_version": 1, "title": "Should not overwrite"},
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["current_version"] == 2

        assert c.get(f"/api/tandems/{tandem_id}/memories").status_code == 404
        assert c.get(f"/api/tandems/{tandem_id}/memories/{memory_id}").status_code == 404
        assert c.get(f"/api/tandems/{tandem_id}/memories", params={"q": "blue"}).status_code == 404
        assert (
            c.patch(
                f"/api/tandems/{tandem_id}/memories/{memory_id}",
                json={"expected_version": 2, "title": "Nope"},
            ).status_code
            == 404
        )
        assert c.delete(f"/api/tandems/{tandem_id}/memories/{memory_id}").status_code == 404

        with Session(runtime_engine) as db, db.begin():
            set_current_user_id(db, str(user_c))
            assert db.scalar(select(Memory).where(Memory.id == UUID(memory_id))) is None
            assert (
                db.execute(
                    update(Memory)
                    .where(Memory.id == UUID(memory_id))
                    .values(title="RLS must reject this")
                ).rowcount
                == 0
            )

        filtered = b.get(f"/api/tandems/{tandem_id}/memories", params={"q": "blue", "tag": "NYC"})
        assert filtered.status_code == 200
        assert [item["id"] for item in filtered.json()["items"]] == [memory_id]

        with Session(owner_engine) as db:
            set_current_user_id(db, str(user_a))
            event_types = db.scalars(
                select(ActivityEvent.event_type)
                .where(ActivityEvent.entity_id == UUID(memory_id))
                .order_by(ActivityEvent.created_at, ActivityEvent.id)
            ).all()
        assert {"MemoryCreated", "MemoryUpdated", "ParticipantAdded", "TagAdded"}.issubset(
            set(event_types)
        )

        assert (
            b.delete(
                f"/api/tandems/{tandem_id}/memories/{memory_id}", params={"expected_version": 2}
            ).status_code
            == 403
        )
        assert (
            a.delete(
                f"/api/tandems/{tandem_id}/memories/{memory_id}", params={"expected_version": 2}
            ).status_code
            == 204
        )
        assert a.get(f"/api/tandems/{tandem_id}/memories/{memory_id}").status_code == 404
        with Session(owner_engine) as db:
            set_current_user_id(db, str(user_a))
            assert (
                db.scalar(
                    select(ActivityEvent.event_type).where(
                        ActivityEvent.entity_id == UUID(memory_id),
                        ActivityEvent.event_type == "MemoryDeleted",
                    )
                )
                == "MemoryDeleted"
            )


@pytest.mark.parametrize(
    ("category", "metadata"),
    [
        ("movie", {"provider": "manual", "release_year": 2020}),
        ("place", {"provider": "manual", "name": "The lake"}),
        ("trip", {"destination": "The coast", "end_date": "2026-05-03"}),
        ("activity", {"activity_kind": "Hike"}),
        ("custom", {}),
    ],
)
def test_all_memory_categories_and_validation(memory_clients, category, metadata):
    _, _, _, (client_a, client_b, _) = memory_clients
    with client_a as a, client_b as b:
        tandem_id = _create_shared_tandem(a, b)
        response = a.post(
            f"/api/tandems/{tandem_id}/memories",
            json={
                "category": category,
                "title": f"A {category}",
                "local_date": "2026-05-01",
                "timezone": "UTC",
                "metadata": metadata,
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["category"] == category
        invalid_timezone = a.post(
            f"/api/tandems/{tandem_id}/memories",
            json={
                "category": "custom",
                "title": "Bad timezone",
                "local_date": "2026-05-01",
                "timezone": "Mars/Olympus",
                "metadata": {},
            },
        )
        assert invalid_timezone.status_code == 422
        invalid_rating = a.post(
            f"/api/tandems/{tandem_id}/memories",
            json={
                "category": "custom",
                "title": "Bad rating",
                "local_date": "2026-05-01",
                "timezone": "UTC",
                "rating": 11,
                "metadata": {},
            },
        )
        assert invalid_rating.status_code == 422
        duplicate_tags = a.post(
            f"/api/tandems/{tandem_id}/memories",
            json={
                "category": "custom",
                "title": "Duplicate tags",
                "local_date": "2026-05-01",
                "timezone": "UTC",
                "tags": ["NYC", " nyc "],
                "metadata": {},
            },
        )
        assert duplicate_tags.status_code == 422
