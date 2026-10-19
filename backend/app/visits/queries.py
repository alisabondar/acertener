from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Patient, User, Visit
from app.patients.queries import day_bounds, on_care_team
from app.schemas.patients import Scope


@dataclass(frozen=True)
class ScheduledVisit:
    visit: Visit
    patient: Patient
    provider_name: str


def build_todays_visits_statement(
    user: User, scope: Scope, today: date, tz: ZoneInfo
) -> Select[Visit, Patient, str]:
    """The practice's visits on `today`, in time order (built but not run; also used by EXPLAIN
    tooling). "My" means I'm the provider or on the patient's care team; cancelled visits and
    archived charts are left off the day."""
    start, end = day_bounds(today, tz)
    query = (
        select(Visit, Patient, User.name)
        .join(Patient, Patient.id == Visit.patient_id)
        .join(User, User.id == Visit.provider_id)
        .where(
            Visit.scheduled_at >= start,
            Visit.scheduled_at < end,
            Visit.status != "cancelled",
            Patient.archived_at.is_(None),
        )
        .order_by(Visit.scheduled_at, Visit.id)
    )
    if scope is Scope.MY:
        query = query.where(or_(Visit.provider_id == user.id, on_care_team(user)))
    return query


async def todays_visits(
    session: AsyncSession, user: User, scope: Scope, today: date, tz: ZoneInfo
) -> list[ScheduledVisit]:
    rows = await session.execute(build_todays_visits_statement(user, scope, today, tz))
    return [ScheduledVisit(visit, patient, name) for visit, patient, name in rows]
