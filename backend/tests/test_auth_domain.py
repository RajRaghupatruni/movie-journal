import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.constants import MAX_TANDEM_MEMBERS
from app.db.session import set_current_user_id
from app.main import create_app
from app.models import Invitation, Tandem, TandemMember
from app.services.auth import hash_secret, new_secret
from tests.helpers import provision_test_user

pytestmark = pytest.mark.integration


@pytest.fixture
def users_and_clients(postgres_engines):
    runtime_engine, owner_engine = postgres_engines
    user_a, session_a = provision_test_user(owner_engine, "a@example.test", "User A")
    user_b, session_b = provision_test_user(owner_engine, "b@example.test", "User B")
    user_c, session_c = provision_test_user(owner_engine, "c@example.test", "User C")
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


@pytest.fixture
def capacity_environment(postgres_engines):
    _, owner_engine = postgres_engines
    records = [
        provision_test_user(owner_engine, f"capacity-{index}@example.test", f"Capacity {index}")
        for index in range(6)
    ]
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

    return owner_engine, records, client


def _seed_pending_invitation(owner_engine, tandem_id, invited_by, invited_email):
    reference = new_secret()
    with Session(owner_engine) as db, db.begin():
        db.add(
            Invitation(
                tandem_id=tandem_id,
                invited_email=invited_email,
                invited_by=invited_by,
                token_hash=hash_secret(reference),
                status="PENDING",
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
    return reference


def test_invites_members_and_isolates_tandem_rows(users_and_clients):
    runtime_engine, owner_engine, (user_a, user_b, user_c), (client_a, client_b, client_c) = (
        users_and_clients
    )
    with client_a as a, client_b as b, client_c as c:
        assert a.get("/api/me").json()["id"] == str(user_a)
        created = a.post("/api/tandems", json={"name": "A and A", "timezone": "America/Chicago"})
        assert created.status_code == 201
        tandem_id = created.json()["id"]
        assert a.get(f"/api/tandems/{tandem_id}").status_code == 200
        assert b.get(f"/api/tandems/{tandem_id}").status_code == 404
        assert c.get(f"/api/tandems/{tandem_id}").status_code == 404

        invitation = a.post(
            f"/api/tandems/{tandem_id}/invitations",
            json={"invited_email": "b@example.test"},
        )
        assert invitation.status_code == 201
        reference = invitation.json()["reference"]
        assert "token_hash" not in invitation.text
        assert b.get(f"/api/invitations/{reference}").status_code == 200
        assert c.post(f"/api/invitations/{reference}/accept").status_code == 403
        assert b.post(f"/api/invitations/{reference}/accept").status_code == 200
        assert b.get(f"/api/tandems/{tandem_id}").status_code == 200
        assert b.post(f"/api/invitations/{reference}/accept").status_code == 409
        assert c.get(f"/api/tandems/{tandem_id}/members").status_code == 404
        assert c.patch(f"/api/tandems/{tandem_id}", json={"name": "stolen"}).status_code == 404
        assert b.patch(f"/api/tandems/{tandem_id}", json={"name": "not owner"}).status_code == 403

        duplicate_one = a.post(
            f"/api/tandems/{tandem_id}/invitations",
            json={"invited_email": "c@example.test"},
        )
        assert duplicate_one.status_code == 201
        assert (
            a.post(
                f"/api/tandems/{tandem_id}/invitations",
                json={"invited_email": "C@EXAMPLE.TEST"},
            ).status_code
            == 409
        )
        duplicate_reference = duplicate_one.json()["reference"]
        assert c.post(f"/api/invitations/{duplicate_reference}/decline").status_code == 200
        assert c.post(f"/api/invitations/{duplicate_reference}/accept").status_code == 409

        revoked = a.post(
            f"/api/tandems/{tandem_id}/invitations",
            json={"invited_email": "c@example.test"},
        )
        assert revoked.status_code == 201
        revoked_reference = revoked.json()["reference"]
        assert (
            a.post(f"/api/tandems/{tandem_id}/invitations/{revoked_reference}/revoke").status_code
            == 200
        )
        assert c.post(f"/api/invitations/{revoked_reference}/accept").status_code == 409

        expired = a.post(
            f"/api/tandems/{tandem_id}/invitations",
            json={"invited_email": "c@example.test"},
        )
        assert expired.status_code == 201
        expired_reference = expired.json()["reference"]
        with Session(owner_engine) as db, db.begin():
            db.execute(
                update(Invitation)
                .where(Invitation.token_hash.is_not(None))
                .where(Invitation.invited_email == "c@example.test")
                .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
            )
        expired_response = c.post(f"/api/invitations/{expired_reference}/accept")
        assert expired_response.status_code == 410, expired_response.text

        assert a.post(f"/api/tandems/{tandem_id}/leave").status_code == 409
        assert a.post("/auth/logout").status_code == 204
        assert a.get("/api/me").status_code == 401

    with Session(runtime_engine) as db, db.begin():
        set_current_user_id(db, str(user_c))
        visible = db.scalars(select(Tandem)).all()
        assert all(tandem.id != UUID(tandem_id) for tandem in visible)
        assert (
            db.scalar(
                text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
            )
            is False
        )


def test_tandem_member_limit_and_acceptance_race(capacity_environment):
    owner_engine, records, client = capacity_environment
    users = [record[0] for record in records]
    sessions = [record[1] for record in records]
    emails = [f"capacity-{index}@example.test" for index in range(6)]

    with client(sessions[0]) as owner, client(sessions[1]) as member_one:
        tandem = owner.post("/api/tandems", json={"name": "The Sunday Table", "timezone": "UTC"})
        assert tandem.status_code == 201, tandem.text
        tandem_id = tandem.json()["id"]

        for index in (1, 2, 3):
            invitation = owner.post(
                f"/api/tandems/{tandem_id}/invitations",
                json={"invited_email": emails[index]},
            )
            assert invitation.status_code == 201, invitation.text
            with client(sessions[index]) as invitee:
                accepted = invitee.post(f"/api/invitations/{invitation.json()['reference']}/accept")
            assert accepted.status_code == 200, accepted.text

        fifth_reference = _seed_pending_invitation(owner_engine, tandem_id, users[0], emails[4])
        sixth_reference = _seed_pending_invitation(owner_engine, tandem_id, users[0], emails[5])
        with client(sessions[4]) as fifth_member:
            accepted = fifth_member.post(f"/api/invitations/{fifth_reference}/accept")
        assert accepted.status_code == 200, accepted.text
        with client(sessions[5]) as sixth_member:
            rejected = sixth_member.post(f"/api/invitations/{sixth_reference}/accept")
        assert rejected.status_code == 409
        assert "full" in rejected.json()["detail"]

        members = owner.get(f"/api/tandems/{tandem_id}/members")
        assert members.status_code == 200
        assert len(members.json()) == MAX_TANDEM_MEMBERS
        full_invitation = owner.post(
            f"/api/tandems/{tandem_id}/invitations",
            json={"invited_email": "capacity-new@example.test"},
        )
        assert full_invitation.status_code == 409
        assert "full" in full_invitation.json()["detail"]
        renamed = owner.patch(f"/api/tandems/{tandem_id}", json={"name": "The Sunday Table"})
        assert renamed.status_code == 200
        forbidden = member_one.patch(f"/api/tandems/{tandem_id}", json={"name": "Nope"})
        assert forbidden.status_code == 403

        memory = owner.post(
            f"/api/tandems/{tandem_id}/memories",
            json={
                "category": "custom",
                "title": "The long table",
                "local_date": "2026-09-09",
                "timezone": "UTC",
                "participant_ids": [str(users[1]), str(users[3]), str(users[4])],
                "metadata": {},
            },
        )
        assert memory.status_code == 201, memory.text
        assert {participant["user_id"] for participant in memory.json()["participants"]} == {
            str(users[1]),
            str(users[3]),
            str(users[4]),
        }

    race_tandem = client(sessions[0])
    with race_tandem as owner:
        created = owner.post("/api/tandems", json={"name": "Race Tandem", "timezone": "UTC"})
        assert created.status_code == 201, created.text
        tandem_id = created.json()["id"]
        for index in (1, 2, 3):
            invitation = owner.post(
                f"/api/tandems/{tandem_id}/invitations",
                json={"invited_email": emails[index]},
            )
            assert invitation.status_code == 201, invitation.text
            with client(sessions[index]) as invitee:
                assert (
                    invitee.post(
                        f"/api/invitations/{invitation.json()['reference']}/accept"
                    ).status_code
                    == 200
                )

        references = [
            _seed_pending_invitation(owner_engine, tandem_id, users[0], emails[index])
            for index in (4, 5)
        ]
        reserved_invitation = owner.post(
            f"/api/tandems/{tandem_id}/invitations",
            json={"invited_email": "capacity-reserved@example.test"},
        )
        assert reserved_invitation.status_code == 409

    def accept(index):
        with client(sessions[index]) as invitee:
            return invitee.post(f"/api/invitations/{references[index - 4]}/accept")

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(accept, (4, 5)))
    assert sorted(response.status_code for response in responses) == [200, 409]

    with Session(owner_engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(TandemMember)
                .where(TandemMember.tandem_id == tandem_id)
            )
            == MAX_TANDEM_MEMBERS
        )
