"""The query behind both patient list endpoints (browse and search)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, Select, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import FieldCipher
from app.db.models import CareTeamMember, Patient, User, Visit
from app.patients.repository import PatientRepository
from app.schemas.patients import Order, QuickFilter, Scope, SearchTerms, Sort


@dataclass(frozen=True)
class ListParams:
    scope: Scope
    filter: QuickFilter | None
    status: str | None
    include_archived: bool
    sort: Sort
    order: Order
    page: int
    page_size: int


@dataclass(frozen=True)
class ListedPatient:
    patient: Patient
    on_my_care_team: bool


def _on_care_team(user: User) -> ColumnElement[bool]:
    return exists().where(
        CareTeamMember.patient_id == Patient.id,
        CareTeamMember.user_id == user.id,
        CareTeamMember.end_date.is_(None),
    )


def practice_today(now: datetime, tz: ZoneInfo) -> date:
    """The calendar day at the practice, which is what "today" means to clinicians."""
    return now.astimezone(tz).date()


def day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[start, end) of a practice-local day, in UTC."""
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def _visit_on(day: date, tz: ZoneInfo) -> ColumnElement[bool]:
    start, end = day_bounds(day, tz)
    return exists().where(
        Visit.patient_id == Patient.id, Visit.scheduled_at >= start, Visit.scheduled_at < end
    )


def _order_by(query: Select[Patient, bool], sort: Sort, order: Order) -> Select[Patient, bool]:
    if sort is Sort.LAST_VISIT:
        visit = Patient.last_visit_at.desc() if order is Order.DESC else Patient.last_visit_at.asc()
        return query.order_by(visit.nulls_last(), Patient.id)
    # Age sorts by plaintext birth_year (DOB is encrypted); youngest first = latest year first.
    year = Patient.birth_year.desc() if order is Order.ASC else Patient.birth_year.asc()
    return query.order_by(year, Patient.dob_fp, Patient.id)


async def list_patients(
    session: AsyncSession,
    cipher: FieldCipher,
    user: User,
    params: ListParams,
    today: date,
    tz: ZoneInfo,
    terms: SearchTerms | None = None,
) -> tuple[list[ListedPatient], int]:
    on_team = _on_care_team(user)
    conditions: list[ColumnElement[bool]] = []
    if params.scope is Scope.MY:
        conditions.append(on_team)
    if params.filter is QuickFilter.TODAY_VISITS:
        conditions.append(_visit_on(today, tz))
    if params.status is not None:
        conditions.append(Patient.status == params.status)
    if not params.include_archived:
        conditions.append(Patient.archived_at.is_(None))
    if terms is not None:
        conditions += PatientRepository(session, cipher).search_conditions(
            terms.last_name, terms.first_name, terms.dob, terms.mrn
        )

    total = await session.scalar(select(func.count()).select_from(Patient).where(*conditions))
    query = _order_by(
        select(Patient, on_team.label("on_team")).where(*conditions), params.sort, params.order
    )
    rows = await session.execute(
        query.offset((params.page - 1) * params.page_size).limit(params.page_size)
    )
    return [ListedPatient(p, on) for p, on in rows], total or 0
