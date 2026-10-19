"""Clinical writes and reads for one patient's chart.

Every write commits with its audit entry and marks the patient's AI summary stale, together.
"""

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import Audit, AuditAction, AuditEntry
from app.db.models import Allergy, Condition, Note, Patient, PatientSummary, User, Vital
from app.db.unit_of_work import transaction
from app.errors import (
    BusinessRuleError,
    InvalidStateError,
    NoteFinalizedError,
    NotFoundError,
    NotNoteAuthorError,
    PatientNotFoundError,
)

ListItem = Allergy | Condition


async def mark_summary_stale(session: AsyncSession, patient_id: uuid.UUID) -> None:
    """Flag the patient's AI summary for regeneration; creates the row if there isn't one."""
    now = datetime.now(UTC)
    statement = insert(PatientSummary).values(
        patient_id=patient_id, status="stale", source_changed_at=now
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[PatientSummary.patient_id],
            set_={"status": "stale", "source_changed_at": now},
        )
    )


class ClinicalService:
    def __init__(self, session: AsyncSession, user: User, audit: Audit) -> None:
        self._session = session
        self._user = user
        self._audit = audit

    # --- Shared -------------------------------------------------------------------------

    async def patient(self, patient_id: uuid.UUID, *, for_write: bool = False) -> Patient:
        patient = await self._session.get(Patient, patient_id)
        if patient is None:
            raise PatientNotFoundError
        if for_write and patient.archived_at is not None:
            raise InvalidStateError("This chart is archived; restore it to add or change entries.")
        return patient

    def audit_read(self, entity: str, patient_id: uuid.UUID) -> None:
        self._audit.record_read(AuditEntry(AuditAction.VIEW, entity, patient_id=patient_id))

    async def _record(
        self,
        action: AuditAction,
        entity: str,
        entity_id: uuid.UUID,
        patient_id: uuid.UUID,
        changes: Mapping[str, tuple[object, object]] | None = None,
        *,
        affects_summary: bool = True,
    ) -> None:
        await self._audit.record_change(AuditEntry(action, entity, entity_id, patient_id, changes))
        # Drafts never reach the AI, so only changes to what it sees make the summary stale.
        if affects_summary:
            await mark_summary_stale(self._session, patient_id)

    # --- Notes ------------------------------------------------------------------------------

    async def notes(self, patient_id: uuid.UUID) -> list[tuple[Note, str]]:
        """Final notes, plus the current user's own drafts; newest first."""
        await self.patient(patient_id)
        rows = await self._session.execute(
            select(Note, User.name)
            .join(User, User.id == Note.author_id)
            .where(
                Note.patient_id == patient_id,
                Note.deleted_at.is_(None),
                or_(
                    Note.status == "final",
                    and_(Note.status == "draft", Note.author_id == self._user.id),
                ),
            )
            .order_by(Note.updated_at.desc(), Note.id)
        )
        return [(note, name) for note, name in rows]

    async def create_note(
        self, patient_id: uuid.UUID, content: str, encounter_at: datetime | None
    ) -> Note:
        await self.patient(patient_id, for_write=True)
        async with transaction(self._session):
            note = Note(
                patient_id=patient_id,
                author_id=self._user.id,
                encounter_at=encounter_at or datetime.now(UTC),
                content=content,
                status="draft",
            )
            self._session.add(note)
            await self._session.flush()
            # Note text is PHI-rich; the audit trail records that it changed, not what it says.
            await self._record(
                AuditAction.CREATE,
                "note",
                note.id,
                patient_id,
                {"status": (None, "draft")},
                affects_summary=False,
            )
        return await self._reload(note)

    async def update_note(self, note_id: uuid.UUID, content: str) -> Note:
        note = await self._own_draft(note_id)
        async with transaction(self._session):
            old_length = len(note.content)
            note.content = content
            await self._record(
                AuditAction.UPDATE,
                "note",
                note.id,
                note.patient_id,
                {"content_length": (old_length, len(content))},
                affects_summary=False,
            )
        return await self._reload(note)

    async def finalize_note(self, note_id: uuid.UUID) -> Note:
        note = await self._own_draft(note_id)
        if not note.content.strip():
            raise BusinessRuleError("Write the note before finalizing it.")
        async with transaction(self._session):
            note.status = "final"
            note.finalized_at = datetime.now(UTC)
            await self._record(
                AuditAction.STATUS_CHANGE,
                "note",
                note.id,
                note.patient_id,
                {"status": ("draft", "final")},
            )
        return await self._reload(note)

    async def delete_note(self, note_id: uuid.UUID, patient_id: uuid.UUID | None = None) -> None:
        """Soft delete; only drafts. A finalized note is part of the record (amend it instead).

        With `patient_id`, the note must belong to that patient (otherwise it's not found).
        """
        note = await self._own_draft(note_id, patient_id)
        async with transaction(self._session):
            note.deleted_at = datetime.now(UTC)
            note.deleted_by = self._user.id
            await self._record(
                AuditAction.DELETE, "note", note.id, note.patient_id, affects_summary=False
            )

    async def _own_draft(self, note_id: uuid.UUID, patient_id: uuid.UUID | None = None) -> Note:
        note = await self._session.get(Note, note_id)
        wrong_patient = (
            patient_id is not None and note is not None and note.patient_id != patient_id
        )
        if note is None or note.deleted_at is not None or wrong_patient:
            raise NotFoundError("Note not found.")
        if note.author_id != self._user.id:
            raise NotNoteAuthorError
        if note.status != "draft":
            raise NoteFinalizedError
        await self.patient(note.patient_id, for_write=True)
        return note

    # --- Vitals ----------------------------------------------------------------------------

    async def vitals(self, patient_id: uuid.UUID) -> list[tuple[Vital, str]]:
        await self.patient(patient_id)
        rows = await self._session.execute(
            select(Vital, User.name)
            .join(User, User.id == Vital.recorded_by)
            .where(Vital.patient_id == patient_id)
            .order_by(Vital.taken_at.desc(), Vital.id)
        )
        return [(vital, name) for vital, name in rows]

    async def record_vitals(self, patient_id: uuid.UUID, values: Mapping[str, Any]) -> Vital:
        await self.patient(patient_id, for_write=True)
        async with transaction(self._session):
            vital = Vital(
                patient_id=patient_id,
                recorded_by=self._user.id,
                taken_at=values.get("taken_at") or datetime.now(UTC),
                **{k: v for k, v in values.items() if k != "taken_at"},
            )
            self._session.add(vital)
            await self._session.flush()
            changes = {k: (None, v) for k, v in values.items() if v is not None and k != "taken_at"}
            await self._record(AuditAction.CREATE, "vitals", vital.id, patient_id, changes)
        return vital

    # --- Allergies & conditions -----------------------------------------------------------

    async def entries[T: ListItem](
        self, model: type[T], patient_id: uuid.UUID
    ) -> list[tuple[T, str]]:
        await self.patient(patient_id)
        rows = await self._session.execute(
            select(model, User.name)
            .join(User, User.id == model.recorded_by)
            .where(model.patient_id == patient_id)
            .order_by(model.created_at.desc(), model.id)
        )
        return [(item, name) for item, name in rows]

    async def add_entry[T: ListItem](
        self, model: type[T], entity: str, patient_id: uuid.UUID, values: Mapping[str, Any]
    ) -> T:
        await self.patient(patient_id, for_write=True)
        async with transaction(self._session):
            item = model(patient_id=patient_id, recorded_by=self._user.id, **values)
            self._session.add(item)
            await self._session.flush()
            changes = {k: (None, v) for k, v in values.items() if v is not None}
            await self._record(AuditAction.CREATE, entity, item.id, patient_id, changes)
        return await self._reload(item)

    async def update_entry[T: ListItem](
        self,
        model: type[T],
        entity: str,
        entry_id: uuid.UUID,
        values: Mapping[str, Any],
        action: AuditAction = AuditAction.UPDATE,
    ) -> T:
        item = await self._session.get(model, entry_id)
        if item is None:
            raise NotFoundError(f"{entity.capitalize()} not found.")
        await self.patient(item.patient_id, for_write=True)
        diff = {k: (getattr(item, k), v) for k, v in values.items() if getattr(item, k) != v}
        if diff:
            async with transaction(self._session):
                for name, (_, new) in diff.items():
                    setattr(item, name, new)
                await self._record(action, entity, item.id, item.patient_id, diff)
        return await self._reload(item)

    async def _reload[T](self, item: T) -> T:
        """Re-read database-set columns (such as `updated_at`) that a write expired."""
        await self._session.refresh(item)
        return item

    async def name_of(self, user_id: uuid.UUID) -> str:
        return await self._name(user_id)

    async def _name(self, user_id: uuid.UUID) -> str:
        user = await self._session.get(User, user_id)
        return user.name if user else "Unknown"
