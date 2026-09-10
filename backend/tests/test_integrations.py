import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.integrations.providers import (
    GeoapifyClient,
    ProviderUnavailable,
    TmdbClient,
    normalize_movie,
    normalize_place,
)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+psycopg://fixture:fixture@127.0.0.1:1/fixture",
        tmdb_api_token=SecretStr("tmdb-test-token"),
        geoapify_api_key=SecretStr("geo-test-key"),
    )


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
