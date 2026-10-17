"""All ORM models. Importing this package registers every table on `Base.metadata`."""

from app.db.models.base import Base
from app.db.models.clinical import Allergy, Condition, Note, PatientSummary
from app.db.models.patients import Patient, PatientNamePrefix
from app.db.models.scheduling import CareTeamMember, Visit, Vital
from app.db.models.staff import User

__all__ = [
    "Allergy",
    "Base",
    "CareTeamMember",
    "Condition",
    "Note",
    "Patient",
    "PatientNamePrefix",
    "PatientSummary",
    "User",
    "Visit",
    "Vital",
]
