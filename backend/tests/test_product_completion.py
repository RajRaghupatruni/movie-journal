import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.models import AuthSession, Notification, TandemMember, User
from app.services.auth import hash_secret
from app.workers.anniversary import generate_candidates
from tests.helpers import provision_test_user

pytestmark = pytest.mark.integration


@pytest.fixture
def product_environment(postgres_engines, request):
    runtime_engine, owner_engine = postgres_engines
    suffix = re.sub(r"[^a-z0-9]+", "-", request.node.name.casefold()).strip("-")
    records = {
        label: (
            *provision_test_user(
                owner_engine,
                f"product-{label}-{suffix}@example.test",
                label.title(),
            ),
            f"product-{label}-{suffix}@example.test",
        )
        for label in ("alice", "bob", "carol", "dana", "erin")
    }
    runtime_url = os.environ["TEST_DATABASE_URL"]

    def client(label: str) -> TestClient:
        app = create_app(
            Settings(
                _env_file=None,
                app_env="test",
                database_url=runtime_url,
                database_runtime_role=os.getenv("DATABASE_RUNTIME_ROLE", "tandem_app"),
            )
        )
        result = TestClient(app)
        result.cookies.set("tandem_session", records[label][1])
        return result

    return runtime_engine, owner_engine, records, client


def _create_tandem(client: TestClient, name: str) -> str:
    response = client.post("/api/tandems", json={"name": name, "timezone": "UTC"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _invite_and_accept(owner: TestClient, invitee: TestClient, tandem_id: str, email: str) -> str:
    created = owner.post(f"/api/tandems/{tandem_id}/invitations", json={"invited_email": email})
    assert created.status_code == 201, created.text
    reference = created.json()["reference"]
    accepted = invitee.post(f"/api/invitations/{reference}/accept")
    assert accepted.status_code == 200, accepted.text
    return reference


def _email(records, label: str) -> str:
    return records[label][2]


def _create_memory(client: TestClient, tandem_id: str, title: str, local_date: str):
    response = client.post(
        f"/api/tandems/{tandem_id}/memories",
        json={
            "category": "custom",
            "title": title,
            "local_date": local_date,
            "timezone": "UTC",
            "metadata": {},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_membership_roles_leave_removal_and_last_owner_race(product_environment):
    _, owner_engine, records, client = product_environment
    alice_id = records["alice"][0]
    bob_id = records["bob"][0]
    carol_id = records["carol"][0]

    with (
        client("alice") as alice,
        client("bob") as bob,
        client("carol") as carol,
        client("dana") as dana,
    ):
        tandem_id = _create_tandem(alice, "Lifecycle Tandem")
        _invite_and_accept(alice, bob, tandem_id, _email(records, "bob"))
        _invite_and_accept(alice, carol, tandem_id, _email(records, "carol"))
        _invite_and_accept(alice, dana, tandem_id, _email(records, "dana"))

        promoted = alice.post(f"/api/tandems/{tandem_id}/members/{bob_id}/promote")
        assert promoted.status_code == 200
        assert promoted.json()["role"] == "OWNER"
        promoted_again = bob.post(f"/api/tandems/{tandem_id}/members/{carol_id}/promote")
        assert promoted_again.status_code == 200
        assert promoted_again.json()["role"] == "OWNER"

        demoted = alice.post(f"/api/tandems/{tandem_id}/members/{bob_id}/demote")
        assert demoted.status_code == 200
        assert demoted.json()["role"] == "MEMBER"
        assert alice.post(f"/api/tandems/{tandem_id}/members/{bob_id}/demote").status_code == 409

        assert dana.post(f"/api/tandems/{tandem_id}/leave").status_code == 204
        assert dana.get(f"/api/tandems/{tandem_id}").status_code == 404
        assert alice.delete(f"/api/tandems/{tandem_id}/members/{bob_id}").status_code == 204
        assert bob.get(f"/api/tandems/{tandem_id}").status_code == 404

        # Removing the last other owner is safe; removing or demoting the final owner is not.
        assert alice.delete(f"/api/tandems/{tandem_id}/members/{carol_id}").status_code == 204
        assert alice.delete(f"/api/tandems/{tandem_id}/members/{alice_id}").status_code == 409
        assert alice.post(f"/api/tandems/{tandem_id}/members/{alice_id}/demote").status_code == 409
        assert alice.post(f"/api/tandems/{tandem_id}/leave").status_code == 409

        race_tandem_id = _create_tandem(alice, "Owner Race Tandem")
        _invite_and_accept(alice, bob, race_tandem_id, _email(records, "bob"))
        assert (
            alice.post(f"/api/tandems/{race_tandem_id}/members/{bob_id}/promote").status_code == 200
        )

    def leave(label: str):
        with client(label) as current:
            return current.post(f"/api/tandems/{race_tandem_id}/leave").status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(leave, ("alice", "bob")))
    assert sorted(statuses) == [204, 409]

    with Session(owner_engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(TandemMember)
                .where(TandemMember.tandem_id == race_tandem_id, TandemMember.role == "OWNER")
            )
            == 1
        )


def test_invitation_revoke_resend_and_history_use_management_identifiers(product_environment):
    _, _, records, client = product_environment
    with client("alice") as alice, client("erin") as erin:
        tandem_id = _create_tandem(alice, "Invitation Tandem")
        created = alice.post(
            f"/api/tandems/{tandem_id}/invitations",
            json={"invited_email": _email(records, "erin")},
        )
        assert created.status_code == 201, created.text
        original_reference = created.json()["reference"]
        history = alice.get(f"/api/tandems/{tandem_id}/invitations")
        assert history.status_code == 200
        original = history.json()[0]
        assert original["status"] == "PENDING"

        revoked = alice.post(f"/api/tandems/{tandem_id}/invitations/{original['id']}/revoke")
        assert revoked.status_code == 200, revoked.text
        assert revoked.json()["status"] == "REVOKED"

        history = alice.get(f"/api/tandems/{tandem_id}/invitations").json()
        revoked_row = next(item for item in history if item["id"] == original["id"])
        resent = alice.post(f"/api/tandems/{tandem_id}/invitations/{revoked_row['id']}/resend")
        assert resent.status_code == 200, resent.text
        new_reference = resent.json()["reference"]
        assert new_reference != original_reference
        assert erin.get(f"/api/invitations/{new_reference}").status_code == 200
        assert erin.post(f"/api/invitations/{new_reference}/accept").status_code == 200

        statuses = {
            item["status"] for item in alice.get(f"/api/tandems/{tandem_id}/invitations").json()
        }
        assert {"REVOKED", "ACCEPTED"}.issubset(statuses)


def test_account_lifecycle_is_explicit_and_preserves_shared_memory_anonymity(product_environment):
    _, owner_engine, records, client = product_environment
    alice_id = records["alice"][0]
    erin_id = records["erin"][0]

    with client("alice") as alice, client("erin") as erin:
        shared_tandem_id = _create_tandem(alice, "Shared Before Deactivation")
        _invite_and_accept(alice, erin, shared_tandem_id, _email(records, "erin"))
        assert (
            alice.post(f"/api/tandems/{shared_tandem_id}/members/{erin_id}/promote").status_code
            == 200
        )
        _create_memory(alice, shared_tandem_id, "Memory before deactivation", "2024-09-10")

        deactivated = alice.post("/api/me/deactivate", json={"confirmation": "DEACTIVATE"})
        assert deactivated.status_code == 204, deactivated.text
        assert alice.get("/api/me").status_code == 401

    with Session(owner_engine) as db, db.begin():
        assert db.scalar(select(TandemMember).where(TandemMember.user_id == alice_id)) is None
        db.add(
            AuthSession(
                user_id=alice_id,
                token_hash=hash_secret("reactivation-session"),
                expires_at=datetime.now(UTC) + timedelta(days=1),
                reactivation_only=True,
            )
        )

    with client("alice") as alice, client("erin") as erin:
        alice.cookies.set("tandem_session", "reactivation-session")
        assert alice.get("/api/me/reactivation").status_code == 200
        assert alice.get("/api/me").status_code == 401
        assert alice.post("/api/me/reactivate").status_code == 200
        assert alice.get("/api/me").status_code == 200
        assert alice.get("/api/me/tandems").json() == []
        assert alice.get(f"/api/tandems/{shared_tandem_id}").status_code == 404

        solo_tandem_id = _create_tandem(alice, "Solo Blocker")
        assert (
            alice.post("/api/me/deactivate", json={"confirmation": "DEACTIVATE"}).status_code == 409
        )
        assert alice.post("/api/me/delete", json={"confirmation": "DELETE"}).status_code == 409
        assert (
            alice.request(
                "DELETE", f"/api/tandems/{solo_tandem_id}", json={"confirmation": "DELETE"}
            ).status_code
            == 204
        )

        delete_tandem_id = _create_tandem(erin, "Delete Shared Memory")
        _invite_and_accept(erin, alice, delete_tandem_id, _email(records, "alice"))
        memory = _create_memory(alice, delete_tandem_id, "Anonymous after deletion", "2026-01-02")
        deleted = alice.post("/api/me/delete", json={"confirmation": "DELETE"})
        assert deleted.status_code == 204, deleted.text
        visible = erin.get(f"/api/tandems/{delete_tandem_id}/memories/{memory['id']}")
        assert visible.status_code == 200
        assert visible.json()["created_by"] is None
        assert alice.get("/api/me").status_code == 401

        with Session(owner_engine) as db:
            assert db.scalar(select(User).where(User.id == alice_id)) is None
            assert (
                db.scalar(select(User.email).where(User.email == _email(records, "alice"))) is None
            )
        assert (
            erin.request(
                "DELETE", f"/api/tandems/{delete_tandem_id}", json={"confirmation": "DELETE"}
            ).status_code
            == 204
        )
        assert erin.get(f"/api/tandems/{delete_tandem_id}").status_code == 404


def test_notifications_global_views_export_and_removed_tandem_exclusion(product_environment):
    runtime_engine, owner_engine, records, client = product_environment
    alice_id = records["alice"][0]
    carol_id = records["carol"][0]

    with client("alice") as alice, client("bob") as bob, client("carol") as carol:
        first_id = _create_tandem(alice, "Global One")
        _invite_and_accept(alice, bob, first_id, _email(records, "bob"))
        first_memory = _create_memory(alice, first_id, "First global memory", "2024-09-10")

        second_id = _create_tandem(alice, "Global Two")
        _invite_and_accept(alice, carol, second_id, _email(records, "carol"))
        second_memory = _create_memory(alice, second_id, "Second global memory", "2025-09-10")

        global_items = alice.get("/api/me/memories").json()["items"]
        assert {item["id"] for item in global_items} >= {first_memory["id"], second_memory["id"]}
        assert {item["tandem_name"] for item in global_items} >= {"Global One", "Global Two"}
        calendar = alice.get(
            "/api/me/calendar", params={"from_date": "2024-01-01", "to_date": "2025-12-31"}
        )
        assert {item["id"] for item in calendar.json()["items"]} >= {
            first_memory["id"],
            second_memory["id"],
        }
        today = alice.get("/api/me/on-this-day", params={"now": "2026-09-10T12:00:00Z"})
        assert {item["memory"]["tandem_name"] for item in today.json()["anniversaries"]} >= {
            "Global One",
            "Global Two",
        }

        assert alice.get("/api/me/export").status_code == 200
        exported = alice.get("/api/me/export").json()
        assert exported["format"] == "tandem-export-v1"
        assert {item["id"] for item in exported["memories"]} >= {
            first_memory["id"],
            second_memory["id"],
        }
        assert bob.get(f"/api/tandems/{second_id}").status_code == 404
        assert second_id not in {
            item["tandem_id"] for item in bob.get("/api/me/export").json()["memories"]
        }

        # B receives an invitation/acceptance notification, while A receives the join event.
        b_notifications = bob.get("/api/me/notifications").json()
        assert b_notifications["items"]
        b_item = b_notifications["items"][0]
        a_notifications = alice.get("/api/me/notifications").json()
        assert a_notifications["items"]
        a_item = a_notifications["items"][0]
        assert all(item["id"] != a_item["id"] for item in b_notifications["items"])
        assert bob.post(f"/api/me/notifications/{a_item['id']}/read").status_code == 404
        assert bob.post(f"/api/me/notifications/{b_item['id']}/read").status_code == 200
        assert bob.post("/api/me/notifications/read-all").status_code == 204
        assert bob.get("/api/me/notifications").json()["unread_count"] == 0

        assert alice.post(f"/api/tandems/{second_id}/members/{carol_id}/promote").status_code == 200
        assert alice.post(f"/api/tandems/{second_id}/leave").status_code == 204
        remaining = alice.get("/api/me/memories").json()["items"]
        assert second_memory["id"] not in {item["id"] for item in remaining}

    with Session(owner_engine) as db, db.begin():
        preference = db.execute(select(User).where(User.id == alice_id)).scalar_one()
        db.execute(
            text(
                "INSERT INTO user_notification_preferences "
                "(id, user_id, timezone, anniversary_notifications_enabled, "
                "anniversary_email_enabled, notification_hour) "
                "VALUES (gen_random_uuid(), :user_id, 'UTC', true, true, 9) "
                "ON CONFLICT (user_id) DO UPDATE SET timezone='UTC', "
                "anniversary_notifications_enabled=true, anniversary_email_enabled=true, "
                "notification_hour=9"
            ),
            {"user_id": str(preference.id)},
        )

    with Session(runtime_engine) as db:
        now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
        first = generate_candidates(db, now)
        second = generate_candidates(db, now)
        assert first == 1
        assert second == 0

    with Session(owner_engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.user_id == alice_id,
                    Notification.type == "on_this_day",
                    Notification.memory_id == first_memory["id"],
                )
            )
            == 1
        )
