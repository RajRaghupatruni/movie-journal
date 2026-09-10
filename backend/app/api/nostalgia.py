from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.memories import _responses
from app.db.session import get_db
from app.models import User
from app.schemas.nostalgia import AnniversaryResponse, OnThisDayResponse
from app.services.auth import get_current_user
from app.services.authorization import TandemAccess, require_tandem_member
from app.services.on_this_day import find_anniversaries

router = APIRouter(prefix="/tandems", tags=["nostalgia"])


@router.get("/{tandem_id}/on-this-day", response_model=OnThisDayResponse)
def on_this_day(
    request: Request,
    tandem_id: UUID,
    now: datetime | None = Query(default=None),
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OnThisDayResponse:
    effective_now = now or datetime.now(UTC)
    today, timezone, matches, fallback = find_anniversaries(
        db,
        user_id=current_user.id,
        tandem_id=access.tandem.id,
        now=effective_now,
    )
    storage = getattr(request.app.state, "object_storage", None)
    memories = [match.memory for match in matches]
    if fallback is not None:
        memories.append(fallback)
    responses = {item.id: value for item, value in zip(memories, _responses(db, memories, storage))}
    return OnThisDayResponse(
        today=today,
        timezone=timezone,
        anniversaries=[
            AnniversaryResponse(
                memory=responses[match.memory.id],
                years_ago=match.years_ago,
                original_date=match.original_date,
                anniversary_date=match.anniversary_date,
            )
            for match in matches
        ],
        fallback=responses[fallback.id] if fallback is not None else None,
    )
