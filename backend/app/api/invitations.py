from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db, set_current_user_id
from app.models import Invitation, Tandem, TandemMember, User
from app.schemas.auth import InvitationCreate, InvitationCreated, InvitationSummary
from app.services.auth import get_current_user, hash_secret, new_secret, normalize_email
from app.services.authorization import TandemAccess, require_tandem_owner

router = APIRouter(tags=["invitations"])


def _summary(invitation: Invitation, tandem_name: str) -> InvitationSummary:
    return InvitationSummary(
        id=invitation.id,
        tandem_id=invitation.tandem_id,
        tandem_name=tandem_name,
        invited_email=invitation.invited_email,
        status=invitation.status,
        expires_at=invitation.expires_at,
    )


def _find_invitation(db: Session, reference: str, *, lock: bool = False) -> Invitation:
    statement = select(Invitation).where(Invitation.token_hash == hash_secret(reference))
    if lock:
        statement = statement.with_for_update()
    invitation = db.scalar(statement)
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return invitation


@router.post(
    "/api/tandems/{tandem_id}/invitations",
    response_model=InvitationCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    payload: InvitationCreate,
    access: TandemAccess = Depends(require_tandem_owner),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationCreated:
    set_current_user_id(db, str(current_user.id))
    invited_email = normalize_email(payload.invited_email)
    if "@" not in invited_email or len(invited_email) > 320:
        raise HTTPException(status_code=422, detail="invited_email must be a valid email")
    if not 1 <= payload.expires_in_days <= 30:
        raise HTTPException(status_code=422, detail="expires_in_days must be between 1 and 30")
    now = datetime.now(UTC)
    existing = db.scalar(
        select(Invitation)
        .where(
            Invitation.tandem_id == access.tandem.id,
            Invitation.invited_email == invited_email,
            Invitation.status == "PENDING",
        )
        .with_for_update()
    )
    if existing is not None:
        if existing.expires_at > now:
            raise HTTPException(status_code=409, detail="An active invitation already exists")
        existing.status = "EXPIRED"
        existing.responded_at = now

    reference = new_secret()
    invitation = Invitation(
        tandem_id=access.tandem.id,
        invited_email=invited_email,
        invited_by=current_user.id,
        token_hash=hash_secret(reference),
        status="PENDING",
        expires_at=now + timedelta(days=payload.expires_in_days),
    )
    db.add(invitation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An active invitation already exists") from None
    set_current_user_id(db, str(current_user.id))
    db.refresh(invitation)
    return InvitationCreated(
        **_summary(invitation, access.tandem.name).model_dump(),
        reference=reference,
    )


@router.get("/api/invitations/{safe_reference}", response_model=InvitationSummary)
def get_invitation(
    safe_reference: str = Path(min_length=20, max_length=128),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationSummary:
    invitation = _find_invitation(db, safe_reference)
    tandem = db.get(Tandem, invitation.tandem_id)
    if tandem is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.status == "PENDING" and invitation.expires_at <= datetime.now(UTC):
        invitation.status = "EXPIRED"
        invitation.responded_at = datetime.now(UTC)
        db.commit()
        set_current_user_id(db, str(current_user.id))
    if normalize_email(current_user.email) != invitation.invited_email:
        raise HTTPException(status_code=403, detail="Invitation belongs to another email")
    return _summary(invitation, tandem.name)


def _respond_to_invitation(
    safe_reference: str,
    action: str,
    current_user: User,
    db: Session,
) -> InvitationSummary:
    set_current_user_id(db, str(current_user.id))
    invitation = _find_invitation(db, safe_reference)
    now = datetime.now(UTC)
    if normalize_email(current_user.email) != invitation.invited_email:
        raise HTTPException(status_code=403, detail="Invitation belongs to another email")
    if invitation.status != "PENDING":
        raise HTTPException(status_code=409, detail="Invitation is no longer pending")
    if invitation.expires_at <= now:
        invitation.status = "EXPIRED"
        invitation.responded_at = now
        db.commit()
        raise HTTPException(status_code=410, detail="Invitation has expired")
    # The recipient check must happen before FOR UPDATE: PostgreSQL's UPDATE USING
    # policy would otherwise hide a row belonging to a different email as a 404.
    invitation = _find_invitation(db, safe_reference, lock=True)
    tandem = db.get(Tandem, invitation.tandem_id)
    if tandem is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.status != "PENDING":
        raise HTTPException(status_code=409, detail="Invitation is no longer pending")

    if action == "ACCEPTED":
        existing_member = db.scalar(
            select(TandemMember).where(
                TandemMember.tandem_id == invitation.tandem_id,
                TandemMember.user_id == current_user.id,
            )
        )
        if existing_member is not None:
            raise HTTPException(status_code=409, detail="User is already a tandem member")
        db.add(
            TandemMember(
                tandem_id=invitation.tandem_id,
                user_id=current_user.id,
                role="MEMBER",
            )
        )
        # The RLS INSERT policy checks the still-pending invitation. Flush the
        # membership before changing its status, then commit both changes atomically.
        db.flush()
        invitation.accepted_by = current_user.id
    invitation.status = action
    invitation.responded_at = now
    db.commit()
    set_current_user_id(db, str(current_user.id))
    return _summary(invitation, tandem.name)


@router.post("/api/invitations/{safe_reference}/accept", response_model=InvitationSummary)
def accept_invitation(
    safe_reference: str = Path(min_length=20, max_length=128),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationSummary:
    return _respond_to_invitation(safe_reference, "ACCEPTED", current_user, db)


@router.post("/api/invitations/{safe_reference}/decline", response_model=InvitationSummary)
def decline_invitation(
    safe_reference: str = Path(min_length=20, max_length=128),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationSummary:
    return _respond_to_invitation(safe_reference, "DECLINED", current_user, db)


@router.post(
    "/api/tandems/{tandem_id}/invitations/{safe_reference}/revoke",
    response_model=InvitationSummary,
)
def revoke_invitation(
    safe_reference: str = Path(min_length=20, max_length=128),
    access: TandemAccess = Depends(require_tandem_owner),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationSummary:
    set_current_user_id(db, str(current_user.id))
    invitation = _find_invitation(db, safe_reference, lock=True)
    if invitation.tandem_id != access.tandem.id:
        raise HTTPException(status_code=404, detail="Invitation not found")
    now = datetime.now(UTC)
    if invitation.status != "PENDING":
        raise HTTPException(status_code=409, detail="Invitation is no longer pending")
    if invitation.expires_at <= now:
        invitation.status = "EXPIRED"
        invitation.responded_at = now
        db.commit()
        raise HTTPException(status_code=409, detail="Invitation has expired")
    invitation.status = "REVOKED"
    invitation.responded_at = now
    db.commit()
    set_current_user_id(db, str(current_user.id))
    return _summary(invitation, access.tandem.name)
