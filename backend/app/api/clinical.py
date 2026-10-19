import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import Audit, AuditAction, get_audit
from app.auth.permissions import Permission, require
from app.clinical.service import ClinicalService
from app.db.models import Allergy, Condition, Note, User, Vital
from app.db.session import get_session
from app.schemas.clinical import (
    AllergyCreate,
    AllergyOut,
    AllergyUpdate,
    ConditionCreate,
    ConditionOut,
    ConditionUpdate,
    ItemsOut,
    NoteCreate,
    NoteOut,
    NoteUpdate,
    StatusChangeIn,
    VitalsCreate,
    VitalsOut,
)

router = APIRouter(tags=["clinical"])

Session = Annotated[AsyncSession, Depends(get_session)]
AuditDep = Annotated[Audit, Depends(get_audit)]


def _service(permission: Permission) -> Any:
    """The clinical service for a user who holds `permission` (401, then 403, otherwise)."""

    async def dependency(
        user: Annotated[User, Depends(require(permission))], session: Session, audit: AuditDep
    ) -> ClinicalService:
        return ClinicalService(session, user, audit)

    return Depends(dependency)


Reader = Annotated[ClinicalService, _service(Permission.VIEW_CLINICAL)]
NoteWriter = Annotated[ClinicalService, _service(Permission.WRITE_NOTES_AND_VITALS)]
NoteDeleter = Annotated[ClinicalService, _service(Permission.DELETE_OWN_NOTE)]
AllergyEditor = Annotated[ClinicalService, _service(Permission.EDIT_ALLERGIES)]
ConditionEditor = Annotated[ClinicalService, _service(Permission.EDIT_CONDITIONS)]


def _note(note: Note, author_name: str) -> NoteOut:
    return NoteOut(
        id=note.id,
        patient_id=note.patient_id,
        author_id=note.author_id,
        author_name=author_name,
        content=note.content,
        status=note.status,
        encounter_at=note.encounter_at,
        finalized_at=note.finalized_at,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def _vitals(vital: Vital, recorded_by_name: str) -> VitalsOut:
    return VitalsOut.model_validate(
        {
            **{c: getattr(vital, c) for c in VitalsOut.model_fields if c != "recorded_by_name"},
            "recorded_by_name": recorded_by_name,
        }
    )


def _allergy(item: Allergy, name: str) -> AllergyOut:
    return AllergyOut.model_validate(
        {
            **{c: getattr(item, c) for c in AllergyOut.model_fields if c != "recorded_by_name"},
            "recorded_by_name": name,
        }
    )


def _condition(item: Condition, name: str) -> ConditionOut:
    return ConditionOut.model_validate(
        {
            **{c: getattr(item, c) for c in ConditionOut.model_fields if c != "recorded_by_name"},
            "recorded_by_name": name,
        }
    )


# --- Notes ---------------------------------------------------------------------------------


@router.get("/patients/{patient_id}/notes")
async def list_notes(patient_id: uuid.UUID, clinical: Reader) -> ItemsOut[NoteOut]:
    rows = await clinical.notes(patient_id)
    clinical.audit_read("notes", patient_id)
    return ItemsOut(items=[_note(note, name) for note, name in rows])


@router.post("/patients/{patient_id}/notes", status_code=201)
async def create_note(patient_id: uuid.UUID, body: NoteCreate, clinical: NoteWriter) -> NoteOut:
    note = await clinical.create_note(patient_id, body.content, body.encounter_at)
    return _note(note, await clinical.name_of(note.author_id))


@router.patch("/notes/{note_id}")
async def update_note(note_id: uuid.UUID, body: NoteUpdate, clinical: NoteWriter) -> NoteOut:
    note = await clinical.update_note(note_id, body.content)
    return _note(note, await clinical.name_of(note.author_id))


@router.post("/notes/{note_id}/finalize")
async def finalize_note(note_id: uuid.UUID, clinical: NoteWriter) -> NoteOut:
    note = await clinical.finalize_note(note_id)
    return _note(note, await clinical.name_of(note.author_id))


@router.delete("/notes/{note_id}", status_code=204)
async def delete_note(note_id: uuid.UUID, clinical: NoteDeleter) -> Response:
    await clinical.delete_note(note_id)
    return Response(status_code=204)


# --- Vitals --------------------------------------------------------------------------------


@router.get("/patients/{patient_id}/vitals")
async def list_vitals(patient_id: uuid.UUID, clinical: Reader) -> ItemsOut[VitalsOut]:
    rows = await clinical.vitals(patient_id)
    clinical.audit_read("vitals", patient_id)
    return ItemsOut(items=[_vitals(vital, name) for vital, name in rows])


@router.post("/patients/{patient_id}/vitals", status_code=201)
async def record_vitals(
    patient_id: uuid.UUID, body: VitalsCreate, clinical: NoteWriter
) -> VitalsOut:
    vital = await clinical.record_vitals(patient_id, body.model_dump(exclude_none=True))
    return _vitals(vital, await clinical.name_of(vital.recorded_by))


# --- Allergies -----------------------------------------------------------------------------


@router.get("/patients/{patient_id}/allergies")
async def list_allergies(patient_id: uuid.UUID, clinical: Reader) -> ItemsOut[AllergyOut]:
    rows = await clinical.entries(Allergy, patient_id)
    clinical.audit_read("allergies", patient_id)
    return ItemsOut(items=[_allergy(item, name) for item, name in rows])


@router.post("/patients/{patient_id}/allergies", status_code=201)
async def add_allergy(
    patient_id: uuid.UUID, body: AllergyCreate, clinical: AllergyEditor
) -> AllergyOut:
    item = await clinical.add_entry(Allergy, "allergy", patient_id, body.model_dump())
    return _allergy(item, await clinical.name_of(item.recorded_by))


@router.patch("/allergies/{allergy_id}")
async def update_allergy(
    allergy_id: uuid.UUID, body: AllergyUpdate, clinical: AllergyEditor
) -> AllergyOut:
    item = await clinical.update_entry(
        Allergy, "allergy", allergy_id, body.model_dump(exclude_unset=True)
    )
    return _allergy(item, await clinical.name_of(item.recorded_by))


@router.post("/allergies/{allergy_id}/status")
async def change_allergy_status(
    allergy_id: uuid.UUID, body: StatusChangeIn, clinical: AllergyEditor
) -> AllergyOut:
    item = await clinical.update_entry(
        Allergy, "allergy", allergy_id, {"status": body.status}, AuditAction.STATUS_CHANGE
    )
    return _allergy(item, await clinical.name_of(item.recorded_by))


# --- Conditions ----------------------------------------------------------------------------


@router.get("/patients/{patient_id}/conditions")
async def list_conditions(patient_id: uuid.UUID, clinical: Reader) -> ItemsOut[ConditionOut]:
    rows = await clinical.entries(Condition, patient_id)
    clinical.audit_read("conditions", patient_id)
    return ItemsOut(items=[_condition(item, name) for item, name in rows])


@router.post("/patients/{patient_id}/conditions", status_code=201)
async def add_condition(
    patient_id: uuid.UUID, body: ConditionCreate, clinical: ConditionEditor
) -> ConditionOut:
    item = await clinical.add_entry(Condition, "condition", patient_id, body.model_dump())
    return _condition(item, await clinical.name_of(item.recorded_by))


@router.patch("/conditions/{condition_id}")
async def update_condition(
    condition_id: uuid.UUID, body: ConditionUpdate, clinical: ConditionEditor
) -> ConditionOut:
    item = await clinical.update_entry(
        Condition, "condition", condition_id, body.model_dump(exclude_unset=True)
    )
    return _condition(item, await clinical.name_of(item.recorded_by))


@router.post("/conditions/{condition_id}/status")
async def change_condition_status(
    condition_id: uuid.UUID, body: StatusChangeIn, clinical: ConditionEditor
) -> ConditionOut:
    item = await clinical.update_entry(
        Condition, "condition", condition_id, {"status": body.status}, AuditAction.STATUS_CHANGE
    )
    return _condition(item, await clinical.name_of(item.recorded_by))
