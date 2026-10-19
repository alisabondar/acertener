"""The only shape of data that may leave for an AI provider.

`DeidentifiedClinicalContext` can be built only by the de-identifier (it checks a private seal in
the validation context), so a raw `Patient` or ad-hoc dict can never be passed to the gateway.
"""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationInfo, model_validator

_SEAL = object()


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Visit(_Frozen):
    day_offset: int
    reason: str | None
    status: str


class Note(_Frozen):
    day_offset: int
    text: str


class Vitals(_Frozen):
    day_offset: int
    bp_systolic: int | None
    bp_diastolic: int | None
    heart_rate: int | None
    respiratory_rate: int | None
    spo2: int | None
    temperature_c: Decimal | None
    weight_kg: Decimal | None
    height_cm: Decimal | None


class Diagnosis(_Frozen):
    icd10_code: str
    name: str
    status: Literal["active", "resolved"]


class DeidentifiedClinicalContext(_Frozen):
    # "90+" above 89 (HIPAA Safe Harbor aggregates older ages).
    age: str
    sex: str | None
    visits: list[Visit]
    notes: list[Note]
    vitals: list[Vitals]
    conditions: list[Diagnosis]

    @model_validator(mode="before")
    @classmethod
    def _only_from_the_de_identifier(cls, data: Any, info: ValidationInfo) -> Any:
        if (info.context or {}).get("seal") is not _SEAL:
            raise ValueError("Build this with app.ai.deidentify.build_context")
        return data


def seal() -> dict[str, object]:
    """The validation context that lets the de-identifier build a context. Not for other callers."""
    return {"seal": _SEAL}
