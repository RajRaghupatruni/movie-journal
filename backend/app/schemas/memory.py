from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
    field_validator,
    model_validator,
)


class MemoryCategory(StrEnum):
    MOVIE = "movie"
    PLACE = "place"
    TRIP = "trip"
    ACTIVITY = "activity"
    CUSTOM = "custom"


class StrictMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MovieMetadata(StrictMetadata):
    provider: Literal["manual", "tmdb"] = "manual"
    provider_movie_id: str | None = Field(default=None, max_length=64)
    movie_title_snapshot: str | None = Field(default=None, max_length=180)
    release_year: int | None = Field(default=None, ge=1888, le=2200)
    release_date: date | None = None
    poster_url: HttpUrl | None = None
    runtime_minutes: int | None = Field(default=None, ge=1, le=1000)
    original_title: str | None = Field(default=None, max_length=180)
    backdrop_url: HttpUrl | None = None
    overview: str | None = Field(default=None, max_length=5000)
    genres: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("genres")
    @classmethod
    def validate_genres(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 40 for value in cleaned):
            raise ValueError("genres must be between 1 and 40 characters")
        return list(dict.fromkeys(cleaned))


class PlaceMetadata(StrictMetadata):
    provider: Literal["manual", "geoapify"] = "manual"
    provider_place_id: str | None = Field(default=None, max_length=128)
    name: str | None = Field(default=None, max_length=180)
    formatted_address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    category: str | None = Field(default=None, max_length=120)


class TripMetadata(StrictMetadata):
    destination: str = Field(min_length=1, max_length=180)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "TripMetadata":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class ActivityMetadata(StrictMetadata):
    activity_kind: str | None = Field(default=None, max_length=120)


class CustomMetadata(StrictMetadata):
    label: str | None = Field(default=None, max_length=120)


Metadata = MovieMetadata | PlaceMetadata | TripMetadata | ActivityMetadata | CustomMetadata
_metadata_adapters = {
    MemoryCategory.MOVIE: TypeAdapter(MovieMetadata),
    MemoryCategory.PLACE: TypeAdapter(PlaceMetadata),
    MemoryCategory.TRIP: TypeAdapter(TripMetadata),
    MemoryCategory.ACTIVITY: TypeAdapter(ActivityMetadata),
    MemoryCategory.CUSTOM: TypeAdapter(CustomMetadata),
}


def normalize_tag(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError:
        raise ValueError("timezone must be an IANA timezone") from None
    return value


class MemoryWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: MemoryCategory
    title: str = Field(min_length=1, max_length=180)
    local_date: date
    end_date: date | None = None
    occurred_at: datetime | None = None
    timezone: str = Field(min_length=1, max_length=64)
    notes: str | None = Field(default=None, max_length=10000)
    rating: int | None = Field(default=None, ge=1, le=10)
    participant_ids: list[UUID] = Field(default_factory=list, max_length=10)
    tags: list[str] = Field(default_factory=list, max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)
    nostalgia_eligible: bool = True

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value: str) -> str:
        return validate_timezone(value)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values: list[str]) -> list[str]:
        cleaned = [normalize_tag(value) for value in values]
        if any(not value or len(value) > 64 for value in cleaned):
            raise ValueError("tags must be between 1 and 64 characters")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("tags must not contain duplicates")
        return cleaned

    @model_validator(mode="after")
    def validate_metadata(self) -> "MemoryWrite":
        if self.occurred_at and self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        parsed = _metadata_adapters[self.category].validate_python(self.metadata)
        self.metadata = parsed.model_dump(mode="json", exclude_none=True)
        if self.category is MemoryCategory.TRIP:
            metadata_start = self.metadata.get("start_date")
            metadata_end = self.metadata.get("end_date")
            if metadata_start and date.fromisoformat(metadata_start) != self.local_date:
                raise ValueError("trip start_date must match local_date")
            if self.end_date is not None:
                if self.end_date < self.local_date:
                    raise ValueError("end_date must be on or after local_date")
                self.metadata["end_date"] = self.end_date.isoformat()
            elif metadata_end:
                self.end_date = date.fromisoformat(metadata_end)
        elif self.end_date is not None:
            raise ValueError("end_date is only supported for trip memories")
        return self


class MemoryCreate(MemoryWrite):
    pass


class MemoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    category: MemoryCategory | None = None
    title: str | None = Field(default=None, min_length=1, max_length=180)
    local_date: date | None = None
    end_date: date | None = None
    occurred_at: datetime | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    notes: str | None = Field(default=None, max_length=10000)
    rating: int | None = Field(default=None, ge=1, le=10)
    participant_ids: list[UUID] | None = Field(default=None, max_length=10)
    tags: list[str] | None = Field(default=None, max_length=20)
    metadata: dict[str, Any] | None = None
    nostalgia_eligible: bool | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value: str | None) -> str | None:
        return validate_timezone(value) if value is not None else None

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        cleaned = [normalize_tag(value) for value in values]
        if any(not value or len(value) > 64 for value in cleaned):
            raise ValueError("tags must be between 1 and 64 characters")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("tags must not contain duplicates")
        return cleaned


class MemberSummary(BaseModel):
    user_id: UUID
    display_name: str


class ReflectionResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    display_name: str
    rating: int | None = None
    note: str | None = None
    reaction: str | None = None
    created_at: datetime
    updated_at: datetime


class ReflectionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int | None = Field(default=None, ge=1, le=10)
    note: str | None = Field(default=None, max_length=10000)
    reaction: Literal["loved", "nostalgic", "funny", "favorite"] | None = None

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class MemoryMediaResponse(BaseModel):
    id: UUID
    memory_id: UUID
    content_type: str
    byte_size: int
    width: int
    height: int
    created_at: datetime
    display_order: int
    url: str | None = None


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tandem_id: UUID
    tandem_name: str | None = None
    category: MemoryCategory
    title: str
    local_date: date
    end_date: date | None = None
    occurred_at: datetime | None
    timezone: str
    notes: str | None
    rating: int | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    version: int
    nostalgia_eligible: bool
    schema_version: int
    metadata: dict[str, Any]
    participants: list[MemberSummary]
    tags: list[str]
    media: list[MemoryMediaResponse] = Field(default_factory=list)
    reflections: list[ReflectionResponse] = Field(default_factory=list)
    my_reflection: ReflectionResponse | None = None
    deleted_at: datetime | None = None
    deletion_expires_at: datetime | None = None


class DuplicateMemoryResponse(BaseModel):
    id: UUID
    title: str
    local_date: date
    category: MemoryCategory
    tandem_id: UUID


class MemoryListResponse(BaseModel):
    items: list[MemoryResponse]
    offset: int
    limit: int
    next_offset: int | None
