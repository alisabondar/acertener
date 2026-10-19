import re
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
    dob: date
    age: int
    status: PatientStatus
    last_visit_at: datetime | None
    archived: bool
    on_my_care_team: bool
    inactivity_suggested: bool
    # Clinical data, so only for roles that may view it; null for everyone else.
    active_problems: list[str] | None


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
    # Clinical, so only for roles that may view clinical data; null for everyone else.
    blood_type: str | None
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


Gender = Literal["female", "male", "nonbinary", "other", "unknown"]
BloodType = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

# Letters in any script, joined by single spaces, hyphens, or apostrophes (straight or curly),
# each part optionally ending in a period: "O'Neil", "Mary-Jane", "Nguyễn", "St. John",
# "Smith Jr.". No digits or symbols.
_NAME = re.compile(r"[^\W\d_]+\.?(?:[ '\u2019-][^\W\d_]+\.?)*")
_MRN = re.compile(r"(?:MRN-)?(\d{1,12})", re.IGNORECASE)
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")
_POSTAL_CODE = re.compile(r"\d{5}(?:-\d{4})?")
_HAS_LETTER_OR_DIGIT = re.compile(r"[^\W_]")
US_STATES = frozenset(
    [
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "DC",
        "AS",
        "GU",
        "MP",
        "PR",
        "VI",
    ]
)


def _collapse(value: str) -> str:
    return " ".join(value.split())


def _check_name(value: str) -> str:
    value = _collapse(value)
    if not _NAME.fullmatch(value):
        raise ValueError("Use letters, with spaces, hyphens, apostrophes, or periods between them")
    return value


def _check_mrn(value: str) -> str:
    """The practice's MRNs are numbers: accept "100234" or "MRN-100234", store "MRN-100234"."""
    match = _MRN.fullmatch(value)
    if not match:
        raise ValueError("Enter the MRN's digits, e.g. 100234")
    return f"MRN-{match.group(1)}"


def _check_phone(value: str) -> str:
    """A US number, in any common format, stored as 555-867-5309."""
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10 or re.search(r"[^\d\s()+.-]", value):
        raise ValueError("Enter a 10-digit phone number, e.g. 555-867-5309")
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"


def _check_email(value: str) -> str:
    if not _EMAIL.fullmatch(value):
        raise ValueError("Enter an email address like name@example.com")
    return value


def _check_state(value: str) -> str:
    if value.upper() not in US_STATES:
        raise ValueError("Use the two-letter state code, e.g. NY")
    return value.upper()


def _check_postal_code(value: str) -> str:
    if not _POSTAL_CODE.fullmatch(value):
        raise ValueError("Use a 5-digit ZIP code, or ZIP+4 (02139-4307)")
    return value


def _check_city(value: str) -> str:
    value = _collapse(value)
    if not _NAME.fullmatch(value):
        raise ValueError("Use letters, with spaces, hyphens, apostrophes, or periods between them")
    return value


def _check_address(value: str) -> str:
    value = _collapse(value)
    if not _HAS_LETTER_OR_DIGIT.search(value):
        raise ValueError("Enter a street address")
    return value


def _limits(max_length: int) -> StringConstraints:
    return StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)


Name = Annotated[str, _limits(100), AfterValidator(_check_name)]
Mrn = Annotated[str, _limits(40), AfterValidator(_check_mrn)]
Phone = Annotated[str, _limits(30), AfterValidator(_check_phone)]
Email = Annotated[str, _limits(254), AfterValidator(_check_email)]
State = Annotated[str, _limits(2), AfterValidator(_check_state)]
PostalCode = Annotated[str, _limits(10), AfterValidator(_check_postal_code)]
City = Annotated[str, _limits(100), AfterValidator(_check_city)]
Address = Annotated[str, _limits(200), AfterValidator(_check_address)]


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
    mrn: Mrn
    dob: Dob
    gender: Gender | None = None
    phone: Phone | None = None
    email: Email | None = None
    address_line1: Address | None = None
    address_line2: Address | None = None
    city: City | None = None
    state: State | None = None
    postal_code: PostalCode | None = None
    blood_type: BloodType | None = None


class PatientReplace(PatientFields):
    """A full replacement (PUT): optional fields that aren't sent are cleared."""

    base_version: int


class PatientCreate(PatientFields):
    """Registration: besides name, DOB, and MRN, administrative sex and a phone number to reach
    the patient are required, as in most practice registration workflows."""

    gender: Gender
    phone: Phone
    confirm_not_duplicate: bool = False


class PatientChanges(BaseModel):
    """A partial update: only the fields that are sent are applied."""

    model_config = ConfigDict(extra="forbid")

    first_name: Name | None = None
    last_name: Name | None = None
    mrn: Mrn | None = None
    dob: Dob | None = None
    gender: Gender | None = None
    phone: Phone | None = None
    email: Email | None = None
    address_line1: Address | None = None
    address_line2: Address | None = None
    city: City | None = None
    state: State | None = None
    postal_code: PostalCode | None = None
    blood_type: BloodType | None = None

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


class StatusChange(BaseModel):
    base_version: int
    status: PatientStatus


class ArchiveRequest(BaseModel):
    base_version: int
    reason: Literal["entered_in_error", "duplicate", "other"]


class RestoreRequest(BaseModel):
    base_version: int
