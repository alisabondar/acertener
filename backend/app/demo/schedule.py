"""Demo data that keeps up with the calendar.

The seed books "today's" visits on the day it runs. In demo mode, a later day with nothing
booked takes the most recent seeded day's visits instead, at the same clinic times, so My day
never goes empty overnight. Never used outside demo mode.
"""

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Visit
from app.patients.queries import day_bounds

logger = logging.getLogger("app.demo")


async def keep_schedule_current(session: AsyncSession, today: date, tz: ZoneInfo) -> int:
    """Move the latest booked day's visits onto `today` if today has none; returns how many."""
    start, end = day_bounds(today, tz)
    booked_today = await session.scalar(
        select(func.count())
        .select_from(Visit)
        .where(Visit.scheduled_at >= start, Visit.scheduled_at < end)
    )
    latest = await session.scalar(
        select(func.max(Visit.scheduled_at)).where(Visit.scheduled_at < start)
    )
    if booked_today or latest is None:
        return 0

    day_start, day_end = day_bounds(latest.astimezone(tz).date(), tz)
    visits = list(
        await session.scalars(
            select(Visit).where(Visit.scheduled_at >= day_start, Visit.scheduled_at < day_end)
        )
    )
    for visit in visits:
        # Same local clinic time on the new day, even across a daylight-saving change.
        visit.scheduled_at = datetime.combine(today, visit.scheduled_at.astimezone(tz).timetz())
    await session.commit()
    logger.info("demo_schedule_moved_to_today", extra={"ctx": {"visits": len(visits)}})
    return len(visits)
