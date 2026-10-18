"""Values computed from stored facts at read time, never stored (they'd go stale)."""

from datetime import UTC, date, datetime, time

from app.db.models import Patient


def age_on(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _years_before(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 February in a non-leap year
        return day.replace(year=day.year - years, day=28)


def inactivity_suggested(patient: Patient, today: date, years: int) -> bool:
    """Active but unseen (or, if never seen, created) over `years` ago. A hint, not a status."""
    if patient.status != "active":
        return False
    cutoff = datetime.combine(_years_before(today, years), time.min, tzinfo=UTC)
    return (patient.last_visit_at or patient.created_at) < cutoff
