from datetime import date

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class MovieSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tmdb_id: int
    title: str = Field(min_length=1, max_length=180)
    original_title: str | None = Field(default=None, max_length=180)
    release_date: date | None = None
    release_year: int | None = None
    poster_url: HttpUrl | None = None
    backdrop_url: HttpUrl | None = None
    overview: str | None = Field(default=None, max_length=5000)
    genres: list[str] = Field(default_factory=list, max_length=12)
    runtime_minutes: int | None = Field(default=None, ge=1, le=1000)


class MovieSearchResponse(BaseModel):
    items: list[MovieSearchResult]


class PlaceSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "geoapify"
    provider_place_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=180)
    formatted_address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    category: str | None = Field(default=None, max_length=120)


class PlaceSearchResponse(BaseModel):
    items: list[PlaceSearchResult]
