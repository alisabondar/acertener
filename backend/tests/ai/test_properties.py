"""Property-based: whatever identifiers end up in a note, none may reach an allowed payload."""

import re
import uuid
from datetime import UTC, date, datetime, timedelta

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.ai.deidentify import ChartRecords, NoteRecord, build_context
from app.ai.identifiers import PatientIdentifiers
from app.ai.leak_check import leak_check
from tests.ai.conftest import TODAY

FIRST = ["Rose", "James", "Maria", "Wei", "Aisha", "Daniel", "Grace", "Luis", "Priya", "Tom"]
LAST = ["O'Neil", "Garcia", "Nguyen", "Okafor", "Smith", "Kowalski", "Haddad", "Becker", "Ruiz"]


@st.composite
def patients(draw: st.DrawFn) -> PatientIdentifiers:
    dob = date(1930, 1, 1) + timedelta(days=draw(st.integers(0, 33000)))
    area, mid, end = (
        draw(st.integers(201, 989)),
        draw(st.integers(200, 999)),
        draw(st.integers(0, 9999)),
    )
    first, last = draw(st.sampled_from(FIRST)), draw(st.sampled_from(LAST))
    return PatientIdentifiers(
        patient_id=uuid.UUID(int=draw(st.integers(0, 2**128 - 1)), version=4),
        first_name=first,
        last_name=last,
        mrn=f"MRN-{draw(st.integers(100000, 999999))}",
        dob=dob,
        phone=f"{area}-{mid:03d}-{end:04d}",
        email=f"{first.lower()}.{re.sub(r'[^a-z]', '', last.lower())}@example.org",
        address_line1=f"{draw(st.integers(1, 9999))} Maple Street",
        address_line2=None,
        city="Springfield",
        postal_code=f"{draw(st.integers(10000, 99999))}",
        staff_names=("Wei Chen", "Sam Okafor"),
    )


def _mentions(ids: PatientIdentifiers) -> st.SearchStrategy[str]:
    digits = re.sub(r"\D", "", ids.phone or "")
    d = ids.dob
    return st.sampled_from(
        [
            f"{ids.first_name} {ids.last_name}",
            f"Mr. {ids.last_name}'s",
            ids.last_name.upper(),
            ids.mrn,
            ids.mrn.removeprefix("MRN-"),
            str(ids.patient_id),
            f"{d.month}/{d.day}/{d.year}",
            d.isoformat(),
            d.strftime("%B %-d, %Y"),
            f"({digits[:3]}) {digits[3:6]}-{digits[6:]}",
            f"{digits[:3]}.{digits[3:6]}.{digits[6:]}",
            ids.email or "",
            ids.address_line1 or "",
            f"zip {ids.postal_code}",
        ]
    )


@settings(max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=st.data())
def test_no_identifier_reaches_an_allowed_payload(data: st.DataObject) -> None:
    ids = data.draw(patients())
    mention = data.draw(_mentions(ids))
    note = NoteRecord(
        datetime(2026, 10, 1, 9, tzinfo=UTC), f"Seen today. {mention} reports a cough.", True
    )

    payload = build_context(ids, ChartRecords(sex="female", notes=[note]), TODAY).model_dump_json()

    if leak_check(payload, ids).ok:
        assert mention.lower() not in payload.lower()
