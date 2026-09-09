from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db, set_current_user_id
from app.models import Tandem, TandemMember, User
from app.schemas.auth import (
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
    db: Session = Depends(get_db),
) -> None:
    member = db.scalar(
        select(TandemMember).where(
            TandemMember.tandem_id == access.tandem.id, TandemMember.user_id == user_id
        )
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "OWNER":
        raise HTTPException(status_code=409, detail="Transfer ownership before removing an owner")
    db.delete(member)
    db.commit()


@router.post("/{tandem_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_tandem(
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
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
    db.execute(
        delete(TandemMember).where(
            TandemMember.tandem_id == access.tandem.id, TandemMember.user_id == current_user.id
        )
    )
    db.commit()
