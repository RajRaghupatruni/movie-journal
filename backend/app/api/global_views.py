import json
from datetime import UTC, date, datetime
from hashlib import sha256
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.memories import _responses
from app.db.session import get_db, set_current_user_id
from app.models import (
    Memory,
    MemoryMedia,
    MemoryParticipant,
    MemoryTag,
    Tag,
    Tandem,
    TandemMember,
    User,
    UserNotificationPreference,
)
from app.schemas.memory import MemoryCategory, MemoryListResponse
from app.schemas.nostalgia import AnniversaryResponse, OnThisDayResponse
from app.services.auth import get_current_user
from app.services.on_this_day import build_anniversary_matches, local_date_for

router = APIRouter(prefix="/api/me", tags=["global views"])


def _query(user_id, *, tandem_id=None, category=None, year=None, q=None):
    statement = (
        select(Memory)
        .join(TandemMember, TandemMember.tandem_id == Memory.tandem_id)
        .where(TandemMember.user_id == user_id)
        .order_by(Memory.local_date.desc(), Memory.id.desc())
    )
    if tandem_id:
        statement = statement.where(Memory.tandem_id == tandem_id)
    if category:
        statement = statement.where(Memory.category == category.value)
    if year:
        statement = statement.where(
            Memory.local_date >= date(year, 1, 1), Memory.local_date < date(year + 1, 1, 1)
        )
    if q:
        statement = statement.where(Memory.search_vector.match(q))
    return statement


@router.get("/memories", response_model=MemoryListResponse)
@router.get("/timeline", response_model=MemoryListResponse)
@router.get("/calendar", response_model=MemoryListResponse)
def global_memories(
    request: Request,
    tandem_id: UUID | None = None,
    category: MemoryCategory | None = None,
    year: int | None = Query(default=None, ge=1900, le=2200),
    q: str | None = Query(default=None, max_length=120),
    from_date: date | None = None,
    to_date: date | None = None,
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    set_current_user_id(db, str(current_user.id))
    statement = _query(current_user.id, tandem_id=tandem_id, category=category, year=year, q=q)
    if from_date:
        statement = statement.where(Memory.local_date >= from_date)
    if to_date:
        statement = statement.where(Memory.local_date <= to_date)
    memories = db.scalars(statement.offset(offset).limit(limit + 1)).all()
    has_more = len(memories) > limit
    items = memories[:limit]
    return MemoryListResponse(
        items=_responses(db, items, getattr(request.app.state, "object_storage", None)),
        offset=offset,
        limit=limit,
        next_offset=offset + limit if has_more else None,
    )


@router.get("/on-this-day", response_model=OnThisDayResponse)
def global_on_this_day(
    request: Request,
    now: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    set_current_user_id(db, str(current_user.id))
    preference = db.scalar(
        select(UserNotificationPreference).where(
            UserNotificationPreference.user_id == current_user.id
        )
    )
    timezone = preference.timezone if preference else "UTC"
    effective_now = now or datetime.now(UTC)
    today = local_date_for(effective_now, timezone)
    memories = db.scalars(
        select(Memory)
        .join(TandemMember, TandemMember.tandem_id == Memory.tandem_id)
        .where(
            TandemMember.user_id == current_user.id,
            Memory.nostalgia_eligible.is_(True),
            Memory.local_date < date(today.year, 1, 1),
        )
        .order_by(Memory.local_date.desc(), Memory.id)
    ).all()
    matches = build_anniversary_matches(memories, today)
    fallback = None
    if not matches and memories:
        seed = f"global:{current_user.id}:{today.isoformat()}".encode()
        fallback = memories[int.from_bytes(sha256(seed).digest()[:8], "big") % len(memories)]
    all_items = [match.memory for match in matches] + ([fallback] if fallback else [])
    response_map = {
        item.id: value
        for item, value in zip(
            all_items, _responses(db, all_items, getattr(request.app.state, "object_storage", None))
        )
    }
    return OnThisDayResponse(
        today=today,
        timezone=timezone,
        anniversaries=[
            AnniversaryResponse(
                memory=response_map[m.memory.id],
                years_ago=m.years_ago,
                original_date=m.original_date,
                anniversary_date=m.anniversary_date,
            )
            for m in matches
        ],
        fallback=response_map[fallback.id] if fallback else None,
    )


@router.get("/export")
def export_account(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download bounded JSON; media bytes remain private in object storage."""
    set_current_user_id(db, str(current_user.id))
    tandem_ids = db.scalars(
        select(TandemMember.tandem_id).where(TandemMember.user_id == current_user.id)
    ).all()
    tandem_rows = (
        db.scalars(select(Tandem).where(Tandem.id.in_(tandem_ids))).all() if tandem_ids else []
    )
    memories = (
        db.scalars(
            select(Memory)
            .where(Memory.tandem_id.in_(tandem_ids))
            .order_by(Memory.local_date, Memory.id)
        ).all()
        if tandem_ids
        else []
    )
    media = (
        db.scalars(select(MemoryMedia).where(MemoryMedia.tandem_id.in_(tandem_ids))).all()
        if tandem_ids
        else []
    )
    participant_rows = (
        db.execute(
            select(
                MemoryParticipant.memory_id,
                User.id,
                User.display_name,
            )
            .join(User, User.id == MemoryParticipant.user_id)
            .join(Memory, Memory.id == MemoryParticipant.memory_id)
            .where(Memory.tandem_id.in_(tandem_ids))
        ).all()
        if tandem_ids
        else []
    )
    tag_rows = (
        db.execute(
            select(MemoryTag.memory_id, Tag.name)
            .join(Tag, Tag.id == MemoryTag.tag_id)
            .join(Memory, Memory.id == MemoryTag.memory_id)
            .where(Memory.tandem_id.in_(tandem_ids))
            .order_by(Tag.name)
        ).all()
        if tandem_ids
        else []
    )
    participants_by_memory: dict[UUID, list[dict]] = {}
    for memory_id, user_id, display_name in participant_rows:
        participants_by_memory.setdefault(memory_id, []).append(
            {
                "user_id": str(user_id),
                "display_name": display_name,
            }
        )
    tags_by_memory: dict[UUID, list[str]] = {}
    for memory_id, name in tag_rows:
        tags_by_memory.setdefault(memory_id, []).append(name)
    preference = db.scalar(
        select(UserNotificationPreference).where(
            UserNotificationPreference.user_id == current_user.id
        )
    )
    payload = {
        "format": "tandem-export-v1",
        "exported_at": datetime.now(UTC).isoformat(),
        "account": {
            "id": str(current_user.id),
            "display_name": current_user.display_name,
            "email": current_user.email,
            "timezone": preference.timezone if preference else "UTC",
        },
        "tandems": [
            {
                "id": str(t.id),
                "name": t.name,
                "timezone": t.timezone,
                "created_at": t.created_at.isoformat(),
            }
            for t in tandem_rows
        ],
        "memberships": [
            {"tandem_id": str(tandem_id), "user_id": str(current_user.id)}
            for tandem_id in tandem_ids
        ],
        "memories": [
            {
                "id": str(m.id),
                "tandem_id": str(m.tandem_id),
                "title": m.title,
                "category": m.category,
                "local_date": m.local_date.isoformat(),
                "occurred_at": m.occurred_at.isoformat() if m.occurred_at else None,
                "timezone": m.timezone,
                "rating": m.rating,
                "notes": m.notes,
                "metadata": m.memory_metadata,
                "tags": tags_by_memory.get(m.id, []),
                "participants": participants_by_memory.get(m.id, []),
                "created_by": str(m.created_by) if m.created_by else None,
            }
            for m in memories
        ],
        "media": [
            {
                "id": str(m.id),
                "memory_id": str(m.memory_id),
                "content_type": m.content_type,
                "byte_size": m.byte_size,
                "width": m.width,
                "height": m.height,
                "original_filename": m.original_filename,
            }
            for m in media
        ],
        "media_semantics": (
            "Private media bytes remain in storage; this export contains authorized media metadata."
        ),
    }
    return Response(
        content=json.dumps(payload),
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="tandem-export.json"',
            "Cache-Control": "no-store",
        },
    )
