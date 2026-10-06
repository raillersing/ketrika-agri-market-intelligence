"""Time and timezone management utilities for Ketrika."""

import calendar
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from ketrika.core.settings import get_settings


def now_utc() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(UTC)


def get_business_tz() -> ZoneInfo:
    """Return business ZoneInfo (Indian/Antananarivo by default)."""
    settings = get_settings()
    return ZoneInfo(settings.tz_business)


def to_business_tz(dt: datetime) -> datetime:
    """Convert datetime to business timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(get_business_tz())


def to_utc(dt: datetime) -> datetime:
    """Convert datetime to UTC timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_business_tz())
    return dt.astimezone(UTC)


def month_bounds(year: int, month: int) -> tuple[date, date]:
    """Return the first and last date of the given month.

    SPECS §13: For monthly observations, period_start is 1st of month,
    period_end is the last day of the month.
    """
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def parse_iso_date(value: str) -> date:
    """Parse ISO formatted date string (YYYY-MM-DD)."""
    return date.fromisoformat(value)
