import uuid
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, model_validator


class Scope(StrEnum):
    MY = "my"
    ALL = "all"


class QuickFilter(StrEnum):
    TODAY_VISITS = "today_visits"


class Sort(StrEnum):
    LAST_VISIT = "last_visit"
    AGE = "age"


class Order(StrEnum):
    ASC = "asc"
    DESC = "desc"


class PatientStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DECEASED = "deceased"


class SearchTerms(BaseModel):
    """Identifying search terms. Sent only in a POST body, never in the URL."""

    last_name: str | None = None
    first_name: str | None = None
    dob: date | None = None
    mrn: str | None = None

    @model_validator(mode="after")
    def _needs_an_anchor_field(self) -> "SearchTerms":
        # First name alone is too broad: searches start from something that identifies.
        if self.last_name is None and self.dob is None and self.mrn is None:
            raise ValueError("search needs last_name, dob, or mrn")
        return self


class PatientListItem(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    mrn: str
    age: int
    status: PatientStatus
    last_visit_at: datetime | None
    archived: bool
    on_my_care_team: bool
    inactivity_suggested: bool


class PatientPage(BaseModel):
    items: list[PatientListItem]
    total: int
    page: int
    page_size: int
