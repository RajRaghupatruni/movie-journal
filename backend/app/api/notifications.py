from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.db.session import get_db, set_current_user_id
from app.models import Notification, User
from app.schemas.auth import NotificationListResponse, NotificationResponse
from app.services.auth import get_current_user
from app.services.notifications import notification_rows

router = APIRouter(prefix="/api/me/notifications", tags=["notifications"])


def _response(item, actor_name, tandem_name):
    return NotificationResponse(
        id=item.id,
        type=item.type,
        actor_name=actor_name,
        tandem_id=item.tandem_id,
        tandem_name=tandem_name,
        memory_id=item.memory_id,
        payload=item.payload,
        created_at=item.created_at,
        read_at=item.read_at,
        archived_at=item.archived_at,
    )


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    set_current_user_id(db, str(current_user.id))
    rows, unread = notification_rows(db, current_user.id, limit=limit)
    return NotificationListResponse(items=[_response(*row) for row in rows], unread_count=unread)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    set_current_user_id(db, str(current_user.id))
    db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == current_user.id)
        .values(read_at=func.now())
    )
    db.commit()
    set_current_user_id(db, str(current_user.id))
    rows, _ = notification_rows(db, current_user.id, limit=100)
    item = next((row for row in rows if row[0].id == notification_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return _response(*item)


@router.post("/read-all", status_code=204)
def mark_all_read(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    set_current_user_id(db, str(current_user.id))
    db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.read_at.is_(None))
        .values(read_at=func.now())
    )
    db.commit()
