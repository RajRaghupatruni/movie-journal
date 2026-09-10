from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import MAX_TANDEM_MEMBERS
from app.db.session import get_db, set_current_user_id
from app.models import Invitation, Tandem, TandemMember, User
from app.schemas.auth import InvitationCreate, InvitationCreated, InvitationSummary
from app.services.auth import get_current_user, hash_secret, new_secret, normalize_email
from app.services.authorization import TandemAccess, require_tandem_owner
from app.services.notifications import create_notification

router = APIRouter(tags=["invitations"])


def _summary(
    invitation: Invitation, tandem_name: str, inviter_name: str | None = None
) -> InvitationSummary:
    return InvitationSummary(
        id=invitation.id,
        tandem_id=invitation.tandem_id,
        tandem_name=tandem_name,
        invited_email=invitation.invited_email,
        status=invitation.status,
        expires_at=invitation.expires_at,
        inviter_name=inviter_name,
    )


def _find_invitation(db: Session, reference: str, *, lock: bool = False) -> Invitation:
    statement = select(Invitation).where(Invitation.token_hash == hash_secret(reference))
    if lock:
        statement = statement.with_for_update()
    invitation = db.scalar(statement)
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return invitation


def _find_owner_invitation(db: Session, reference: str, *, lock: bool = False) -> Invitation:
    try:
        invitation_id = UUID(reference)
    except ValueError:
        return _find_invitation(db, reference, lock=lock)
    statement = select(Invitation).where(Invitation.id == invitation_id)
    if lock:
        statement = statement.with_for_update()
    invitation = db.scalar(statement)
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return invitation


def _lock_tandem_capacity(db: Session, tandem_id) -> None:
    """Serialize capacity changes without weakening invitee RLS visibility."""

    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:tandem_id, 0))"),
        {"tandem_id": str(tandem_id)},
    )


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
    _lock_tandem_capacity(db, access.tandem.id)
    tandem = db.scalar(select(Tandem).where(Tandem.id == access.tandem.id).with_for_update())
    if tandem is None:
        raise HTTPException(status_code=404, detail="Tandem not found")

    member_count = int(db.scalar(select(func.app.tandem_member_count(tandem.id))) or 0)
    if member_count >= MAX_TANDEM_MEMBERS:
        raise HTTPException(
            status_code=409,
            detail=f"Tandem is full; it can have at most {MAX_TANDEM_MEMBERS} members",
        )

    pending_invitations = db.scalars(
        select(Invitation)
        .where(
            Invitation.tandem_id == tandem.id,
            Invitation.status == "PENDING",
        )
        .with_for_update()
    ).all()
    existing = next(
        (
            invitation
            for invitation in pending_invitations
            if invitation.invited_email == invited_email
        ),
        None,
    )
    if existing is not None:
        if existing.expires_at > now:
            raise HTTPException(status_code=409, detail="An active invitation already exists")
        existing.status = "EXPIRED"
        existing.responded_at = now

    active_pending_count = sum(
        invitation.expires_at > now
        for invitation in pending_invitations
        if invitation is not existing
    )
    if member_count + active_pending_count >= MAX_TANDEM_MEMBERS:
        raise HTTPException(
            status_code=409,
            detail="Tandem has no room reserved for another invitation",
        )

    reference = new_secret()
    invitation = Invitation(
        tandem_id=tandem.id,
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
    invited_user = db.scalar(
        select(User).where(User.email == invited_email, User.is_active.is_(True))
    )
    if invited_user:
        create_notification(
            db,
            user_id=invited_user.id,
            notification_type="tandem_invitation",
            actor_user_id=current_user.id,
            tandem_id=tandem.id,
            invitation_id=invitation.id,
            payload={"tandem_name": tandem.name},
            dedupe_key=f"invite:{invitation.id}",
        )
        db.commit()
        set_current_user_id(db, str(current_user.id))
    return InvitationCreated(
        **_summary(invitation, tandem.name).model_dump(),
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
    inviter = db.get(User, invitation.invited_by)
    return _summary(invitation, tandem.name, inviter.display_name if inviter else None)


@router.get("/api/tandems/{tandem_id}/invitations", response_model=list[InvitationSummary])
def list_invitations(
    access: TandemAccess = Depends(require_tandem_owner), db: Session = Depends(get_db)
):
    rows = db.execute(
        select(Invitation, User.display_name)
        .outerjoin(User, User.id == Invitation.invited_by)
        .where(Invitation.tandem_id == access.tandem.id)
        .order_by(Invitation.created_at.desc())
    ).all()
    now = datetime.now(UTC)
    result = []
    for invitation, inviter_name in rows:
        if invitation.status == "PENDING" and invitation.expires_at <= now:
            invitation.status = "EXPIRED"
            invitation.responded_at = now
        result.append(_summary(invitation, access.tandem.name, inviter_name))
    db.commit()
    return result


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
    # A transaction-scoped advisory lock keyed by Tandem serializes concurrent
    # acceptances while preserving the narrow RLS visibility granted to invitees.
    # This is the authoritative membership-capacity check; invitation creation
    # is only an early guard.
    _lock_tandem_capacity(db, invitation.tandem_id)
    tandem = db.get(Tandem, invitation.tandem_id)
    if tandem is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitation = _find_owner_invitation(db, safe_reference, lock=True)
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
        member_count = int(
            db.scalar(select(func.app.tandem_member_count(invitation.tandem_id))) or 0
        )
        if member_count >= MAX_TANDEM_MEMBERS:
            raise HTTPException(
                status_code=409,
                detail=f"Tandem is full; it can have at most {MAX_TANDEM_MEMBERS} members",
            )
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
        # Make the invitee's RLS update valid before the next query triggers
        # autoflush. The membership INSERT above still validated against the
        # pending invitation in the same transaction.
        invitation.status = action
        invitation.responded_at = now
        existing_members = db.scalars(
            select(TandemMember.user_id).where(
                TandemMember.tandem_id == invitation.tandem_id,
                TandemMember.user_id != current_user.id,
            )
        ).all()
        for member_id in existing_members:
            create_notification(
                db,
                user_id=member_id,
                notification_type="invitation_accepted",
                actor_user_id=current_user.id,
                tandem_id=invitation.tandem_id,
                invitation_id=invitation.id,
                payload={"member_name": current_user.display_name, "tandem_name": tandem.name},
                dedupe_key=f"member-joined:{invitation.id}:{member_id}",
            )
    if action != "ACCEPTED":
        invitation.status = action
        invitation.responded_at = now
    db.commit()
    set_current_user_id(db, str(current_user.id))
    inviter = db.get(User, invitation.invited_by)
    return _summary(invitation, tandem.name, inviter.display_name if inviter else None)


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
    invitation = _find_owner_invitation(db, safe_reference, lock=True)
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


@router.post(
    "/api/tandems/{tandem_id}/invitations/{safe_reference}/resend",
    response_model=InvitationCreated,
)
def resend_invitation(
    safe_reference: str = Path(min_length=20, max_length=128),
    access: TandemAccess = Depends(require_tandem_owner),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitationCreated:
    set_current_user_id(db, str(current_user.id))
    _lock_tandem_capacity(db, access.tandem.id)
    old = _find_owner_invitation(db, safe_reference, lock=True)
    if old.tandem_id != access.tandem.id:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if old.status not in {"PENDING", "EXPIRED", "REVOKED"}:
        raise HTTPException(status_code=409, detail="This invitation cannot be reissued")
    old.status = "REVOKED" if old.status == "PENDING" else old.status
    old.responded_at = datetime.now(UTC)
    member_count = int(db.scalar(select(func.app.tandem_member_count(access.tandem.id))) or 0)
    active_pending_count = int(
        db.scalar(
            select(func.count())
            .select_from(Invitation)
            .where(
                Invitation.tandem_id == access.tandem.id,
                Invitation.status == "PENDING",
                Invitation.expires_at > datetime.now(UTC),
            )
        )
        or 0
    )
    if member_count + active_pending_count >= MAX_TANDEM_MEMBERS:
        raise HTTPException(
            status_code=409,
            detail="Tandem has no room reserved for another invitation",
        )
    reference = new_secret()
    invitation = Invitation(
        tandem_id=access.tandem.id,
        invited_email=old.invited_email,
        invited_by=current_user.id,
        token_hash=hash_secret(reference),
        status="PENDING",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(invitation)
    db.commit()
    set_current_user_id(db, str(current_user.id))
    db.refresh(invitation)
    invited_user = db.scalar(
        select(User).where(User.email == invitation.invited_email, User.is_active.is_(True))
    )
    if invited_user:
        create_notification(
            db,
            user_id=invited_user.id,
            notification_type="tandem_invitation",
            actor_user_id=current_user.id,
            tandem_id=access.tandem.id,
            invitation_id=invitation.id,
            payload={"tandem_name": access.tandem.name},
            dedupe_key=f"invite:{invitation.id}",
        )
        db.commit()
    return InvitationCreated(
        **_summary(invitation, access.tandem.name, current_user.display_name).model_dump(),
        reference=reference,
    )
