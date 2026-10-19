"""Turn one patient's chart into the de-identified context the AI is allowed to see."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from app.ai.identifiers import PatientIdentifiers
from app.ai.payload import DeidentifiedClinicalContext, seal
from app.ai.scrub import scrub

# Sex is not a Safe Harbor identifier and changes clinical reading; other gender values aren't sent.
_SEX = {"female": "female", "male": "male"}


@dataclass(frozen=True)
class VisitRecord:
    scheduled_at: datetime
    reason: str | None
    status: str


@dataclass(frozen=True)
class NoteRecord:
    encounter_at: datetime
    content: str
    final: bool


@dataclass(frozen=True)
class VitalsRecord:
    taken_at: datetime
    bp_systolic: int | None
    bp_diastolic: int | None
    heart_rate: int | None
    respiratory_rate: int | None
    spo2: int | None
    temperature_c: Decimal | None
    weight_kg: Decimal | None
    height_cm: Decimal | None


@dataclass(frozen=True)
class ConditionRecord:
    icd10_code: str
    name: str
    status: str


@dataclass(frozen=True)
class AllergyRecord:
    substance: str
    severity: str | None
    status: str


@dataclass(frozen=True)
class ChartRecords:
    sex: str | None
    visits: list[VisitRecord] = field(default_factory=list)
    notes: list[NoteRecord] = field(default_factory=list)
    vitals: list[VitalsRecord] = field(default_factory=list)
    conditions: list[ConditionRecord] = field(default_factory=list)
    allergies: list[AllergyRecord] = field(default_factory=list)


def _age(dob: date, today: date) -> str:
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return "90+" if years >= 90 else str(years)


def build_context(
    ids: PatientIdentifiers, chart: ChartRecords, today: date
) -> DeidentifiedClinicalContext:
    def offset(moment: datetime) -> int:
        return (moment.date() - today).days

    data = {
        "age": _age(ids.dob, today),
        "sex": _SEX.get(chart.sex or ""),
        "visits": [
            {
                "day_offset": offset(v.scheduled_at),
                "reason": scrub(v.reason, ids, today) if v.reason else None,
                "status": v.status,
            }
            for v in sorted(chart.visits, key=lambda v: v.scheduled_at)
        ],
        # Only finalized notes are part of the record; drafts never leave.
        "notes": [
            {"day_offset": offset(n.encounter_at), "text": scrub(n.content, ids, today)}
            for n in sorted(chart.notes, key=lambda n: n.encounter_at)
            if n.final
        ],
        "vitals": [
            {
                "day_offset": offset(v.taken_at),
                **{
                    name: getattr(v, name)
                    for name in (
                        "bp_systolic",
                        "bp_diastolic",
                        "heart_rate",
                        "respiratory_rate",
                        "spo2",
                        "temperature_c",
                        "weight_kg",
                        "height_cm",
                    )
                },
            }
            for v in sorted(chart.vitals, key=lambda v: v.taken_at)
        ],
        "conditions": [
            {"icd10_code": c.icd10_code, "name": scrub(c.name, ids, today), "status": c.status}
            for c in chart.conditions
            if c.status in ("active", "resolved")
        ],
        # Active allergies as substance and severity only, so a summary can flag a relevant risk.
        "allergies": [
            {"substance": scrub(a.substance, ids, today), "severity": a.severity}
            for a in chart.allergies
            if a.status == "active"
        ],
    }
    return DeidentifiedClinicalContext.model_validate(data, context=seal())
