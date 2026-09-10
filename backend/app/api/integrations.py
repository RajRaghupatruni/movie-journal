from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.integrations.providers import (
    GeoapifyClient,
    ProviderClientError,
    ProviderUnavailable,
    TmdbClient,
)
from app.schemas.integrations import MovieSearchResponse, MovieSearchResult, PlaceSearchResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _provider_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProviderClientError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="The provider rejected the request"
        )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Provider temporarily unavailable"
    )


@router.get("/movies/search", response_model=MovieSearchResponse)
def search_movies(
    request: Request,
    q: str = Query(min_length=2, max_length=100),
    _current_user=Depends(get_current_user),
) -> MovieSearchResponse:
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Search for at least two characters")
    try:
        return MovieSearchResponse(items=TmdbClient(request.app.state.settings).search(query))
    except (ProviderClientError, ProviderUnavailable) as exc:
        raise _provider_error(exc) from None


@router.get("/movies/{tmdb_id}", response_model=MovieSearchResult)
def get_movie(
    request: Request, tmdb_id: int, _current_user=Depends(get_current_user)
) -> MovieSearchResult:
    if tmdb_id <= 0:
        raise HTTPException(status_code=422, detail="tmdb_id must be positive")
    try:
        return TmdbClient(request.app.state.settings).get(tmdb_id)
    except (ProviderClientError, ProviderUnavailable) as exc:
        raise _provider_error(exc) from None


@router.get("/places/search", response_model=PlaceSearchResponse)
def search_places(
    request: Request,
    q: str = Query(min_length=2, max_length=100),
    _current_user=Depends(get_current_user),
) -> PlaceSearchResponse:
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Search for at least two characters")
    try:
        return PlaceSearchResponse(items=GeoapifyClient(request.app.state.settings).search(query))
    except (ProviderClientError, ProviderUnavailable) as exc:
        raise _provider_error(exc) from None
