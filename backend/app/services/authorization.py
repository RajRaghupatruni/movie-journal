from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db, set_current_user_id
from app.models import Tandem, TandemMember, User
from app.services.auth import get_current_user


@dataclass(frozen=True)
class TandemAccess:
    tandem: Tandem
    member: TandemMember


def require_tandem_member(
    tandem_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TandemAccess:
    set_current_user_id(db, str(current_user.id))
    access = db.execute(
        select(Tandem, TandemMember)
        .join(TandemMember, TandemMember.tandem_id == Tandem.id)
        .where(Tandem.id == tandem_id, TandemMember.user_id == current_user.id)
    ).first()
    if access is None:
        # Do not reveal whether a guessed UUID belongs to another tandem.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tandem not found")
    return TandemAccess(tandem=access[0], member=access[1])


def require_tandem_owner(
    access: TandemAccess = Depends(require_tandem_member),
) -> TandemAccess:
    if access.member.role != "OWNER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tandem owner required")
    return access
