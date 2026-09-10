from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    display_name: str
    avatar_url: str | None
    timezone: str = "UTC"
    created_at: datetime
    is_active: bool = True


class StrictRequestModel(BaseModel):
    """Reject client-controlled properties outside the explicit request contract."""

    model_config = ConfigDict(extra="forbid")


class NotificationPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timezone: str
    anniversary_notifications_enabled: bool
    anniversary_email_enabled: bool
    notification_hour: int


class NotificationPreferencePatch(StrictRequestModel):
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
    created_at: datetime | None = None
    memory_count: int = 0
    earliest_memory_date: date | None = None


class InvitationCreate(StrictRequestModel):
    invited_email: str
    expires_in_days: int = 7


class InvitationCreated(InvitationSummary):
    # This is the one-time raw URL reference. token_hash is never exposed.
    reference: str


class TandemPreferenceResponse(BaseModel):
    tandem_id: UUID
    resurfacing_enabled: bool
    routine_notifications_enabled: bool


class TandemPreferencePatch(StrictRequestModel):
    resurfacing_enabled: bool | None = None
    routine_notifications_enabled: bool | None = None


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    actor_name: str | None = None
    tandem_id: UUID | None
    tandem_name: str | None = None
    memory_id: UUID | None
    payload: dict
    created_at: datetime
    read_at: datetime | None
    archived_at: datetime | None


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int


class AccountAction(StrictRequestModel):
    confirmation: str


class TandemCreate(StrictRequestModel):
    name: str
    timezone: str = "UTC"


class TandemUpdate(StrictRequestModel):
    name: str | None = None
    timezone: str | None = None


class TandemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_by: UUID | None
    timezone: str
    created_at: datetime
    updated_at: datetime


class TandemSummaryResponse(TandemResponse):
    member_count: int = 0
    owner_count: int = 0


class MemberResponse(BaseModel):
    user_id: UUID
    display_name: str
    role: str
    joined_at: datetime
