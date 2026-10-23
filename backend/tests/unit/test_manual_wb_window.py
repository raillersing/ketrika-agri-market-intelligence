"""Bounded acquisition selection; these tests do not qualify publisher data."""

from datetime import UTC, date, datetime
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from ketrika.connectors import manual_wb
from ketrika.connectors.base import RunContext
from ketrika.connectors.manual_wb import DATA_URL, recent_rice_history_url


@pytest.mark.parametrize("as_of", [date(2026, 1, 1), date(2024, 2, 29), date(2026, 12, 31)])
def test_selection_is_monthly_bounded_and_never_future(as_of):
    url = urlsplit(recent_rice_history_url(as_of))
    query = parse_qs(url.query)
    periods = [date.fromisoformat(value) for value in query["c[price_date]"][0].split(",")]
    assert url.scheme == "https"
    assert url.netloc == "microdata.worldbank.org"
    assert url.path == "/api/tables/data/fcv/wld_2021_rtfp_v02_m"
    assert query["limit"] == ["120"]
    assert query["c[ISO3]"] == ["MDG"]
    assert query["c[c_rice]"] == [">0"]
    assert len(periods) == 72 + as_of.month
    assert len(set(periods)) == len(periods) <= 84
    assert periods[0] == date(as_of.year - 6, 1, 1)
    assert periods[-1] == as_of.replace(day=1)
    assert all(period.day == 1 and period <= as_of for period in periods)
    assert all(
        right.year * 12 + right.month == left.year * 12 + left.month + 1
        for left, right in zip(periods, periods[1:], strict=False)
    )
    assert {"c_rice", "currency", "price_date", "mkt_name"} <= set(query["fields"][0].split(","))


def test_same_month_has_same_url_and_legacy_url_stays_available():
    assert recent_rice_history_url(date(2026, 10, 1)) == recent_rice_history_url(date(2026, 10, 31))
    query = parse_qs(urlsplit(DATA_URL).query)
    assert query["limit"] == ["15"]
    assert "c[price_date]" not in query


def test_manual_discovery_uses_utc_window_and_keeps_official_context(monkeypatch):
    clock = Mock()
    clock.now.return_value = datetime(2026, 10, 31, 23, 30, tzinfo=UTC)
    monkeypatch.setattr(manual_wb, "datetime", clock)
    items = list(manual_wb.ManualWbConnector().discover(Mock(spec=RunContext)))
    assert [item.url for item in items] == [
        manual_wb.STUDY_URL,
        recent_rice_history_url(date(2026, 10, 31)),
    ]
    clock.now.assert_called_once_with(UTC)
