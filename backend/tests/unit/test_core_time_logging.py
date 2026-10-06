"""Unit tests for ketrika.core.time and ketrika.core.logging."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from ketrika.core.logging import (
    bind_context,
    clear_context,
    get_logger,
    setup_logging,
)
from ketrika.core.time import (
    get_business_tz,
    month_bounds,
    now_utc,
    parse_iso_date,
    to_business_tz,
    to_utc,
)


def test_time_now_utc_has_timezone():
    """Verify now_utc returns timezone-aware UTC datetime."""
    t = now_utc()
    assert t.tzinfo is not None
    assert t.tzinfo == UTC


def test_time_conversions():
    """Verify conversion between UTC and business timezone (Indian/Antananarivo)."""
    biz_tz = get_business_tz()
    assert biz_tz.key == "Indian/Antananarivo"

    # 12:00 UTC = 15:00 UTC+3 in Antananarivo
    dt_utc = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
    dt_biz = to_business_tz(dt_utc)
    assert dt_biz.hour == 15
    assert dt_biz.tzinfo == ZoneInfo("Indian/Antananarivo")

    # Round trip
    dt_back = to_utc(dt_biz)
    assert dt_back.hour == 12
    assert dt_back.tzinfo == UTC


def test_month_bounds():
    """Verify month boundaries for monthly observation normalization."""
    # February in leap year 2024
    start, end = month_bounds(2024, 2)
    assert start == date(2024, 2, 1)
    assert end == date(2024, 2, 29)

    # February in standard year 2025
    start, end = month_bounds(2025, 2)
    assert start == date(2025, 2, 1)
    assert end == date(2025, 2, 28)

    # April (30 days)
    start, end = month_bounds(2025, 4)
    assert start == date(2025, 4, 1)
    assert end == date(2025, 4, 30)


def test_parse_iso_date():
    """Verify ISO date parser."""
    d = parse_iso_date("2025-10-14")
    assert d == date(2025, 10, 14)


def test_logging_configuration_and_binding():
    """Verify structlog configuration and contextual binding."""
    setup_logging()
    logger = get_logger("test_logger")
    assert logger is not None

    bind_context(source_id="test_source", run_id="12345")
    # Log info message with bound context
    logger.info("Test log message", extra_param="value")
    clear_context()
