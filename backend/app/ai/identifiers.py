import uuid
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class PatientIdentifiers:
    """What identifies one patient (and their care staff), for scrubbing and leak checks."""

    patient_id: uuid.UUID
    first_name: str
    last_name: str
    mrn: str
    dob: date
    phone: str | None
    email: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    postal_code: str | None
    staff_names: tuple[str, ...]
