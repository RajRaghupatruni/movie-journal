"""Small persistent notification service; delivery is separate from the email outbox."""

import json
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import Notification, Tandem, User


def create_notification(
    db: Session,
    *,
    user_id: UUID,
    notification_type: str,
    actor_user_id: UUID | None = None,
    tandem_id: UUID | None = None,
    memory_id: UUID | None = None,
    invitation_id: UUID | None = None,
    payload: dict | None = None,
    dedupe_key: str,
) -> None:
    """Call the constrained database helper; no arbitrary notification insert endpoint exists."""

    db.execute(
        text(
            "SELECT app.insert_notification(:user_id, :type, :actor, :tandem, :memory, "
            ":invite, CAST(:payload AS jsonb), :dedupe)"
        ),
        {
            "user_id": str(user_id),
            "type": notification_type,
            "actor": str(actor_user_id) if actor_user_id else None,
            "tandem": str(tandem_id) if tandem_id else None,
            "memory": str(memory_id) if memory_id else None,
            "invite": str(invitation_id) if invitation_id else None,
            "payload": json.dumps(payload or {}),
            "dedupe": dedupe_key,
        },
    )


def cancel_user_tandem_notifications(db: Session, user_id: UUID, tandem_id: UUID) -> None:
    db.execute(
        text("SELECT app.cancel_user_tandem_notifications(:user_id, :tandem_id)"),
        {
            "user_id": str(user_id),
            "tandem_id": str(tandem_id),
        },
    )


def notification_rows(db: Session, user_id: UUID, *, limit: int = 50) -> tuple[list, int]:
    rows = db.execute(
        select(Notification, User.display_name, Tandem.name)
        .outerjoin(User, User.id == Notification.actor_user_id)
        .outerjoin(Tandem, Tandem.id == Notification.tandem_id)
        .where(Notification.user_id == user_id, Notification.archived_at.is_(None))
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
    ).all()
    unread = int(
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.archived_at.is_(None),
                Notification.read_at.is_(None),
            )
        )
        or 0
    )
    return [
        (notification, actor_name, tandem_name) for notification, actor_name, tandem_name in rows
    ], unread
