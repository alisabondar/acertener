import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

VisitStatus = Literal["scheduled", "checked_in", "completed", "no_show", "cancelled"]


class VisitPatient(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    dob: date
    age: int
    mrn: str


class ScheduledVisitOut(BaseModel):
    id: uuid.UUID
    scheduled_at: datetime
    status: VisitStatus
    provider_name: str
    # Clinical detail: only for roles that may see clinical data.
    reason: str | None
    patient: VisitPatient


class TodaysVisits(BaseModel):
    date: date
    items: list[ScheduledVisitOut]
