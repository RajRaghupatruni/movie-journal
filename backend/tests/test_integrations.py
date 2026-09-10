import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.integrations.providers import (
    GeoapifyClient,
    ProviderClientError,
    ProviderUnavailable,
    TmdbClient,
    normalize_movie,
    normalize_place,
)
from app.main import create_app
from app.services.auth import get_current_user

FIXTURES = Path(__file__).parent / "fixtures"


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+psycopg://fixture:fixture@127.0.0.1:1/fixture",
        tmdb_api_token=SecretStr("tmdb-test-token"),
        geoapify_api_key=SecretStr("geo-test-key"),
    )


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_tmdb_normalization_is_tandem_shaped():
    result = normalize_movie(
        {
            "id": 550,
            "title": "Fight Club",
            "original_title": "Fight Club",
            "release_date": "1999-10-15",
            "poster_path": "/poster.jpg",
            "backdrop_path": "/backdrop.jpg",
            "overview": "A normalized overview",
            "genres": [{"id": 18, "name": "Drama"}],
            "runtime": 139,
            "extra": "ignored",
        },
        _settings(),
    )
    assert result.model_dump(mode="json") == {
        "tmdb_id": 550,
        "title": "Fight Club",
        "original_title": "Fight Club",
        "release_date": "1999-10-15",
        "release_year": 1999,
        "poster_url": "https://image.tmdb.org/t/p/w500/poster.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/backdrop.jpg",
        "overview": "A normalized overview",
        "genres": ["Drama"],
        "runtime_minutes": 139,
    }


def test_tmdb_search_uses_backend_token_and_mock_response(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured.update(url=url, kwargs=kwargs)
        return httpx.Response(
            200, json={"results": [{"id": 1, "title": "A film", "release_date": "2024-01-01"}]}
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    results = TmdbClient(_settings()).search("A film")
    assert results[0].tmdb_id == 1
    assert captured["kwargs"]["headers"]["Authorization"] == "Bearer tmdb-test-token"
    assert "tmdb-test-token" not in repr(results)


def test_provider_timeout_is_translated(monkeypatch):
    def fake_get(*args, **kwargs):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(ProviderUnavailable):
        TmdbClient(_settings()).search("slow")


def test_geoapify_normalization_drops_raw_payload():
    result = normalize_place(
        {
            "place_id": "my-place",
            "name": "The Nook",
            "formatted": "The Nook, Chicago, Illinois, USA",
            "city": "Chicago",
            "state": "Illinois",
            "country": "United States",
            "lat": 41.88,
            "lon": -87.63,
            "category": "catering.restaurant",
            "datasource": {"raw": {"secret": "not returned"}},
        }
    )
    assert result.provider == "geoapify"
    assert result.provider_place_id == "my-place"
    assert result.latitude == 41.88
    assert "secret" not in result.model_dump_json()


def test_geoapify_timeout_is_translated(monkeypatch):
    monkeypatch.setattr(
        httpx, "get", lambda *args, **kwargs: (_ for _ in ()).throw(httpx.TimeoutException("slow"))
    )
    with pytest.raises(ProviderUnavailable):
        GeoapifyClient(_settings()).search("Chicago")


@pytest.mark.parametrize(
    ("query", "fixture_name"),
    [
        ("Chicago", "geoapify_autocomplete_chicago.json"),
        ("New York", "geoapify_autocomplete_new_york.json"),
    ],
)
def test_geoapify_json_results_are_normalized(monkeypatch, query, fixture_name):
    payload = _fixture(fixture_name)
    captured = {}

    def fake_get(url, **kwargs):
        captured.update(url=url, kwargs=kwargs)
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(httpx, "get", fake_get)
    results = GeoapifyClient(_settings()).search(query)

    assert results
    assert results[0].name == query
    assert results[0].formatted_address
    assert results[0].city == query
    assert results[0].latitude is not None
    assert results[0].longitude is not None
    assert captured["url"].endswith("/geocode/autocomplete")
    assert captured["kwargs"]["params"]["format"] == "json"
    assert captured["kwargs"]["params"]["text"] == query


def test_geoapify_json_named_place_preserves_normalized_metadata(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(
            200, json=_fixture("geoapify_autocomplete_named_place.json")
        ),
    )

    result = GeoapifyClient(_settings()).search("Millennium Park, Chicago")[0]

    assert result.model_dump(mode="json") == {
        "provider": "geoapify",
        "provider_place_id": "51f0c2b6a20f1b274059dc0a96dfac6c",
        "name": "Millennium Park",
        "formatted_address": (
            "Millennium Park, 201 East Randolph Street, Chicago, IL 60602, United States of America"
        ),
        "city": "Chicago",
        "region": "Illinois",
        "country": "United States of America",
        "latitude": 41.8826,
        "longitude": -87.6226,
        "category": "tourism.attraction",
    }


def test_geoapify_json_zero_results_is_empty(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(
            200, json=_fixture("geoapify_autocomplete_zero_results.json")
        ),
    )

    assert GeoapifyClient(_settings()).search("zzzzzzzzzzzzzzzz") == []


def test_geoapify_unexpected_response_shape_is_not_empty_success(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(
            200, json=_fixture("geoapify_autocomplete_unexpected_shape.json")
        ),
    )

    with pytest.raises(ProviderUnavailable):
        GeoapifyClient(_settings()).search("Chicago")


@pytest.mark.parametrize(
    ("status_code", "exception"),
    [(400, ProviderClientError), (500, ProviderUnavailable)],
)
def test_geoapify_non_2xx_behavior_remains_correct(monkeypatch, status_code, exception):
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: httpx.Response(status_code))

    with pytest.raises(exception):
        GeoapifyClient(_settings()).search("Chicago")


def test_geoapify_provider_failures_do_not_log_api_key(monkeypatch, caplog):
    secret = "geo-test-key"
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(
            200, json=_fixture("geoapify_autocomplete_unexpected_shape.json")
        ),
    )

    with pytest.raises(ProviderUnavailable):
        GeoapifyClient(_settings()).search("Chicago")

    assert secret not in caplog.text


def test_places_search_api_contract_uses_normalized_items(monkeypatch):
    app = create_app(_settings())
    app.dependency_overrides[get_current_user] = lambda: MagicMock()
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(
            200, json=_fixture("geoapify_autocomplete_chicago.json")
        ),
    )

    with TestClient(app) as client:
        response = client.get("/api/integrations/places/search?q=Chicago")

    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "Chicago"
    assert response.json()["items"][0]["provider"] == "geoapify"


def test_places_search_api_exposes_provider_schema_failure(monkeypatch):
    app = create_app(_settings())
    app.dependency_overrides[get_current_user] = lambda: MagicMock()
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(
            200, json=_fixture("geoapify_autocomplete_unexpected_shape.json")
        ),
    )

    with TestClient(app) as client:
        response = client.get("/api/integrations/places/search?q=Chicago")

    assert response.status_code == 503
    assert response.json() == {"detail": "Provider temporarily unavailable"}
