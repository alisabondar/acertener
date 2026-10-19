import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

NoteStatus = Literal["draft", "final"]
RecordStatus = Literal["active", "resolved", "entered_in_error"]
Severity = Literal["mild", "moderate", "severe"]

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
NoteText = Annotated[str, StringConstraints(max_length=20_000)]
# ICD-10-CM: a letter, two characters, then an optional dot and up to four more.
Icd10 = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_upper=True, pattern=r"^[A-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$"
    ),
]


class ItemsOut[T](BaseModel):
    items: list[T]


# --- Notes ---------------------------------------------------------------------------------


class NoteCreate(BaseModel):
    content: NoteText = ""
    encounter_at: datetime | None = None


class NoteUpdate(BaseModel):
    content: NoteText


class NoteOut(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    author_id: uuid.UUID
    author_name: str
    content: str
    status: NoteStatus
    encounter_at: datetime
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime


# --- Vitals --------------------------------------------------------------------------------

# Physiologic limits: anything outside is a typo, not a patient (e.g. 1200 for 120).
READINGS = (
    "bp_systolic",
    "bp_diastolic",
    "heart_rate",
    "respiratory_rate",
    "spo2",
    "temperature_c",
    "weight_kg",
    "height_cm",
)


class VitalsCreate(BaseModel):
    taken_at: datetime | None = None
    bp_systolic: Annotated[int, Field(ge=50, le=260)] | None = None
    bp_diastolic: Annotated[int, Field(ge=20, le=200)] | None = None
    heart_rate: Annotated[int, Field(ge=20, le=250)] | None = None
    respiratory_rate: Annotated[int, Field(ge=4, le=80)] | None = None
    spo2: Annotated[int, Field(ge=50, le=100)] | None = None
    temperature_c: Annotated[Decimal, Field(ge=30, le=45, decimal_places=1)] | None = None
    weight_kg: Annotated[Decimal, Field(gt=0, le=500, decimal_places=1)] | None = None
    height_cm: Annotated[Decimal, Field(ge=20, le=260, decimal_places=1)] | None = None

    @field_validator("bp_diastolic")
    @classmethod
    def _below_systolic(cls, value: int | None, info: ValidationInfo) -> int | None:
        systolic = info.data.get("bp_systolic")
        if value is not None and systolic is not None and value >= systolic:
            raise ValueError("Diastolic must be lower than systolic")
        return value

    @field_validator("taken_at")
    @classmethod
    def _not_in_the_future(cls, value: datetime | None) -> datetime | None:
        if value is not None and value > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("Vitals can't be taken in the future")
        return value

    @model_validator(mode="after")
    def _has_a_reading(self) -> "VitalsCreate":
        if all(getattr(self, name) is None for name in READINGS):
            raise ValueError("Record at least one reading")
        return self


class VitalsOut(BaseModel):
    id: uuid.UUID
    taken_at: datetime
    recorded_by_name: str
    bp_systolic: int | None
    bp_diastolic: int | None
    heart_rate: int | None
    respiratory_rate: int | None
    spo2: int | None
    temperature_c: Decimal | None
    weight_kg: Decimal | None
    height_cm: Decimal | None


# --- Allergies & conditions -----------------------------------------------------------------


class StatusChangeIn(BaseModel):
    status: RecordStatus


class AllergyCreate(BaseModel):
    substance: Text
    reaction: Text | None = None
    severity: Severity | None = None


def _not_cleared(value: object) -> object:
    # Omitting a field leaves it unchanged; sending null for a required one is a mistake.
    if value is None:
        raise ValueError("This field is required and can't be cleared")
    return value


class AllergyUpdate(BaseModel):
    substance: Text | None = None
    reaction: Text | None = None
    severity: Severity | None = None

    _substance_required = field_validator("substance", mode="before")(_not_cleared)


class AllergyOut(BaseModel):
    id: uuid.UUID
    substance: str
    reaction: str | None
    severity: Severity | None
    status: RecordStatus
    recorded_by_name: str
    created_at: datetime
    updated_at: datetime


class ConditionCreate(BaseModel):
    icd10_code: Icd10
    name: Text
    onset_date: date | None = None

    @field_validator("onset_date")
    @classmethod
    def _onset_not_in_the_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Onset can't be in the future")
        return value


class ConditionUpdate(BaseModel):
    icd10_code: Icd10 | None = None
    name: Text | None = None
    onset_date: date | None = None

    _required = field_validator("icd10_code", "name", mode="before")(_not_cleared)


class ConditionOut(BaseModel):
    id: uuid.UUID
    icd10_code: str
    name: str
    onset_date: date | None
    status: RecordStatus
    recorded_by_name: str
    created_at: datetime
    updated_at: datetime
