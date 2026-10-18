"""The query behind both patient list endpoints (browse and search)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, Select, and_, exists, func, select
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


def on_care_team(user: User) -> ColumnElement[bool]:
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


@dataclass(frozen=True)
class ListStatements:
    total: Select[int]
    page: Select[Patient, bool]


def build_list_statements(
    session: AsyncSession,
    cipher: FieldCipher,
    user: User,
    params: ListParams,
    today: date,
    tz: ZoneInfo,
    terms: SearchTerms | None = None,
) -> ListStatements:
    """The SQL behind the list endpoints, built but not run (also used by EXPLAIN tooling)."""
    on_team = on_care_team(user)
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
    page = _order_by(
        select(Patient, on_team.label("on_team")).where(*conditions), params.sort, params.order
    )
    return ListStatements(
        total=select(func.count()).select_from(Patient).where(*conditions),
        page=page.offset((params.page - 1) * params.page_size).limit(params.page_size),
    )


async def list_patients(
    session: AsyncSession,
    cipher: FieldCipher,
    user: User,
    params: ListParams,
    today: date,
    tz: ZoneInfo,
    terms: SearchTerms | None = None,
) -> tuple[list[ListedPatient], int]:
    statements = build_list_statements(session, cipher, user, params, today, tz, terms)
    total = await session.scalar(statements.total)
    rows = await session.execute(statements.page)
    return [ListedPatient(p, on) for p, on in rows], total or 0


@dataclass(frozen=True)
class FilterCounts:
    today_visits: int
    status: dict[str, int]
    archived: int


STATUSES = ("active", "inactive", "deceased")


def build_counts_statement(
    user: User, scope: Scope, today: date, tz: ZoneInfo
) -> Select[*tuple[Any, ...]]:
    """Every quick-filter count in one query, using the same conditions as the list."""
    current = Patient.archived_at.is_(None)
    query: Select[*tuple[Any, ...]] = select(
        func.count().filter(and_(current, _visit_on(today, tz))),
        *(func.count().filter(and_(current, Patient.status == s)) for s in STATUSES),
        func.count().filter(Patient.archived_at.is_not(None)),
    ).select_from(Patient)
    if scope is Scope.MY:
        query = query.where(on_care_team(user))
    return query


async def count_filters(
    session: AsyncSession, user: User, scope: Scope, today: date, tz: ZoneInfo
) -> FilterCounts:
    row = (await session.execute(build_counts_statement(user, scope, today, tz))).one()
    today_visits, *by_status, archived = row
    return FilterCounts(today_visits, dict(zip(STATUSES, by_status, strict=True)), archived)
