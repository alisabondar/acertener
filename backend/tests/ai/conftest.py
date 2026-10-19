import uuid
from datetime import date

import pytest

from app.ai.identifiers import PatientIdentifiers

TODAY = date(2026, 10, 19)


@pytest.fixture
def ids() -> PatientIdentifiers:
    return PatientIdentifiers(
        patient_id=uuid.UUID("0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"),
        first_name="Rose",
        last_name="O'Neil",
        mrn="MRN-104412",
        dob=date(1956, 3, 4),
        phone="555-867-5309",
        email="rose.oneil@example.org",
        address_line1="742 Evergreen Terrace",
        address_line2=None,
        city="Springfield",
        postal_code="62704",
        staff_names=("Wei Chen", "Sam Okafor"),
    )
