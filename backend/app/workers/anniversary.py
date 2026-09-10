"""Generate in-app anniversary notifications and optionally deliver email."""

from __future__ import annotations

import argparse
import html
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import Settings, load_settings
from app.db.session import create_db_engine
from app.integrations.resend import EmailDeliveryError, ResendEmailAdapter
from app.models import (
    NotificationOutbox,
    TandemMember,
    User,
    UserNotificationPreference,
)
from app.services.notifications import create_notification
from app.services.on_this_day import find_anniversaries, is_currently_eligible

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
PROCESSING_LEASE = timedelta(minutes=15)


def idempotency_key_for(tandem_id, user_id, memory_id, anniversary_year: int) -> str:
    return f"anniversary:{tandem_id}:{user_id}:{memory_id}:{anniversary_year}:email"


def retry_at(now: datetime, attempts: int) -> datetime:
    return now + timedelta(minutes=5 * (2 ** (attempts - 1)))


def as_utc(now: datetime) -> datetime:
    return (now.replace(tzinfo=UTC) if now.tzinfo is None else now).astimezone(UTC)


def _worker_mode(db: Session) -> None:
    # The migration-created RLS policy exposes only this process's explicit
    # worker transaction context. The API runtime role has no outbox grants.
    db.execute(text("SELECT set_config('app.worker_mode', 'true', false)"))


def generate_candidates(db: Session, now: datetime, *, email_delivery_enabled: bool = False) -> int:
    _worker_mode(db)
    rows = db.execute(
        select(TandemMember.tandem_id, TandemMember.user_id)
        .join(User, User.id == TandemMember.user_id)
        .order_by(TandemMember.tandem_id, TandemMember.user_id)
    ).all()
    created = 0
    for tandem_id, user_id in rows:
        preference = db.scalar(
            select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
        )
        if preference is None or not preference.anniversary_notifications_enabled:
            continue
        if now.astimezone(ZoneInfo(preference.timezone)).hour < preference.notification_hour:
            continue
        _, _, matches, _ = find_anniversaries(
            db, user_id=user_id, tandem_id=tandem_id, now=now, timezone=preference.timezone
        )
        for match in matches:
            create_notification(
                db,
                user_id=user_id,
                notification_type="on_this_day",
                tandem_id=tandem_id,
                memory_id=match.memory.id,
                payload={
                    "years_ago": match.years_ago,
                    "original_date": match.original_date.isoformat(),
                    "anniversary_date": match.anniversary_date.isoformat(),
                },
                dedupe_key=(
                    f"anniversary:{tandem_id}:{user_id}:{match.memory.id}:"
                    f"{match.anniversary_date.year}:in_app"
                ),
            )
            if not email_delivery_enabled or not preference.anniversary_email_enabled:
                continue
            key = idempotency_key_for(
                tandem_id, user_id, match.memory.id, match.anniversary_date.year
            )
            result = db.execute(
                pg_insert(NotificationOutbox)
                .values(
                    event_type="AnniversaryEmailRequested",
                    user_id=user_id,
                    tandem_id=tandem_id,
                    memory_id=match.memory.id,
                    anniversary_year=match.anniversary_date.year,
                    channel="email",
                    payload={
                        "version": 1,
                        "years_ago": match.years_ago,
                        "original_date": match.original_date.isoformat(),
                        "anniversary_date": match.anniversary_date.isoformat(),
                    },
                    idempotency_key=key,
                )
                .on_conflict_do_nothing(index_elements=["idempotency_key"])
                .returning(NotificationOutbox.id)
            )
            created += int(result.scalar_one_or_none() is not None)
    db.commit()
    return created


def _copy_for(years_ago: int) -> tuple[str, str]:
    age = "1 year" if years_ago == 1 else f"{years_ago} years"
    text_copy = f"A memory from {age} ago is waiting for you in Tandem."
    return "A memory is waiting in Tandem", text_copy


def _email_markup(settings: Settings, years_ago: int) -> tuple[str, str, str]:
    subject, text_copy = _copy_for(years_ago)
    url = html.escape(settings.frontend_url, quote=True)
    body = html.escape(text_copy)
    markup = (
        '<div style="background:#f7f3ed;padding:40px 20px;font-family:Georgia,serif;color:#2b2424">'
        '<div style="max-width:520px;margin:auto;background:#fbf9f5;padding:36px;'
        'border:1px solid #e5ddd3">'
        '<p style="color:#803e53;letter-spacing:.16em;text-transform:uppercase;'
        'font:11px sans-serif">tandem</p>'
        f'<h1 style="font-weight:500">{body}</h1>'
        f'<p><a href="{url}" style="color:#803e53">Open Tandem</a></p>'
        '<p style="color:#6f6560;font:13px sans-serif">Private by default. Your memory '
        "stays in Tandem.</p>"
        "</div></div>"
    )
    return subject, text_copy, markup


def _revalidate(db: Session, item: NotificationOutbox, now: datetime) -> bool:
    return is_currently_eligible(
        db,
        user_id=item.user_id,
        tandem_id=item.tandem_id,
        memory_id=item.memory_id,
        now=now,
        expected_anniversary_year=item.anniversary_year,
        expected_original_date=item.payload.get("original_date"),
    )


def deliver_pending(
    db: Session,
    *,
    now: datetime,
    adapter,
    settings: Settings,
    limit: int = 100,
) -> dict[str, int]:
    if not settings.email_delivery_enabled:
        return {"sent": 0, "cancelled": 0, "retrying": 0, "failed": 0}
    _worker_mode(db)
    db.execute(
        update(NotificationOutbox)
        .where(
            NotificationOutbox.status == "PROCESSING",
            NotificationOutbox.processing_started_at < now - PROCESSING_LEASE,
        )
        .values(status="PENDING", processing_started_at=None, next_attempt_at=now)
    )
    db.commit()
    counts = {"sent": 0, "cancelled": 0, "retrying": 0, "failed": 0}
    for _ in range(limit):
        item = db.scalar(
            select(NotificationOutbox)
            .where(
                NotificationOutbox.status == "PENDING",
                NotificationOutbox.next_attempt_at <= now,
            )
            .order_by(NotificationOutbox.created_at, NotificationOutbox.id)
            .with_for_update(skip_locked=True)
        )
        if item is None:
            break
        item.status = "PROCESSING"
        item.attempts += 1
        item.processing_started_at = now
        db.commit()
        if not _revalidate(db, item, now):
            item.status = "CANCELLED"
            item.processed_at = now
            item.last_error = "Eligibility changed before delivery"
            db.commit()
            counts["cancelled"] += 1
            continue
        user = db.get(User, item.user_id)
        years_ago = int(item.payload.get("years_ago", 1))
        subject, text_copy, markup = _email_markup(settings, years_ago)
        try:
            adapter.send(recipient=user.email, subject=subject, html=markup, text=text_copy)
        except EmailDeliveryError as exc:
            item.last_error = str(exc)
            if exc.transient and item.attempts < MAX_ATTEMPTS:
                item.status = "PENDING"
                item.next_attempt_at = retry_at(now, item.attempts)
                counts["retrying"] += 1
            else:
                item.status = "FAILED"
                item.processed_at = now
                counts["failed"] += 1
            db.commit()
            continue
        item.status = "SENT"
        item.processed_at = now
        item.processing_started_at = None
        item.last_error = None
        db.commit()
        counts["sent"] += 1
    return counts


def run_worker(settings: Settings, *, now: datetime | None = None, adapter=None) -> dict[str, int]:
    effective_now = as_utc(now or datetime.now(UTC))
    # The scheduler is an application process, not a schema owner. It uses the same dedicated
    # non-bypass-RLS role as the web service and opts into only the migration-created worker
    # policies through the transaction/session setting above.
    engine = create_db_engine(settings)
    try:
        with Session(engine) as db:
            generate_candidates(
                db,
                effective_now,
                email_delivery_enabled=settings.email_delivery_enabled,
            )
            if not settings.email_delivery_enabled:
                return {"sent": 0, "cancelled": 0, "retrying": 0, "failed": 0}
            return deliver_pending(
                db,
                now=effective_now,
                adapter=adapter or ResendEmailAdapter(settings),
                settings=settings,
            )
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Tandem anniversary notifications and optionally send email"
    )
    parser.add_argument("--now", help="UTC ISO timestamp for deterministic runs/tests")
    args = parser.parse_args()
    now = as_utc(datetime.fromisoformat(args.now)) if args.now else None
    result = run_worker(load_settings(service_mode="worker"), now=now)
    print(result)


if __name__ == "__main__":
    main()
