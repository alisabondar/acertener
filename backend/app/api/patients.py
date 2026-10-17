from datetime import UTC, date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import Audit, AuditAction, AuditEntry, get_audit
from app.auth.permissions import Permission, require
from app.db.models import User
from app.db.session import get_session
from app.db.types import get_field_cipher
from app.patients.derived import age_on, inactivity_suggested
from app.patients.queries import ListedPatient, ListParams, list_patients, practice_today
from app.schemas.patients import (
    Order,
    PatientListItem,
    PatientPage,
    PatientStatus,
    QuickFilter,
    Scope,
    SearchTerms,
    Sort,
)

router = APIRouter(prefix="/patients", tags=["patients"])

Viewer = Annotated[User, Depends(require(Permission.VIEW_DEMOGRAPHICS))]
Session = Annotated[AsyncSession, Depends(get_session)]
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
    request: Request, user: Viewer, session: Session, audit: AuditDep, params: Params
) -> PatientPage:
    page = await _page(request, session, user, params, terms=None)
    audit.record_read(AuditEntry(AuditAction.VIEW, "patient_list"))
    return page


@router.post("/search")
async def search(
    request: Request,
    user: Viewer,
    session: Session,
    audit: AuditDep,
    params: Params,
    terms: SearchTerms,
) -> PatientPage:
    """Identifying terms travel in the body; the audit entry never records them."""
    page = await _page(request, session, user, params, terms)
    audit.record_read(AuditEntry(AuditAction.VIEW, "patient_search"))
    return page
