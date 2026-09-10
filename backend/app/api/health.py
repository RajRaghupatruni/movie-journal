import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.health import HealthResponse

router = APIRouter()
liveness_router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
def health(response: Response, db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    """Readiness-compatible compatibility endpoint used by existing local tooling."""
    return _database_readiness(response, db)


@router.get("/readyz", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
def ready(response: Response, db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    return _database_readiness(response, db)


def _database_readiness(response: Response, db: Session) -> HealthResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        db.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError:
        logger.warning("database_unavailable")
        response.status_code = 503
        return HealthResponse(status="degraded", database="unavailable")
    return HealthResponse(status="ok", database="ok")


@liveness_router.get("/healthz", include_in_schema=False)
def liveness(response: Response) -> dict[str, str]:
    """Cheap process liveness check; it intentionally does not touch infrastructure."""
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}
