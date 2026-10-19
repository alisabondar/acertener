import uuid
from collections.abc import Awaitable
from datetime import UTC, date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import Audit, AuditAction, AuditEntry, changed_fields, get_audit
from app.auth.permissions import Permission, require
from app.db.models import AuditLog, Patient, User
from app.db.session import DbSession
from app.db.types import get_field_cipher
from app.errors import PatientNotFoundError, VersionConflictError
from app.patients.derived import age_on, inactivity_suggested
from app.patients.queries import (
    ListedPatient,
    ListParams,
    count_filters,
    list_patients,
    on_care_team,
    practice_today,
)
from app.patients.repository import NewPatient
from app.patients.service import PatientService, StaleVersion
from app.schemas.patients import (
    AccessLogItem,
    AccessLogPage,
    ArchiveRequest,
    FilterCountsOut,
    Order,
    PatientCreate,
    PatientDetail,
    PatientListItem,
    PatientPage,
    PatientStatus,
    PatientUpdate,
    QuickFilter,
    RestoreRequest,
    Scope,
    SearchTerms,
    Sort,
    StatusChange,
)

router = APIRouter(prefix="/patients", tags=["patients"])

Viewer = Annotated[User, Depends(require(Permission.VIEW_DEMOGRAPHICS))]
AuditDep = Annotated[Audit, Depends(get_audit)]


def list_params(
    scope: Scope = Scope.MY,
    filter: QuickFilter | None = None,
    status: PatientStatus | None = None,
    include_archived: bool = False,
    sort: Sort = Sort.LAST_VISIT,
    order: Order = Order.DESC,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ListParams:
    """Non-identifying list options only; every value comes from an allowlist."""
    return ListParams(scope, filter, status, include_archived, sort, order, page, page_size)


Params = Annotated[ListParams, Depends(list_params)]


def _item(row: ListedPatient, today: date, years: int) -> PatientListItem:
    p = row.patient
    return PatientListItem(
        id=p.id,
        first_name=p.first_name,
        last_name=p.last_name,
        mrn=p.mrn,
        dob=p.dob,
        age=age_on(p.dob, today),
        status=PatientStatus(p.status),
        last_visit_at=p.last_visit_at,
        archived=p.archived_at is not None,
        on_my_care_team=row.on_my_care_team,
        inactivity_suggested=inactivity_suggested(p, today, years),
    )


async def _page(
    request: Request,
    session: AsyncSession,
    user: User,
    params: ListParams,
    terms: SearchTerms | None,
) -> PatientPage:
    tz = ZoneInfo(request.app.state.settings.practice_timezone)
    today = practice_today(datetime.now(UTC), tz)
    rows, total = await list_patients(session, get_field_cipher(), user, params, today, tz, terms)
    years = request.app.state.settings.inactive_after_years
    return PatientPage(
        items=[_item(r, today, years) for r in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("")
async def browse(
    request: Request, user: Viewer, session: DbSession, audit: AuditDep, params: Params
) -> PatientPage:
    page = await _page(request, session, user, params, terms=None)
    audit.record_read(AuditEntry(AuditAction.VIEW, "patient_list"))
    return page


@router.post("/search")
async def search(
    request: Request,
    user: Viewer,
    session: DbSession,
    audit: AuditDep,
    params: Params,
    terms: SearchTerms,
) -> PatientPage:
    """Identifying terms travel in the body; the audit entry never records them."""
    page = await _page(request, session, user, params, terms)
    audit.record_read(AuditEntry(AuditAction.VIEW, "patient_search"))
    return page


@router.get("/filter-counts")
async def filter_counts(
    request: Request, user: Viewer, session: DbSession, audit: AuditDep, scope: Scope = Scope.MY
) -> FilterCountsOut:
    """Counts for the list's quick-filter chips."""
    tz = ZoneInfo(request.app.state.settings.practice_timezone)
    counts = await count_filters(session, user, scope, practice_today(datetime.now(UTC), tz), tz)
    audit.record_read(AuditEntry(AuditAction.VIEW, "patient_counts"))
    return FilterCountsOut(
        today_visits=counts.today_visits,
        status={PatientStatus(k): v for k, v in counts.status.items()},
        archived=counts.archived,
    )


async def _get_patient(session: AsyncSession, patient_id: uuid.UUID) -> Patient:
    patient = await session.get(Patient, patient_id)
    if patient is None:
        raise PatientNotFoundError
    return patient


async def _detail_out(
    request: Request, session: AsyncSession, user: User, patient: Patient
) -> PatientDetail:
    on_team = await session.scalar(select(on_care_team(user)).where(Patient.id == patient.id))
    settings = request.app.state.settings
    today = practice_today(datetime.now(UTC), ZoneInfo(settings.practice_timezone))
    return PatientDetail(
        id=patient.id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        mrn=patient.mrn,
        dob=patient.dob,
        age=age_on(patient.dob, today),
        gender=patient.gender,
        phone=patient.phone,
        email=patient.email,
        address_line1=patient.address_line1,
        address_line2=patient.address_line2,
        city=patient.city,
        state=patient.state,
        postal_code=patient.postal_code,
        status=PatientStatus(patient.status),
        last_visit_at=patient.last_visit_at,
        archived=patient.archived_at is not None,
        archive_reason=patient.archive_reason,
        on_my_care_team=bool(on_team),
        inactivity_suggested=inactivity_suggested(patient, today, settings.inactive_after_years),
        version=patient.version,
    )


@router.get("/{patient_id:uuid}")
async def detail(
    request: Request, patient_id: uuid.UUID, user: Viewer, session: DbSession, audit: AuditDep
) -> PatientDetail:
    patient = await _get_patient(session, patient_id)
    audit.record_read(AuditEntry(AuditAction.VIEW, "patient", patient.id, patient.id))
    return await _detail_out(request, session, user, patient)


@router.post("", status_code=201)
async def create(
    request: Request,
    body: PatientCreate,
    user: Annotated[User, Depends(require(Permission.CREATE_PATIENT))],
    session: DbSession,
    audit: AuditDep,
) -> PatientDetail:
    data = NewPatient(**body.model_dump(exclude={"confirm_not_duplicate"}))
    service = PatientService(session, get_field_cipher(), user, audit)
    patient = await service.create(data, confirm_not_duplicate=body.confirm_not_duplicate)
    return await _detail_out(request, session, user, patient)


@router.patch("/{patient_id:uuid}")
async def update(
    request: Request,
    patient_id: uuid.UUID,
    body: PatientUpdate,
    user: Annotated[User, Depends(require(Permission.EDIT_DEMOGRAPHICS))],
    session: DbSession,
    audit: AuditDep,
) -> PatientDetail:
    """Applies only the fields sent. A stale base_version returns 409 with the current record."""
    service = PatientService(session, get_field_cipher(), user, audit)
    patient = await _saved(
        request,
        session,
        user,
        service.update(patient_id, body.base_version, body.changes.model_dump(exclude_unset=True)),
    )
    return await _detail_out(request, session, user, patient)


async def _saved(
    request: Request, session: AsyncSession, user: User, write: Awaitable[Patient]
) -> Patient:
    """Await a versioned write; a stale base_version becomes a 409 with the current record."""
    try:
        return await write
    except StaleVersion as stale:
        current = await _detail_out(request, session, user, stale.current)
        raise VersionConflictError(current=current.model_dump(mode="json")) from None


StatusChanger = Annotated[User, Depends(require(Permission.CHANGE_PATIENT_STATUS))]
Archiver = Annotated[User, Depends(require(Permission.ARCHIVE_PATIENT))]


@router.post("/{patient_id:uuid}/status")
async def change_status(
    request: Request,
    patient_id: uuid.UUID,
    body: StatusChange,
    user: StatusChanger,
    session: DbSession,
    audit: AuditDep,
) -> PatientDetail:
    service = PatientService(session, get_field_cipher(), user, audit)
    patient = await _saved(
        request, session, user, service.set_status(patient_id, body.base_version, body.status)
    )
    return await _detail_out(request, session, user, patient)


@router.post("/{patient_id:uuid}/archive")
async def archive(
    request: Request,
    patient_id: uuid.UUID,
    body: ArchiveRequest,
    user: Archiver,
    session: DbSession,
    audit: AuditDep,
) -> PatientDetail:
    """Hides the record from lists and search; it stays viewable by id. Nothing is deleted."""
    service = PatientService(session, get_field_cipher(), user, audit)
    patient = await _saved(
        request, session, user, service.archive(patient_id, body.base_version, body.reason)
    )
    return await _detail_out(request, session, user, patient)


@router.post("/{patient_id:uuid}/restore")
async def restore(
    request: Request,
    patient_id: uuid.UUID,
    body: RestoreRequest,
    user: Archiver,
    session: DbSession,
    audit: AuditDep,
) -> PatientDetail:
    service = PatientService(session, get_field_cipher(), user, audit)
    patient = await _saved(request, session, user, service.restore(patient_id, body.base_version))
    return await _detail_out(request, session, user, patient)


@router.get("/{patient_id:uuid}/access-log")
async def access_log(
    patient_id: uuid.UUID,
    _: Annotated[User, Depends(require(Permission.VIEW_PATIENT_ACCESS_LOG))],
    session: DbSession,
    audit: AuditDep,
    before_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AccessLogPage:
    """Who accessed this chart, newest first. Changed field names only, never values."""
    patient = await _get_patient(session, patient_id)
    query = (
        select(AuditLog, User)
        .join(User, AuditLog.actor_id == User.id)
        .where(AuditLog.patient_id == patient.id)
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )
    if before_id is not None:
        query = query.where(AuditLog.id < before_id)
    rows = list(await session.execute(query))
    audit.record_read(AuditEntry(AuditAction.VIEW, "patient_access_log", patient.id, patient.id))
    return AccessLogPage(
        items=[
            AccessLogItem(
                occurred_at=entry.occurred_at,
                actor_name=actor.name,
                actor_role=actor.role,
                via_demo_persona=entry.via_demo_persona,
                action=entry.action,
                changed_fields=changed_fields(entry),
            )
            for entry, actor in rows
        ],
        next_before_id=rows[-1][0].id if len(rows) == limit else None,
    )
