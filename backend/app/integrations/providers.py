"""Backend-owned, normalized clients for external capture providers."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

from app.core.config import Settings
from app.core.logging import request_id
from app.schemas.integrations import MovieSearchResult, PlaceSearchResult

logger = logging.getLogger(__name__)


class ProviderUnavailable(Exception):
    pass


class ProviderClientError(Exception):
    pass


def _request_json(
    url: str, *, params: dict[str, Any], headers: dict[str, str] | None, timeout: float
) -> dict[str, Any]:
    try:
        response = httpx.get(url, params=params, headers=headers, timeout=timeout)
    except httpx.TimeoutException as exc:
        logger.warning("provider_timeout", extra={"provider_request_id": request_id.get()})
        raise ProviderUnavailable from exc
    except httpx.HTTPError as exc:
        logger.warning("provider_network_error", extra={"provider_request_id": request_id.get()})
        raise ProviderUnavailable from exc
    if response.status_code >= 500:
        logger.warning("provider_unavailable", extra={"provider_request_id": request_id.get()})
        raise ProviderUnavailable
    if response.status_code >= 400:
        logger.warning("provider_rejected_request", extra={"provider_request_id": request_id.get()})
        raise ProviderClientError
    try:
        payload = response.json()
    except ValueError as exc:
        logger.warning(
            "provider_malformed_response", extra={"provider_request_id": request_id.get()}
        )
        raise ProviderUnavailable from exc
    if not isinstance(payload, dict):
        raise ProviderUnavailable
    return payload


def _image_url(base_url: str, size: str, path: Any) -> str | None:
    if not isinstance(path, str) or not path.startswith("/"):
        return None
    return f"{base_url.rstrip('/')}/{size}{path}"


def _date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def normalize_movie(payload: dict[str, Any], settings: Settings) -> MovieSearchResult:
    tmdb_id = payload.get("id")
    title = payload.get("title") or payload.get("name")
    if not isinstance(tmdb_id, int) or not isinstance(title, str) or not title.strip():
        raise ProviderUnavailable
    release_date = _date(payload.get("release_date"))
    raw_genres = payload.get("genres", [])
    if not isinstance(raw_genres, list):
        raw_genres = []
    genres = [item.get("name", "").strip() for item in raw_genres if isinstance(item, dict)]
    genres = list(dict.fromkeys(item for item in genres if item))[:12]
    return MovieSearchResult(
        tmdb_id=tmdb_id,
        title=title.strip(),
        original_title=payload.get("original_title")
        if isinstance(payload.get("original_title"), str)
        else None,
        release_date=release_date,
        release_year=release_date.year if release_date else None,
        poster_url=_image_url(settings.tmdb_image_base_url, "w500", payload.get("poster_path")),
        backdrop_url=_image_url(
            settings.tmdb_image_base_url, "w1280", payload.get("backdrop_path")
        ),
        overview=payload.get("overview") if isinstance(payload.get("overview"), str) else None,
        genres=genres,
        runtime_minutes=payload.get("runtime")
        if isinstance(payload.get("runtime"), int) and payload.get("runtime") > 0
        else None,
    )


class TmdbClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def search(self, query: str) -> list[MovieSearchResult]:
        token = (
            self.settings.tmdb_api_token.get_secret_value()
            if self.settings.tmdb_api_token
            else None
        )
        if not token:
            raise ProviderUnavailable
        payload = _request_json(
            f"{self.settings.tmdb_base_url.rstrip('/')}/search/movie",
            params={"query": query, "include_adult": "false", "language": "en-US", "page": 1},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=self.settings.provider_timeout_seconds,
        )
        raw_results = payload.get("results", [])
        if not isinstance(raw_results, list):
            raise ProviderUnavailable
        normalized: list[MovieSearchResult] = []
        for item in raw_results[:10]:
            if isinstance(item, dict):
                try:
                    normalized.append(normalize_movie(item, self.settings))
                except ProviderUnavailable:
                    continue
        return normalized

    def get(self, tmdb_id: int) -> MovieSearchResult:
        token = (
            self.settings.tmdb_api_token.get_secret_value()
            if self.settings.tmdb_api_token
            else None
        )
        if not token:
            raise ProviderUnavailable
        payload = _request_json(
            f"{self.settings.tmdb_base_url.rstrip('/')}/movie/{tmdb_id}",
            params={"language": "en-US"},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=self.settings.provider_timeout_seconds,
        )
        return normalize_movie(payload, self.settings)


def normalize_place(properties: dict[str, Any]) -> PlaceSearchResult:
    datasource = properties.get("datasource")
    raw = datasource.get("raw") if isinstance(datasource, dict) else None
    place_id = properties.get("place_id") or (
        raw.get("place_id") if isinstance(raw, dict) else None
    )
    name = properties.get("name") or properties.get("address_line1")
    if (
        not isinstance(place_id, str)
        or not place_id
        or not isinstance(name, str)
        or not name.strip()
    ):
        raise ProviderUnavailable
    lat = properties.get("lat")
    lon = properties.get("lon")
    return PlaceSearchResult(
        provider_place_id=place_id,
        name=name.strip(),
        formatted_address=properties.get("formatted")
        if isinstance(properties.get("formatted"), str)
        else None,
        city=properties.get("city") if isinstance(properties.get("city"), str) else None,
        region=properties.get("state") or properties.get("state_district")
        if isinstance(properties.get("state") or properties.get("state_district"), str)
        else None,
        country=properties.get("country") if isinstance(properties.get("country"), str) else None,
        latitude=float(lat) if isinstance(lat, (int, float)) else None,
        longitude=float(lon) if isinstance(lon, (int, float)) else None,
        category=properties.get("category")
        if isinstance(properties.get("category"), str)
        else None,
    )


class GeoapifyClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def search(self, query: str) -> list[PlaceSearchResult]:
        key = (
            self.settings.geoapify_api_key.get_secret_value()
            if self.settings.geoapify_api_key
            else None
        )
        if not key:
            raise ProviderUnavailable
        payload = _request_json(
            f"{self.settings.geoapify_base_url.rstrip('/')}/geocode/autocomplete",
            params={"text": query, "apiKey": key, "limit": 10, "format": "json"},
            headers=None,
            timeout=self.settings.provider_timeout_seconds,
        )
        results = payload.get("results")
        if not isinstance(results, list):
            raise ProviderUnavailable
        normalized: list[PlaceSearchResult] = []
        for result in results[:10]:
            if not isinstance(result, dict):
                raise ProviderUnavailable
            try:
                normalized.append(normalize_place(result))
            except ProviderUnavailable:
                raise ProviderUnavailable from None
        return normalized
