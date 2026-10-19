from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import Audit, AuditAction, AuditEntry, get_audit
from app.auth.permissions import Permission, has_permission, require
from app.db.models import User
from app.db.session import get_session
from app.demo.schedule import keep_schedule_current
from app.patients.derived import age_on
from app.patients.queries import practice_today
from app.schemas.patients import Scope
from app.schemas.visits import ScheduledVisitOut, TodaysVisits, VisitPatient
from app.visits.queries import todays_visits

router = APIRouter(prefix="/visits", tags=["visits"])

Scheduler = Annotated[User, Depends(require(Permission.SCHEDULE_VISITS))]


@router.get("/today")
async def today(
    request: Request,
    user: Scheduler,
    session: Annotated[AsyncSession, Depends(get_session)],
    audit: Annotated[Audit, Depends(get_audit)],
    scope: Scope = Scope.MY,
) -> TodaysVisits:
    """Today's schedule at the practice, for the "My day" home page."""
    tz = ZoneInfo(request.app.state.settings.practice_timezone)
    day = practice_today(datetime.now(UTC), tz)
    if request.app.state.settings.demo_mode:
        # Demo data follows the calendar, so a demo left running overnight isn't empty.
        await keep_schedule_current(session, day, tz)
    clinical = has_permission(user, Permission.VIEW_CLINICAL)
    rows = await todays_visits(session, user, scope, day, tz)
    audit.record_read(AuditEntry(AuditAction.VIEW, "todays_visits"))
    return TodaysVisits(
        date=day,
        items=[
            ScheduledVisitOut(
                id=row.visit.id,
                scheduled_at=row.visit.scheduled_at,
                status=row.visit.status,
                provider_name=row.provider_name,
                reason=row.visit.reason if clinical else None,
                patient=VisitPatient(
                    id=row.patient.id,
                    first_name=row.patient.first_name,
                    last_name=row.patient.last_name,
                    dob=row.patient.dob,
                    age=age_on(row.patient.dob, day),
                    mrn=row.patient.mrn,
                ),
            )
            for row in rows
        ],
    )
