"""Patient writes. Each one commits the change and its audit entry together, or neither."""

import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.audit import Audit, AuditAction, AuditEntry
from app.crypto import FieldCipher
from app.db.models import CareTeamMember, Patient, User
from app.errors import DuplicateMrnConflictError, PatientNotFoundError, PossibleDuplicateError
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

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[None]:
        """Commit this write with its audit entry; on failure undo only this write.

        A savepoint (not session.rollback()) keeps anything else in the session intact.
        """
        async with self._session.begin_nested():
            yield
        await self._session.commit()

    async def create(self, data: NewPatient, *, confirm_not_duplicate: bool) -> Patient:
        matches = await self._repo.find_likely_duplicates(data.last_name, data.dob)
        if matches and not confirm_not_duplicate:
            raise PossibleDuplicateError(matches=[str(m) for m in matches])
        async with self._transaction():
            try:
                patient = await self._repo.create(data)
            except DuplicateMrnError:
                raise DuplicateMrnConflictError from None
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
        patient = await self._repo.get(patient_id)
        if patient is None:
            raise PatientNotFoundError
        if patient.version != base_version:
            raise StaleVersion(patient)
        diff = {
            name: (getattr(patient, name), value)
            for name, value in changes.items()
            if getattr(patient, name) != value
        }
        if not diff:
            return patient
        new_values = {name: new for name, (_, new) in diff.items()}
        try:
            async with self._transaction():
                try:
                    await self._repo.update(patient_id, **new_values)
                except DuplicateMrnError:
                    raise DuplicateMrnConflictError from None
                await self._audit.record_change(
                    AuditEntry(AuditAction.UPDATE, "patient", patient.id, patient.id, diff)
                )
        except StaleDataError:
            # Another save landed between our read and write. The transaction has been
            # rolled back by now, so the current record can be reloaded for the 409.
            raise StaleVersion(await self._reload(patient_id)) from None
        return patient

    async def _reload(self, patient_id: uuid.UUID) -> Patient:
        patient = await self._session.get(Patient, patient_id, populate_existing=True)
        if patient is None:
            raise PatientNotFoundError
        return patient
