"""A browser run respects the real quota and never retries refusal or bad evidence."""

from types import SimpleNamespace

import pytest

from ketrika.core.browser_budget import respect_browser_budget


def response(remaining, status=200, limit="60"):
    return SimpleNamespace(
        status=status,
        headers={"x-ratelimit-limit": limit, "x-ratelimit-remaining": str(remaining)},
    )


def test_available_budget_does_not_wait():
    calls = []
    respect_browser_budget(lambda: response(20), {}, "/map", calls.append)
    assert calls == []


def test_low_budget_waits_once_and_requires_recovery():
    replies = iter([response(19), response(59)])
    waits, receipt = [], {}
    respect_browser_budget(lambda: next(replies), receipt, "/map", waits.append)
    assert waits == [60]
    assert receipt == {"rate_budget_waits": [{"stage": "/map", "remaining": 19, "seconds": 60}]}


@pytest.mark.parametrize("status", [401, 429, 503])
def test_error_is_not_retried_or_waited_out(status):
    calls, waits = [], []

    def probe():
        calls.append(1)
        return response(0, status)

    with pytest.raises(RuntimeError, match=f"HTTP {status}"):
        respect_browser_budget(probe, {}, "/map", waits.append)
    assert calls == [1] and waits == []


@pytest.mark.parametrize("value,limit", [(-1, "60"), (60, "60"), (50, "600"), ("unknown", "60")])
def test_invalid_quota_evidence_is_rejected(value, limit):
    with pytest.raises(ValueError):
        respect_browser_budget(lambda: response(value, limit=limit), {}, "/map")


def test_a_window_that_does_not_restore_budget_fails():
    waits = []
    with pytest.raises(RuntimeError, match="did not recover"):
        respect_browser_budget(lambda: response(19), {}, "/map", waits.append)
    assert waits == [60]
