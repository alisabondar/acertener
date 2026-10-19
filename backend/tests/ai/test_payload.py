import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.deidentify import (
    AllergyRecord,
    ChartRecords,
    ConditionRecord,
    NoteRecord,
    VisitRecord,
    VitalsRecord,
    build_context,
)
from app.ai.identifiers import PatientIdentifiers
from app.ai.leak_check import leak_check
from app.ai.payload import DeidentifiedClinicalContext
from tests.ai.conftest import TODAY

GOLDEN = Path(__file__).parent / "golden_payload.json"


def _at(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, 14, tzinfo=UTC)


def _records() -> ChartRecords:
    return ChartRecords(
        sex="female",
        visits=[VisitRecord(_at(date(2026, 10, 12)), "Cough and congestion", "completed")],
        notes=[
            NoteRecord(
                _at(date(2026, 10, 12)),
                "Rose O'Neil seen with Dr. Chen. Cough since 10/2/2026. Call (555) 867-5309.",
                final=True,
            ),
            NoteRecord(_at(date(2026, 10, 13)), "Draft that was never finalized.", final=False),
        ],
        vitals=[
            VitalsRecord(
                _at(date(2026, 10, 12)), 142, 88, 76, None, 98, Decimal("37.1"), None, None
            )
        ],
        conditions=[
            ConditionRecord("I10", "Essential hypertension", "active"),
            ConditionRecord("J45.909", "Asthma", "entered_in_error"),
        ],
        allergies=[
            AllergyRecord("Lisinopril", "severe", "active"),
            AllergyRecord("Latex", "mild", "resolved"),
        ],
    )


def test_holds_only_de_identified_clinical_context(ids: PatientIdentifiers) -> None:
    context = build_context(ids, _records(), TODAY)

    assert context.age == "70"
    assert context.sex == "female"
    assert [v.day_offset for v in context.visits] == [-7]
    assert [n.text for n in context.notes] == [
        "[PATIENT] seen with [CLINICIAN]. Cough since [DATE -17d]. Call [REDACTED]."
    ]
    assert [c.icd10_code for c in context.conditions] == ["I10"]
    # Active allergies only, as substance and severity: what a summary needs to flag a risk.
    assert [(a.substance, a.severity) for a in context.allergies] == [("Lisinopril", "severe")]
    assert leak_check(context.model_dump_json(), ids, context.clinical_terms()).ok


def test_ages_over_89_are_sent_as_90_plus(ids: PatientIdentifiers) -> None:
    older = PatientIdentifiers(**{**vars(ids), "dob": date(1930, 1, 1)})

    assert build_context(older, _records(), TODAY).age == "90+"


def test_cannot_be_built_except_by_the_de_identifier() -> None:
    with pytest.raises(ValidationError):
        DeidentifiedClinicalContext(
            age="40", sex=None, visits=[], notes=[], vitals=[], conditions=[], allergies=[]
        )


@pytest.mark.privacy
def test_the_exact_outbound_payload_is_reviewed_in_code(ids: PatientIdentifiers) -> None:
    """Golden snapshot: any change to what's sent to the AI shows up as a diff in review."""
    payload = json.loads(build_context(ids, _records(), TODAY).model_dump_json())

    assert payload == json.loads(GOLDEN.read_text())
