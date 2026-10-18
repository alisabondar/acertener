from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.patients.queries import day_bounds, practice_today

NEW_YORK = ZoneInfo("America/New_York")


def test_today_is_the_practices_day_not_utcs() -> None:
    evening_in_new_york = datetime(2026, 10, 18, 0, 30, tzinfo=UTC)  # 8:30pm on the 17th

    assert practice_today(evening_in_new_york, NEW_YORK) == date(2026, 10, 17)


def test_day_bounds_cover_the_practices_whole_day() -> None:
    start, end = day_bounds(date(2026, 10, 17), NEW_YORK)

    assert start == datetime(2026, 10, 17, 4, 0, tzinfo=UTC)
    assert end == datetime(2026, 10, 18, 4, 0, tzinfo=UTC)
