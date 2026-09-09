import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import set_current_user_id
from app.main import create_app
from app.models import Invitation, Tandem
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
