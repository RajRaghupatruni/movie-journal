from datetime import date

from pydantic import BaseModel

from app.schemas.memory import MemoryResponse


class AnniversaryResponse(BaseModel):
    memory: MemoryResponse
    years_ago: int
    original_date: date
    anniversary_date: date


class OnThisDayResponse(BaseModel):
    today: date
    timezone: str
    anniversaries: list[AnniversaryResponse]
    fallback: MemoryResponse | None = None
