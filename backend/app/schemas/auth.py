from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    avatar_url: str | None
    timezone: str = "UTC"
    created_at: datetime


class NotificationPreferenceResponse(BaseModel):
    timezone: str
    anniversary_notifications_enabled: bool
    anniversary_email_enabled: bool
    notification_hour: int


class NotificationPreferencePatch(BaseModel):
    timezone: str | None = None
    anniversary_notifications_enabled: bool | None = None
    anniversary_email_enabled: bool | None = None
    notification_hour: int | None = None

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("timezone must be an IANA timezone") from None
        return value

    @field_validator("notification_hour")
    @classmethod
    def check_hour(cls, value: int | None) -> int | None:
        if value is not None and not 0 <= value <= 23:
            raise ValueError("notification_hour must be between 0 and 23")
        return value


class InvitationSummary(BaseModel):
    id: UUID
    tandem_id: UUID
    tandem_name: str
    invited_email: str
    status: str
    expires_at: datetime
    inviter_name: str | None = None


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
