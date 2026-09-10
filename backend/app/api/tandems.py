from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.db.session import get_db, set_current_user_id
from app.models import MemoryMedia, StorageCleanupFailure, Tandem, TandemMember, User
from app.schemas.auth import (
    AccountAction,
    MemberResponse,
    TandemCreate,
    TandemResponse,
    TandemUpdate,
)
from app.services.auth import get_current_user
from app.services.authorization import (
    TandemAccess,
    require_tandem_member,
    require_tandem_owner,
)
from app.services.media_storage import ObjectStorage
from app.services.notifications import cancel_user_tandem_notifications, create_notification

router = APIRouter(prefix="/tandems", tags=["tandems"])


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=422, detail="timezone must be an IANA timezone") from None
    return value


@router.post("", response_model=TandemResponse, status_code=status.HTTP_201_CREATED)
def create_tandem(
    payload: TandemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TandemResponse:
    set_current_user_id(db, str(current_user.id))
    name = payload.name.strip()
    if not name or len(name) > 120:
        raise HTTPException(status_code=422, detail="name must be between 1 and 120 characters")
    timezone = validate_timezone(payload.timezone)
    tandem = Tandem(name=name, timezone=timezone, created_by=current_user.id)
    db.add(tandem)
    db.flush()
    db.add(TandemMember(tandem_id=tandem.id, user_id=current_user.id, role="OWNER"))
    db.commit()
    set_current_user_id(db, str(current_user.id))
    db.refresh(tandem)
    return TandemResponse.model_validate(tandem)


@router.get("/{tandem_id}", response_model=TandemResponse)
def get_tandem(access: TandemAccess = Depends(require_tandem_member)) -> TandemResponse:
    return TandemResponse.model_validate(access.tandem)


@router.delete("/{tandem_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tandem(
    request: Request,
    payload: AccountAction | None = Body(default=None),
    confirm: str | None = None,
    access: TandemAccess = Depends(require_tandem_owner),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    confirmation = payload.confirmation if payload else confirm
    if confirmation not in {access.tandem.name, "DELETE"}:
        raise HTTPException(status_code=422, detail="Type the Tandem name or DELETE to confirm")
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:id, 0))"),
        {"id": str(access.tandem.id)},
    )
    media = db.scalars(select(MemoryMedia).where(MemoryMedia.tandem_id == access.tandem.id)).all()
    storage: ObjectStorage | None = getattr(request.app.state, "object_storage", None)
    if media and storage is None:
        raise HTTPException(
            status_code=503, detail="Photo storage is unavailable; Tandem remains intact"
        )
    if storage:
        for item in media:
            try:
                storage.delete_object(item.object_key)
            except Exception as exc:
                db.execute(text("SELECT set_config('app.worker_mode', 'true', true)"))
                failure = db.scalar(
                    select(StorageCleanupFailure)
                    .where(StorageCleanupFailure.object_key == item.object_key)
                    .with_for_update()
                )
                if failure is None:
                    db.add(
                        StorageCleanupFailure(
                            object_key=item.object_key,
                            scope={"tandem_id": str(access.tandem.id)},
                            attempts=1,
                            last_error=str(exc)[:2000],
                        )
                    )
                else:
                    failure.attempts += 1
                    failure.last_error = str(exc)[:2000]
                    failure.resolved_at = None
                db.commit()
                raise HTTPException(
                    status_code=503,
                    detail="Some private photos could not be cleaned up; Tandem remains intact",
                ) from None
    db.delete(access.tandem)
    db.commit()


@router.patch("/{tandem_id}", response_model=TandemResponse)
def update_tandem(
    payload: TandemUpdate,
    access: TandemAccess = Depends(require_tandem_owner),
    db: Session = Depends(get_db),
) -> TandemResponse:
    if payload.name is not None:
        name = payload.name.strip()
        if not name or len(name) > 120:
            raise HTTPException(status_code=422, detail="name must be between 1 and 120 characters")
        access.tandem.name = name
    if payload.timezone is not None:
        access.tandem.timezone = validate_timezone(payload.timezone)
    db.commit()
    set_current_user_id(db, str(access.member.user_id))
    db.refresh(access.tandem)
    return TandemResponse.model_validate(access.tandem)


@router.get("/{tandem_id}/members", response_model=list[MemberResponse])
def list_members(
    access: TandemAccess = Depends(require_tandem_member), db: Session = Depends(get_db)
) -> list[MemberResponse]:
    rows = db.execute(
        select(TandemMember, User)
        .join(User, User.id == TandemMember.user_id)
        .where(TandemMember.tandem_id == access.tandem.id)
        .order_by(TandemMember.joined_at, User.email)
    ).all()
    return [
        MemberResponse(
            user_id=member.user_id,
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            role=member.role,
            joined_at=member.joined_at,
        )
        for member, user in rows
    ]


@router.delete("/{tandem_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: UUID,
    access: TandemAccess = Depends(require_tandem_owner),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:id, 0))"),
        {"id": str(access.tandem.id)},
    )
    member = db.scalar(
        select(TandemMember).where(
            TandemMember.tandem_id == access.tandem.id, TandemMember.user_id == user_id
        )
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "OWNER":
        owners = (
            db.scalar(
                select(func.count())
                .select_from(TandemMember)
                .where(TandemMember.tandem_id == access.tandem.id, TandemMember.role == "OWNER")
            )
            or 0
        )
        if owners <= 1:
            raise HTTPException(
                status_code=409, detail="Transfer ownership before removing the final owner"
            )
    recipients = db.scalars(
        select(TandemMember.user_id).where(
            TandemMember.tandem_id == access.tandem.id, TandemMember.user_id != user_id
        )
    ).all()
    db.delete(member)
    db.commit()
    set_current_user_id(db, str(current_user.id))
    cancel_user_tandem_notifications(db, user_id, access.tandem.id)
    for recipient_id in recipients:
        create_notification(
            db,
            user_id=recipient_id,
            notification_type="member_removed",
            actor_user_id=current_user.id,
            tandem_id=access.tandem.id,
            payload={"member_name": user_id.hex[:8], "tandem_name": access.tandem.name},
            dedupe_key=f"member-removed:{access.tandem.id}:{user_id}:{datetime.now(UTC).timestamp()}",
        )
    db.commit()


@router.post("/{tandem_id}/members/{user_id}/promote", response_model=MemberResponse)
def promote_member(
    user_id: UUID,
    access: TandemAccess = Depends(require_tandem_owner),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemberResponse:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:id, 0))"),
        {"id": str(access.tandem.id)},
    )
    member = db.scalar(
        select(TandemMember)
        .where(TandemMember.tandem_id == access.tandem.id, TandemMember.user_id == user_id)
        .with_for_update()
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "OWNER":
        raise HTTPException(status_code=409, detail="Member is already an owner")
    member.role = "OWNER"
    db.commit()
    set_current_user_id(db, str(current_user.id))
    create_notification(
        db,
        user_id=user_id,
        notification_type="owner_promoted",
        actor_user_id=current_user.id,
        tandem_id=access.tandem.id,
        payload={"tandem_name": access.tandem.name},
        dedupe_key=f"owner-promoted:{access.tandem.id}:{user_id}:{member.joined_at.isoformat()}",
    )
    db.commit()
    set_current_user_id(db, str(current_user.id))
    user = db.get(User, user_id)
    return MemberResponse(
        user_id=member.user_id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.post("/{tandem_id}/members/{user_id}/demote", response_model=MemberResponse)
def demote_member(
    user_id: UUID,
    access: TandemAccess = Depends(require_tandem_owner),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemberResponse:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:id, 0))"),
        {"id": str(access.tandem.id)},
    )
    if user_id == current_user.id:
        raise HTTPException(status_code=409, detail="You cannot demote yourself")
    member = db.scalar(
        select(TandemMember)
        .where(TandemMember.tandem_id == access.tandem.id, TandemMember.user_id == user_id)
        .with_for_update()
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role != "OWNER":
        raise HTTPException(status_code=409, detail="Member is not an owner")
    member.role = "MEMBER"
    db.commit()
    set_current_user_id(db, str(current_user.id))
    create_notification(
        db,
        user_id=user_id,
        notification_type="owner_demoted",
        actor_user_id=current_user.id,
        tandem_id=access.tandem.id,
        payload={"tandem_name": access.tandem.name},
        dedupe_key=f"owner-demoted:{access.tandem.id}:{user_id}:{member.joined_at.isoformat()}",
    )
    db.commit()
    set_current_user_id(db, str(current_user.id))
    user = db.get(User, user_id)
    return MemberResponse(
        user_id=member.user_id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.post("/{tandem_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_tandem(
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:id, 0))"),
        {"id": str(access.tandem.id)},
    )
    if access.member.role == "OWNER":
        owner_count = db.scalar(
            select(func.count())
            .select_from(TandemMember)
            .where(TandemMember.tandem_id == access.tandem.id, TandemMember.role == "OWNER")
        )
        if owner_count == 1:
            raise HTTPException(
                status_code=409,
                detail="The final owner must transfer ownership or delete the tandem",
            )
    recipients = db.scalars(
        select(TandemMember.user_id).where(
            TandemMember.tandem_id == access.tandem.id, TandemMember.user_id != current_user.id
        )
    ).all()
    db.execute(
        delete(TandemMember).where(
            TandemMember.tandem_id == access.tandem.id, TandemMember.user_id == current_user.id
        )
    )
    db.commit()
    set_current_user_id(db, str(current_user.id))
    cancel_user_tandem_notifications(db, current_user.id, access.tandem.id)
    for recipient_id in recipients:
        create_notification(
            db,
            user_id=recipient_id,
            notification_type="member_left",
            actor_user_id=current_user.id,
            tandem_id=access.tandem.id,
            payload={"member_name": current_user.display_name, "tandem_name": access.tandem.name},
            dedupe_key=f"member-left:{access.tandem.id}:{current_user.id}:{datetime.now(UTC).timestamp()}",
        )
    db.commit()
