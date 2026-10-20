"""Regression coverage for inherited budget/calendar compatibility, not source proof."""

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from ketrika.core.geo import load_crop_calendar
from ketrika.core.registry import find_repo_root
from ketrika.extraction.llm.budget import BudgetExceededError, BudgetGuard
from ketrika.geo.contracts import load_crop_calendar as load_rich_calendar


@pytest.mark.parametrize("cost", [-1.0, float("nan"), float("inf")])
@pytest.mark.parametrize(
    "method", ["check_can_spend", "check_and_reserve", "record_spend", "rollback_reservation"]
)
def test_invalid_cost_never_changes_budget(cost: float, method: str) -> None:
    guard = BudgetGuard(monthly_limit_usd=10, per_run_limit_usd=10)
    with pytest.raises(BudgetExceededError, match="invalid budget"):
        getattr(guard, method)(cost)
    assert guard.get_monthly_spend() == 0


@pytest.mark.parametrize("limit", [-1.0, float("nan"), float("inf")])
def test_invalid_limits_are_refused(limit: float) -> None:
    with pytest.raises(BudgetExceededError, match="invalid budget"):
        BudgetGuard(monthly_limit_usd=limit)
    with pytest.raises(BudgetExceededError, match="invalid budget"):
        BudgetGuard(per_run_limit_usd=limit)


def test_direct_recording_and_reservation_paths_both_charge() -> None:
    guard = BudgetGuard(monthly_limit_usd=1, per_run_limit_usd=1)
    guard.record_spend(0.6)
    guard.check_and_reserve(0.3)
    assert guard.get_monthly_spend() == pytest.approx(0.9)
    with pytest.raises(BudgetExceededError, match="monthly budget"):
        guard.check_can_spend(0.2)
    guard.rollback_reservation(0.3)
    assert guard.get_monthly_spend() == pytest.approx(0.6)


def test_legacy_calendar_is_strict_baseline_projection_without_mutating_rich_data() -> None:
    path = find_repo_root() / "taxonomy/crop_calendar.yaml"
    before = path.read_bytes()
    rich = load_rich_calendar(path)
    legacy = load_crop_calendar()
    expected = [
        row
        for row in rich
        if row.calendar_type == "traditional_baseline"
        and row.verified
        and row.eligible_for_alerts
        and row.is_active
        and row.superseded_by is None
    ]
    assert len(legacy) == len(expected)
    assert {row.crop_cycle for row in legacy} == {row.crop_cycle for row in expected}
    assert any(row.calendar_type == "seasonal_recommendation" for row in rich)
    assert any(not row.verified for row in rich)
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "bad", [{"unexpected_instructions": "ignored"}, {"planting_start_month": 13}]
)
def test_rich_validation_is_not_bypassed_by_projection(
    tmp_path: Path, bad: dict[str, object]
) -> None:
    row = yaml.safe_load((find_repo_root() / "taxonomy/crop_calendar.yaml").read_text())[0]
    row.update(bad)
    (tmp_path / "crop_calendar.yaml").write_text(json.dumps([row]))
    with pytest.raises(ValidationError):
        load_crop_calendar(tmp_path)


def test_legacy_unverified_flag_is_not_promoted(tmp_path: Path) -> None:
    row = {
        "zone_code": "SYNTHETIC_TEST_ZONE",
        "zone_name": "Synthetic test",
        "crop": "RICE",
        "crop_cycle": "test",
        "planting_months": [1],
        "harvest_months": [6],
        "source": "Synthetic test, not official evidence",
        "verified": False,
    }
    (tmp_path / "crop_calendar.yaml").write_text(json.dumps([row]))
    assert load_crop_calendar(tmp_path)[0].verified is False
