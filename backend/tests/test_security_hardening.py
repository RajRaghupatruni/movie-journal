import pytest
from pydantic import ValidationError

from app.core.rate_limit import InProcessRateLimitMiddleware
from app.schemas.auth import AccountAction, InvitationCreate, TandemCreate, TandemUpdate
from app.schemas.memory import MemoryCreate, MemoryPatch
from app.services.media_processing import InvalidImage, process_image


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (AccountAction, {"confirmation": "DELETE", "is_owner": True}),
        (InvitationCreate, {"invited_email": "victim@example.test", "user_id": "attacker"}),
        (TandemCreate, {"name": "private", "timezone": "UTC", "created_by": "victim"}),
        (TandemUpdate, {"name": "private", "owner_id": "attacker"}),
        (
            MemoryCreate,
            {
                "category": "custom",
                "title": "private",
                "local_date": "2026-09-10",
                "timezone": "UTC",
                "metadata": {},
                "tandem_id": "other-tandem",
            },
        ),
        (MemoryPatch, {"expected_version": 1, "created_by": "victim"}),
    ],
)
def test_sensitive_mutation_schemas_forbid_protected_properties(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_rate_limiter_key_map_stays_bounded_under_rotating_clients():
    limiter = InProcessRateLimitMiddleware(object())
    for index in range(5000):
        assert limiter._allowed(f"provider:rotating-client-{index}", 60, 60)
    assert len(limiter._events) <= 4096


def test_image_dimensions_are_rejected_before_decode(monkeypatch):
    class HeaderOnlyImage:
        size = (100_000, 100_000)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def verify(self):
            raise AssertionError("oversized image should be rejected before verify/decode")

    monkeypatch.setattr(
        "app.services.media_processing.Image.open", lambda *_args: HeaderOnlyImage()
    )
    with pytest.raises(InvalidImage, match="dimensions"):
        process_image(b"header", "image/jpeg", 10 * 1024 * 1024, 2400)
