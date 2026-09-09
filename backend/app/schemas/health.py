from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    application: Literal["ok"] = "ok"
    database: Literal["ok", "unavailable"]
