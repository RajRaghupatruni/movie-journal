from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    avatar_url: str | None
    created_at: datetime


class InvitationSummary(BaseModel):
    id: UUID
    tandem_id: UUID
    tandem_name: str
    invited_email: str
    status: str
    expires_at: datetime


class InvitationCreate(BaseModel):
    invited_email: str
    expires_in_days: int = 7


class InvitationCreated(InvitationSummary):
    # This is the one-time raw URL reference. token_hash is never exposed.
    reference: str


class TandemCreate(BaseModel):
    name: str
    timezone: str = "UTC"


class TandemUpdate(BaseModel):
    name: str | None = None
    timezone: str | None = None


class TandemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_by: UUID
    timezone: str
    created_at: datetime
    updated_at: datetime


class MemberResponse(BaseModel):
    user_id: UUID
    email: str
    display_name: str
    avatar_url: str | None
    role: str
    joined_at: datetime
