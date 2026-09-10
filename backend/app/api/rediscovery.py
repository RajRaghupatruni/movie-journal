"""Cheap, deterministic rediscovery surfaces built from authorized memories."""
# ruff: noqa: E501

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.memories import _responses
from app.db.session import get_db, set_current_user_id
from app.models import Memory, Tandem, TandemMember, TandemUserPreference, User
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/me/rediscovery", tags=["rediscovery"])


def _eligible(db: Session, user_id: UUID, tandem_id: UUID | None = None):
    statement = (
        select(Memory)
        .join(TandemMember, TandemMember.tandem_id == Memory.tandem_id)
        .outerjoin(
            TandemUserPreference,
            (TandemUserPreference.tandem_id == Memory.tandem_id)
            & (TandemUserPreference.user_id == user_id),
        )
        .where(
            TandemMember.user_id == user_id,
            Memory.deleted_at.is_(None),
            Memory.nostalgia_eligible.is_(True),
            Memory.local_date <= date.today() - timedelta(days=30),
            (
                TandemUserPreference.resurfacing_enabled.is_(True)
                | TandemUserPreference.id.is_(None)
            ),
        )
    )
    if tandem_id:
        statement = statement.where(Memory.tandem_id == tandem_id)
    return statement


def _scope_check(db: Session, user_id: UUID, tandem_id: UUID | None) -> None:
    if (
        tandem_id
        and db.scalar(
            select(Tandem.id)
            .join(TandemMember, TandemMember.tandem_id == Tandem.id)
            .where(Tandem.id == tandem_id, TandemMember.user_id == user_id)
        )
        is None
    ):
        raise HTTPException(status_code=404, detail="Tandem not found")


@router.get("/shuffle")
def memory_shuffle(
    request: Request,
    tandem_id: UUID | None = None,
    seed: str | None = Query(default=None, max_length=80),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    set_current_user_id(db, str(current_user.id))
    _scope_check(db, current_user.id, tandem_id)
    memories = db.scalars(
        _eligible(db, current_user.id, tandem_id).order_by(Memory.local_date, Memory.id)
    ).all()
    if not memories:
        return {"memory": None, "message": "There is nothing old enough to resurface yet."}
    stable_seed = seed or datetime.now(UTC).strftime("%Y-%m-%d-%H")
    index = int.from_bytes(
        sha256(f"{current_user.id}:{tandem_id}:{stable_seed}".encode()).digest()[:8], "big"
    ) % len(memories)
    item = memories[index]
    return {
        "memory": _responses(
            db, [item], getattr(request.app.state, "object_storage", None), current_user.id
        )[0]
    }


@router.get("/year-review")
def year_review(
    request: Request,
    year: int = Query(ge=1900, le=2200),
    tandem_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    set_current_user_id(db, str(current_user.id))
    _scope_check(db, current_user.id, tandem_id)
    memories = db.scalars(
        _eligible(db, current_user.id, tandem_id)
        .where(Memory.local_date >= date(year, 1, 1), Memory.local_date < date(year + 1, 1, 1))
        .order_by(Memory.local_date, Memory.id)
    ).all()
    category_counts: dict[str, int] = {}
    months: set[int] = set()
    for memory in memories:
        category_counts[memory.category] = category_counts.get(memory.category, 0) + 1
        months.add(memory.local_date.month)
    highlights = _responses(
        db, memories[:12], getattr(request.app.state, "object_storage", None), current_user.id
    )
    return {
        "year": year,
        "tandem_id": tandem_id,
        "memory_count": len(memories),
        "months_represented": sorted(months),
        "categories": category_counts,
        "trips": sum(1 for item in memories if item.category == "trip"),
        "movies": sum(1 for item in memories if item.category == "movie"),
        "highlights": highlights,
    }


@router.get("/collections")
def throwback_collections(
    current_user: User = Depends(get_current_user),
    tandem_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    set_current_user_id(db, str(current_user.id))
    _scope_check(db, current_user.id, tandem_id)
    memories = db.scalars(
        _eligible(db, current_user.id, tandem_id).order_by(Memory.local_date, Memory.id)
    ).all()
    collections = []
    by_year: dict[int, list[Memory]] = {}
    for memory in memories:
        by_year.setdefault(memory.local_date.year, []).append(memory)
    for year, items in sorted(by_year.items(), reverse=True):
        if len(items) >= 2:
            collections.append(
                {
                    "key": f"year-{year}",
                    "title": f"Memories from {year}",
                    "memory_ids": [str(item.id) for item in items],
                }
            )
        movies = [item for item in items if item.category == "movie"]
        if len(movies) >= 2:
            collections.append(
                {
                    "key": f"movies-{year}",
                    "title": f"Movies we watched in {year}",
                    "memory_ids": [str(item.id) for item in movies],
                }
            )
    trips = [item for item in memories if item.category == "trip"]
    if len(trips) >= 2:
        collections.append(
            {
                "key": "trips",
                "title": "Trips together",
                "memory_ids": [str(item.id) for item in trips],
            }
        )
    current_month = date.today().month
    month_items = [item for item in memories if item.local_date.month == current_month]
    if len(month_items) >= 2:
        collections.append(
            {
                "key": "this-month",
                "title": "This month in Tandem",
                "memory_ids": [str(item.id) for item in month_items],
            }
        )
    return {"items": collections[:12]}
