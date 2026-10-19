"""Patient writes. Each one commits the change and its audit entry together, or neither."""

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.audit import Audit, AuditAction, AuditEntry
from app.crypto import FieldCipher
from app.db.models import CareTeamMember, Patient, User
from app.db.unit_of_work import transaction
from app.errors import (
    DuplicateMrnConflictError,
    InvalidStateError,
    PatientNotFoundError,
    PossibleDuplicateError,
)
from app.patients.repository import DuplicateMrnError, NewPatient, PatientRepository

# Who joins a new patient's care team when they register them.
CREATOR_CARE_TEAM_ROLES = {"provider": "provider", "nurse": "nurse"}


class StaleVersion(Exception):  # noqa: N818 (a condition, not an error)
    """The client edited an older version; carries the current record for the 409."""

    def __init__(self, current: Patient) -> None:
        super().__init__("stale base_version")
        self.current = current


class PatientService:
    def __init__(
        self, session: AsyncSession, cipher: FieldCipher, user: User, audit: Audit
    ) -> None:
        self._session = session
        self._cipher = cipher
        self._repo = PatientRepository(session, cipher)
        self._user = user
        self._audit = audit

    async def create(self, data: NewPatient, *, confirm_not_duplicate: bool) -> Patient:
        matches = await self._repo.find_likely_duplicates(data.last_name, data.dob)
        if matches and not confirm_not_duplicate:
            raise PossibleDuplicateError(matches=[str(m) for m in matches])
        async with transaction(self._session):
            try:
                patient = await self._repo.create(data)
            except DuplicateMrnError:
                raise await self._mrn_taken(data.mrn) from None
            if role := CREATOR_CARE_TEAM_ROLES.get(self._user.role):
                self._session.add(
                    CareTeamMember(patient_id=patient.id, user_id=self._user.id, role=role)
                )
            changes: dict[str, tuple[object, object]] = {
                name: (None, value) for name, value in vars(data).items() if value is not None
            }
            if matches:
                changes["duplicate_override"] = (None, [str(m) for m in matches])
            await self._audit.record_change(
                AuditEntry(AuditAction.CREATE, "patient", patient.id, patient.id, changes)
            )
        return patient

    async def update(
        self, patient_id: uuid.UUID, base_version: int, changes: Mapping[str, Any]
    ) -> Patient:
        patient = await self._load(patient_id, base_version)
        return await self._apply(patient, changes, AuditAction.UPDATE)

    async def set_status(self, patient_id: uuid.UUID, base_version: int, status: str) -> Patient:
        patient = await self._load(patient_id, base_version)
        return await self._apply(patient, {"status": status}, AuditAction.STATUS_CHANGE)

    async def archive(self, patient_id: uuid.UUID, base_version: int, reason: str) -> Patient:
        patient = await self._load(patient_id, base_version)
        if patient.archived_at is not None:
            raise InvalidStateError("This patient is already archived.")
        values = {
            "archived_at": datetime.now(UTC),
            "archived_by": self._user.id,
            "archive_reason": reason,
        }
        return await self._apply(patient, values, AuditAction.ARCHIVE)

    async def restore(self, patient_id: uuid.UUID, base_version: int) -> Patient:
        patient = await self._load(patient_id, base_version)
        if patient.archived_at is None:
            raise InvalidStateError("This patient isn't archived.")
        values = {"archived_at": None, "archived_by": None, "archive_reason": None}
        return await self._apply(patient, values, AuditAction.RESTORE)

    async def _load(self, patient_id: uuid.UUID, base_version: int) -> Patient:
        patient = await self._repo.get(patient_id)
        if patient is None:
            raise PatientNotFoundError
        if patient.version != base_version:
            raise StaleVersion(patient)
        return patient

    async def _apply(
        self, patient: Patient, values: Mapping[str, Any], action: AuditAction
    ) -> Patient:
        """Apply only the values that differ, audited with old -> new, in one savepoint."""
        diff = {
            name: (getattr(patient, name), value)
            for name, value in values.items()
            if getattr(patient, name) != value
        }
        if not diff:
            return patient
        new_values = {name: new for name, (_, new) in diff.items()}
        try:
            async with transaction(self._session):
                try:
                    await self._repo.update(patient.id, **new_values)
                except DuplicateMrnError:
                    raise await self._mrn_taken(new_values["mrn"]) from None
                await self._audit.record_change(
                    AuditEntry(action, "patient", patient.id, patient.id, diff)
                )
        except StaleDataError:
            # Another save landed between our read and write. The savepoint has been
            # rolled back by now, so the current record can be reloaded for the 409.
            raise StaleVersion(await self._reload(patient.id)) from None
        return patient

    async def _reload(self, patient_id: uuid.UUID) -> Patient:
        patient = await self._session.get(Patient, patient_id, populate_existing=True)
        if patient is None:
            raise PatientNotFoundError
        return patient

    async def _mrn_taken(self, mrn: str) -> DuplicateMrnConflictError:
        """The conflict, naming (by id only) the patient who already has the MRN."""
        holder = await self._repo.find_by_mrn(mrn)
        return DuplicateMrnConflictError(matches=[str(holder)] if holder else [])
