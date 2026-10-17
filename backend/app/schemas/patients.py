import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
    model_validator,
)


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


class PatientDetail(BaseModel):
    """Demographics and contact details. Clinical data comes from separate, gated endpoints."""

    id: uuid.UUID
    first_name: str
    last_name: str
    mrn: str
    dob: date
    age: int
    gender: str | None
    phone: str | None
    email: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    status: PatientStatus
    last_visit_at: datetime | None
    archived: bool
    archive_reason: str | None
    on_my_care_team: bool
    inactivity_suggested: bool
    version: int


class AccessLogItem(BaseModel):
    occurred_at: datetime
    actor_name: str
    actor_role: str
    via_demo_persona: bool
    action: str
    changed_fields: list[str]


class AccessLogPage(BaseModel):
    items: list[AccessLogItem]
    next_before_id: int | None


class FilterCountsOut(BaseModel):
    today_visits: int
    status: dict[PatientStatus, int]
    archived: int


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Optional = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Gender = Literal["female", "male", "nonbinary", "other", "unknown"]


def _check_dob(dob: date) -> date:
    if dob > date.today():
        raise ValueError("Date of birth can't be in the future")
    if dob.year < 1900:
        raise ValueError("Date of birth is before 1900")
    return dob


Dob = Annotated[date, AfterValidator(_check_dob)]


class PatientFields(BaseModel):
    """Editable demographics and contact details (shape rules only; state rules live in the
    service)."""

    model_config = ConfigDict(extra="forbid")

    first_name: Name
    last_name: Name
    mrn: Name
    dob: Dob
    gender: Gender | None = None
    phone: Optional | None = None
    email: Optional | None = None
    address_line1: Optional | None = None
    address_line2: Optional | None = None
    city: Optional | None = None
    state: Optional | None = None
    postal_code: Optional | None = None


class PatientCreate(PatientFields):
    confirm_not_duplicate: bool = False


class PatientChanges(BaseModel):
    """A partial update: only the fields that are sent are applied."""

    model_config = ConfigDict(extra="forbid")

    first_name: Name | None = None
    last_name: Name | None = None
    mrn: Name | None = None
    dob: Dob | None = None
    gender: Gender | None = None
    phone: Optional | None = None
    email: Optional | None = None
    address_line1: Optional | None = None
    address_line2: Optional | None = None
    city: Optional | None = None
    state: Optional | None = None
    postal_code: Optional | None = None

    @field_validator("first_name", "last_name", "mrn", "dob", mode="before")
    @classmethod
    def _required_fields_stay_set(cls, value: object) -> object:
        # Leaving a field out means "don't change it"; sending null would erase a required value.
        if value is None:
            raise ValueError("this field is required and can't be cleared")
        return value


class PatientUpdate(BaseModel):
    base_version: int
    changes: PatientChanges
