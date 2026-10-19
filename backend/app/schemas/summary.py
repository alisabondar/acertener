from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.schemas.clinical import Severity

SummaryStatus = Literal["fresh", "stale", "generating", "failed", "blocked"]


class SummaryAllergy(BaseModel):
    substance: str
    severity: Severity | None


class SummaryCondition(BaseModel):
    icd10_code: str
    name: str


class SummaryHeader(BaseModel):
    """Straight from the chart, never from the AI, so it's always available and exact."""

    allergies: list[SummaryAllergy]
    conditions: list[SummaryCondition]


class SummaryOut(BaseModel):
    header: SummaryHeader
    status: SummaryStatus
    narrative: str | None
    is_ai_generated: bool
    provider: str | None
    generated_at: datetime | None
    next_refresh_at: datetime | None
    error_code: str | None


class LeakCheckOut(BaseModel):
    ok: bool
    detectors: list[str]


class PayloadPreview(BaseModel):
    payload: dict[str, Any]
    leak_check: LeakCheckOut
    provider: str
