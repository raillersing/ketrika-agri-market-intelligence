"""Quota model tests are inert, not a proof of PostgreSQL durability."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from ketrika.core.http_budget import Admission, MemoryBudgetBackend, SqlBudgetBackend
from ketrika.core.policy import PolicyStop

NOW = datetime(2026, 10, 14, 23, 59, tzinfo=UTC)
ADMISSION = Admission("fixture_source", "example.invalid", "https://example.invalid", 3, 3, 2)


def test_source_domain_reservation_is_atomic_on_domain_exhaustion():
    backend = MemoryBudgetBackend()
    backend.reserve(replace(ADMISSION, source_id="other", domain_limit=1), NOW)
    with pytest.raises(PolicyStop, match="exhausted"):
        backend.reserve(ADMISSION, NOW)
    assert backend.counts.get(("source", ADMISSION.source_id, NOW.date()), 0) == 0
    assert backend.counts[("domain", ADMISSION.domain, NOW.date())] == 1


def test_source_exhaustion_does_not_consume_domain_and_lower_cap_persists():
    backend = MemoryBudgetBackend()
    backend.reserve(ADMISSION, NOW)
    with pytest.raises(PolicyStop, match="exhausted"):
        backend.reserve(replace(ADMISSION, source_limit=0), NOW)
    with pytest.raises(PolicyStop, match="exhausted"):
        backend.reserve(ADMISSION, NOW)
    assert backend.counts[("domain", ADMISSION.domain, NOW.date())] == 1
    assert backend.limits[("source", ADMISSION.source_id, NOW.date())] == 0


def test_new_utc_day_resets_quota_not_domain_pacing():
    backend = MemoryBudgetBackend()
    now = NOW.replace(hour=23, minute=59, second=59, microsecond=900000)
    assert backend.reserve(replace(ADMISSION, max_rps=1), now) == 0
    assert backend.reserve(replace(ADMISSION, max_rps=1), now + timedelta(seconds=0.2)) == 0.8
    assert len([key for key in backend.counts if key[0] == "domain"]) == 2


def test_parallel_reservations_never_exceed_cap():
    backend = MemoryBudgetBackend()

    def reserve(_):
        try:
            backend.reserve(ADMISSION, NOW)
            return True
        except PolicyStop:
            return False

    with ThreadPoolExecutor(max_workers=12) as pool:
        assert sum(pool.map(reserve, range(40))) == 3
    assert set(backend.counts.values()) == {3}


def test_tighter_rate_cannot_be_increased_by_later_worker():
    backend = MemoryBudgetBackend()
    assert backend.reserve(ADMISSION, NOW) == 0
    assert backend.reserve(replace(ADMISSION, max_rps=0.2), NOW) == 0.5
    assert backend.reserve(replace(ADMISSION, max_rps=100), NOW) == 5.5
    assert backend.pacing[ADMISSION.domain][1] == 0.2


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_limit", -1),
        ("source_limit", True),
        ("domain_limit", -1),
        ("max_rps", 0),
        ("max_rps", float("nan")),
        ("max_rps", float("inf")),
        ("source_id", ""),
        ("domain", ""),
    ],
)
def test_invalid_admission_rejected_without_mutation(field, value):
    backend = MemoryBudgetBackend()
    with pytest.raises(PolicyStop):
        backend.reserve(replace(ADMISSION, **{field: value}), NOW)
    assert not backend.counts and not backend.pacing


def test_timezone_less_clock_rejected():
    with pytest.raises(PolicyStop, match="timezone"):
        MemoryBudgetBackend().reserve(ADMISSION, NOW.replace(tzinfo=None))


@pytest.mark.parametrize("scope", ["source", "origin"])
def test_policy_stop_survives_other_source_or_origin(scope):
    backend = MemoryBudgetBackend()
    backend.stop(ADMISSION.source_id, ADMISSION.origin, 403)
    other = (
        replace(ADMISSION, source_id="other")
        if scope == "origin"
        else replace(ADMISSION, domain="other.invalid", origin="https://other.invalid")
    )
    with pytest.raises(PolicyStop, match="disabled"):
        backend.reserve(other, NOW)
    assert not backend.counts


def test_sql_backend_does_not_create_schema_or_fallback_on_failure():
    engine = MagicMock()
    backend = SqlBudgetBackend(engine)
    engine.assert_not_called()
    engine.begin.assert_not_called()
    engine.begin.side_effect = OperationalError("private credentials", {}, Exception("secret"))
    with pytest.raises(PolicyStop, match="^http_budget_storage_unavailable$") as error:
        backend.reserve(ADMISSION, NOW)
    assert "secret" not in str(error.value) and error.value.__cause__ is None
    with pytest.raises(PolicyStop, match="^http_stop_storage_unavailable$"):
        backend.stop(ADMISSION.source_id, ADMISSION.origin, 403)
