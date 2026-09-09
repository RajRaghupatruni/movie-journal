import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.health import HealthResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
def health(response: Response, db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        db.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError:
        logger.warning("database_unavailable")
        response.status_code = 503
        return HealthResponse(status="degraded", database="unavailable")
    return HealthResponse(status="ok", database="ok")
