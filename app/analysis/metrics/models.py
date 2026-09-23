from __future__ import annotations

from pydantic import BaseModel


class Metric(BaseModel):
    name: str
    value: float | None
    confidence: float
    sample_size: int
    status: str = "ok"


class Score(BaseModel):
    name: str
    value: float | None
    confidence: float
    status: str
