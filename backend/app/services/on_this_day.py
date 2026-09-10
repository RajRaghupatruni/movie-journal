"""Timezone-aware anniversary selection for Tandem's On This Day surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Memory, TandemMember, UserNotificationPreference


@dataclass(frozen=True)
class AnniversaryMatch:
    memory: Memory
    years_ago: int
    original_date: date
    anniversary_date: date


def local_date_for(now: datetime, timezone: str) -> date:
    """Return a user's calendar date. Naive clocks are treated as UTC for safety."""

    aware_now = now.replace(tzinfo=UTC) if now.tzinfo is None else now
    return aware_now.astimezone(ZoneInfo(timezone)).date()


def anniversary_date_for(original_date: date, current_year: int) -> date:
    """Apply the explicit Feb 29 policy: Feb 28 in non-leap years."""

    if original_date.month == 2 and original_date.day == 29:
        if _is_leap_year(current_year):
            return date(current_year, 2, 29)
        return date(current_year, 2, 28)
    return date(current_year, original_date.month, original_date.day)


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def build_anniversary_matches(memories: list[Memory], today: date) -> list[AnniversaryMatch]:
    """Pure matching step kept separate so temporal behavior is easy to freeze/test."""

    matches = [
        AnniversaryMatch(
            memory=memory,
            years_ago=today.year - memory.local_date.year,
            original_date=memory.local_date,
            anniversary_date=anniversary_date_for(memory.local_date, today.year),
        )
        for memory in memories
        if memory.nostalgia_eligible
        and memory.local_date < date(today.year, 1, 1)
        and anniversary_date_for(memory.local_date, today.year) == today
    ]
    return sorted(matches, key=lambda item: (item.original_date, str(item.memory.id)), reverse=True)


def _preference(db: Session, user_id):
    return db.scalar(
        select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
    )


def find_anniversaries(
    db: Session,
    *,
    user_id,
    tandem_id,
    now: datetime,
    timezone: str | None = None,
) -> tuple[date, str, list[AnniversaryMatch], Memory | None]:
    """Find all eligible memories and a deterministic fallback for one member."""

    preference = _preference(db, user_id)
    effective_timezone = timezone or (preference.timezone if preference else "UTC")
    today = local_date_for(now, effective_timezone)
    memories = db.scalars(
        select(Memory)
        .join(TandemMember, TandemMember.tandem_id == Memory.tandem_id)
        .where(
            Memory.tandem_id == tandem_id,
            TandemMember.user_id == user_id,
            Memory.nostalgia_eligible.is_(True),
            Memory.local_date < date(today.year, 1, 1),
        )
        .order_by(Memory.local_date.desc(), Memory.id)
    ).all()
    matches = build_anniversary_matches(memories, today)
    if matches:
        return today, effective_timezone, matches, None
    if not memories:
        return today, effective_timezone, [], None
    seed = f"{tandem_id}:{user_id}:{today.isoformat()}".encode()
    fallback = memories[int.from_bytes(sha256(seed).digest()[:8], "big") % len(memories)]
    return today, effective_timezone, [], fallback


def is_currently_eligible(
    db: Session,
    *,
    user_id,
    tandem_id,
    memory_id,
    now: datetime,
    expected_anniversary_year: int | None = None,
    expected_original_date: str | None = None,
) -> bool:
    """Re-check membership, preferences, date and memory state before delivery."""

    preference = _preference(db, user_id)
    if (
        not preference
        or not preference.anniversary_notifications_enabled
        or not preference.anniversary_email_enabled
    ):
        return False
    match_data = find_anniversaries(
        db, user_id=user_id, tandem_id=tandem_id, now=now, timezone=preference.timezone
    )
    return any(
        match.memory.id == memory_id
        and (
            expected_anniversary_year is None
            or match.anniversary_date.year == expected_anniversary_year
        )
        and (
            expected_original_date is None
            or match.original_date.isoformat() == expected_original_date
        )
        for match in match_data[2]
    )


class OnThisDayService:
    """Application-facing service boundary for anniversary selection."""

    @staticmethod
    def find(db: Session, *, user_id, tandem_id, now: datetime, timezone: str | None = None):
        return find_anniversaries(
            db, user_id=user_id, tandem_id=tandem_id, now=now, timezone=timezone
        )

    @staticmethod
    def eligible_before_send(db: Session, *, user_id, tandem_id, memory_id, now: datetime) -> bool:
        return is_currently_eligible(
            db, user_id=user_id, tandem_id=tandem_id, memory_id=memory_id, now=now
        )
