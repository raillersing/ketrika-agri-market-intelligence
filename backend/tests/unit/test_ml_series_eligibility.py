"""Unit tests for price series eligibility, calendar integrity, and exclusion reporting (SPECS §17, ADR-004, ADR-073, R3.1)."""

from __future__ import annotations

import uuid
from datetime import date

import numpy as np
import pytest

from ketrika.ml.series import (
    DEFAULT_QUALITY_GRADE,
    DEFAULT_UNIT,
    build_series_key,
    evaluate_series_eligibility_records,
    generate_monthly_calendar,
    parse_series_key,
    shift_months,
)


def test_series_key_construction_and_parsing():
    """Verify canonical 5-component series key and backwards-compatible legacy parsing."""
    key = build_series_key(
        product_code="rice_milled",
        quality_grade="standard",
        actor_level="retail",
        location_pcode="MG11",
        unit="kg",
    )
    assert key == "rice_milled|standard|retail|MG11|kg"

    parsed = parse_series_key(key)
    assert parsed["product_code"] == "rice_milled"
    assert parsed["quality_grade"] == "standard"
    assert parsed["actor_level"] == "retail"
    assert parsed["location_pcode"] == "MG11"
    assert parsed["unit"] == "kg"

    # Legacy 3-part format: product_code|location_pcode|actor_level
    legacy_key = "rice_milled|MG11|retail"
    legacy_parsed = parse_series_key(legacy_key)
    assert legacy_parsed["product_code"] == "rice_milled"
    assert legacy_parsed["quality_grade"] == DEFAULT_QUALITY_GRADE
    assert legacy_parsed["actor_level"] == "retail"
    assert legacy_parsed["location_pcode"] == "MG11"
    assert legacy_parsed["unit"] == DEFAULT_UNIT

    with pytest.raises(ValueError, match="Invalid series_key format"):
        parse_series_key("invalid_key_with_two_parts|only")


def test_calendar_shift_and_generation():
    """Verify exact monthly calendar generation and shift arithmetic."""
    base = date(2024, 3, 1)
    # 24 months inclusive window: 2024-03 minus 23 months = 2022-04
    start_24m = shift_months(base, -23)
    assert start_24m == date(2022, 4, 1)

    cal = generate_monthly_calendar(date(2023, 10, 1), date(2024, 2, 1))
    assert len(cal) == 5
    assert cal == [
        date(2023, 10, 1),
        date(2023, 11, 1),
        date(2023, 12, 1),
        date(2024, 1, 1),
        date(2024, 2, 1),
    ]


def _build_synthetic_monthly_records(
    product_code: str = "rice_milled",
    location_pcode: str = "MG11",
    admin_level: int = 1,
    actor_level: str = "retail",
    months_count: int = 36,
    end_date: date = date(2024, 3, 1),
    observed_or_imputed: str = "observed",
    skip_months: set[int] | None = None,
) -> list[dict]:
    """Helper to generate sequential monthly observation records."""
    records = []
    prod_id = uuid.uuid4()
    loc_id = uuid.uuid4()
    # Build list of 1st-of-month dates backwards from end_date
    dates = [shift_months(end_date, -i) for i in reversed(range(months_count))]
    for idx, m in enumerate(dates):
        if skip_months and idx in skip_months:
            continue
        records.append(
            {
                "product_id": prod_id,
                "product_code": product_code,
                "product_name": "Riz blanc",
                "location_id": loc_id,
                "location_pcode": location_pcode,
                "location_name": "Analamanga",
                "admin_level": admin_level,
                "actor_level": actor_level,
                "month": m,
                "median_price": 2500.0 + idx * 10.0,
                "observed_or_imputed": observed_or_imputed,
                "chosen_source_id": "miasa_odr",
                "chosen_source_family": "odr",
            }
        )
    return records


def test_rejection_of_insufficient_points_35():
    """Verify that a series with 35 points is strictly rejected (criterion: 35 points refusés)."""
    cutoff = date(2024, 3, 31)
    records = _build_synthetic_monthly_records(months_count=35, end_date=date(2024, 3, 1))

    report = evaluate_series_eligibility_records(records, data_cutoff=cutoff)
    assert report.eligible_count == 0
    assert report.excluded_count == 1
    assert "insufficient_total_points" in report.summary_reasons

    excluded = report.excluded_series[0]
    assert excluded.total_valid_points == 35
    assert any("35 points < 36 required" in r for r in excluded.reasons)


def test_acceptance_of_36_points_with_sufficient_recency():
    """Verify that a series with 36 points and >= 12 recent points is accepted."""
    cutoff = date(2024, 3, 31)
    records = _build_synthetic_monthly_records(months_count=36, end_date=date(2024, 3, 1))

    report = evaluate_series_eligibility_records(records, data_cutoff=cutoff)
    assert report.eligible_count == 1
    assert report.excluded_count == 0

    s = report.eligible_series[0]
    assert s.total_valid_points == 36
    assert s.recent_points_24m == 24  # All last 24 months present
    assert s.coverage_ratio == 1.0
    assert s.can_backtest_6_windows is True
    assert s.can_calibrate_conformal is True


def test_rejection_of_36_points_lacking_recency():
    """Verify that 36 points without sufficient recent observations is rejected (criterion: 36 points sans récence refusés)."""
    cutoff = date(2024, 3, 31)
    # Generate 40 total points, but stop observations 16 months before cutoff
    # so that only 8 observations fall within the 24-month window
    end_point = date(2022, 11, 1)  # Only Nov 2022 to Apr 2022 in last 24m (8 points)
    records = _build_synthetic_monthly_records(months_count=36, end_date=end_point)

    report = evaluate_series_eligibility_records(records, data_cutoff=cutoff)
    assert report.eligible_count == 0
    assert report.excluded_count == 1
    assert "insufficient_recency" in report.summary_reasons

    excluded = report.excluded_series[0]
    assert excluded.total_valid_points == 36
    assert excluded.recent_points_24m < 12
    assert any("insufficient_recency" in r for r in excluded.reasons)


def test_rejection_of_district_granularity_admin_level_2():
    """Verify district granularity (admin_level=2) is rejected per ADR-004."""
    cutoff = date(2024, 3, 31)
    records = _build_synthetic_monthly_records(
        location_pcode="MG1101",
        admin_level=2,  # District level
        months_count=40,
        end_date=date(2024, 3, 1),
    )

    report = evaluate_series_eligibility_records(records, data_cutoff=cutoff)
    assert report.eligible_count == 0
    assert report.excluded_count == 1
    assert "ineligible_geo_granularity" in report.summary_reasons

    excluded = report.excluded_series[0]
    assert any("districts admin_level=2 rejected" in r for r in excluded.reasons)


def test_rejection_of_commune_granularity_admin_level_3():
    """Verify commune granularity (admin_level=3) is rejected."""
    cutoff = date(2024, 3, 31)
    records = _build_synthetic_monthly_records(
        location_pcode="MG110101",
        admin_level=3,  # Commune level
        months_count=40,
        end_date=date(2024, 3, 1),
    )

    report = evaluate_series_eligibility_records(records, data_cutoff=cutoff)
    assert report.eligible_count == 0
    assert report.excluded_count == 1
    assert "ineligible_geo_granularity" in report.summary_reasons


def test_acceptance_of_national_and_regional_granularity():
    """Verify regional (admin_level=1) and national (admin_level=0) series are eligible."""
    cutoff = date(2024, 3, 31)
    rec_reg = _build_synthetic_monthly_records(
        location_pcode="MG11",
        admin_level=1,
        months_count=36,
        end_date=date(2024, 3, 1),
    )
    rec_nat = _build_synthetic_monthly_records(
        location_pcode="MG",
        admin_level=0,
        months_count=36,
        end_date=date(2024, 3, 1),
    )

    report = evaluate_series_eligibility_records(rec_reg + rec_nat, data_cutoff=cutoff)
    assert report.eligible_count == 2
    assert report.excluded_count == 0
    pcodes = {s.location_pcode for s in report.eligible_series}
    assert pcodes == {"MG11", "MG"}


def test_rejection_of_regulated_prices_and_indices():
    """Verify regulated prices (official_ppn, administered) are excluded from market price forecasting."""
    cutoff = date(2024, 3, 31)
    rec_ppn = _build_synthetic_monthly_records(
        actor_level="official_ppn",
        months_count=36,
        end_date=date(2024, 3, 1),
    )
    rec_admin = _build_synthetic_monthly_records(
        actor_level="administered",
        months_count=36,
        end_date=date(2024, 3, 1),
    )

    report = evaluate_series_eligibility_records(rec_ppn + rec_admin, data_cutoff=cutoff)
    assert report.eligible_count == 0
    assert report.excluded_count == 2
    assert "forbidden_price_type" in report.summary_reasons


def test_calendar_grid_explicit_holes_not_compressed():
    """Verify holes in calendar grid are explicit (price=None, np.nan) and never compressed."""
    cutoff = date(2024, 3, 31)
    # Generate 40 months with months at indices 10, 11, 25 skipped (holes)
    skipped = {10, 11, 25}
    records = _build_synthetic_monthly_records(
        months_count=40,
        end_date=date(2024, 3, 1),
        skip_months=skipped,
    )
    # 40 - 3 = 37 valid points -> eligible!
    report = evaluate_series_eligibility_records(records, data_cutoff=cutoff)
    assert report.eligible_count == 1

    s = report.eligible_series[0]
    assert s.total_valid_points == 37
    assert len(s.grid) == 40  # Full continuous calendar span!
    assert len(s.points) == 37  # Non-null points

    # Check that holes exist explicitly in grid
    holes = [pt for pt in s.grid if pt.price is None]
    assert len(holes) == 3
    for h in holes:
        assert h.price is None
        assert h.observed_or_imputed is None
        assert h.is_observed is False
        assert h.is_valid is False

    # Check numpy array conversions
    arr_none = s.to_numpy_array(fill_strategy="none")
    assert len(arr_none) == 40
    assert np.isnan(arr_none).sum() == 3

    # Check forward fill
    arr_ff = s.to_numpy_array(fill_strategy="forward_fill")
    assert len(arr_ff) == 40
    assert not np.any(np.isnan(arr_ff))
    # Filled value at skipped index 10 must equal value at index 9
    assert arr_ff[10] == arr_ff[9]

    # Check linear interpolation
    arr_lin = s.to_numpy_array(fill_strategy="linear")
    assert len(arr_lin) == 40
    assert not np.any(np.isnan(arr_lin))


def test_cohort_separation_observed_vs_mixed():
    """Verify cohort separation between pure observed series and mixed/estimated series."""
    cutoff = date(2024, 3, 31)
    rec_obs = _build_synthetic_monthly_records(
        product_code="rice_milled",
        location_pcode="MG11",
        months_count=36,
        end_date=date(2024, 3, 1),
        observed_or_imputed="observed",
    )
    rec_mixed = _build_synthetic_monthly_records(
        product_code="maize",
        location_pcode="MG11",
        months_count=36,
        end_date=date(2024, 3, 1),
        observed_or_imputed="imputed",
    )

    # In standard mode, both eligible, with distinct cohort tags
    report = evaluate_series_eligibility_records(rec_obs + rec_mixed, data_cutoff=cutoff)
    assert report.eligible_count == 2
    cohorts = {s.product_code: s.cohort for s in report.eligible_series}
    assert cohorts["rice_milled"] == "observed"
    assert cohorts["maize"] == "mixed"

    # In strict evaluation ground-truth mode, mixed must be excluded
    report_strict = evaluate_series_eligibility_records(
        rec_obs + rec_mixed,
        data_cutoff=cutoff,
        require_observed_only=True,
    )
    assert report_strict.eligible_count == 1
    assert report_strict.excluded_count == 1
    assert report_strict.eligible_series[0].product_code == "rice_milled"
    assert "ineligible_cohort" in report_strict.summary_reasons


def test_protocol_capacities_flags():
    """Verify capacity flags for backtesting windows and conformal calibration."""
    cutoff = date(2024, 3, 31)
    # Series with 36 points and high recency
    records = _build_synthetic_monthly_records(months_count=36, end_date=date(2024, 3, 1))
    report = evaluate_series_eligibility_records(records, data_cutoff=cutoff)
    s = report.eligible_series[0]
    assert s.can_backtest_6_windows is True
    assert s.can_calibrate_conformal is True


def test_no_synthetic_series_fabricated_for_kpi():
    """Verify that only genuinely qualified series are returned, with zero KPI fabrication."""
    cutoff = date(2024, 3, 31)
    # 1 series with 36 points (eligible)
    rec_good = _build_synthetic_monthly_records(product_code="rice_milled", months_count=36)
    # 2 series with 20 points (excluded)
    rec_bad1 = _build_synthetic_monthly_records(product_code="maize", months_count=20)
    rec_bad2 = _build_synthetic_monthly_records(product_code="oil_edible", months_count=15)

    all_records = rec_good + rec_bad1 + rec_bad2
    report = evaluate_series_eligibility_records(all_records, data_cutoff=cutoff)

    assert report.total_series_evaluated == 3
    assert report.eligible_count == 1
    assert report.excluded_count == 2
    assert len(report.eligible_series) == 1
    assert report.eligible_series[0].product_code == "rice_milled"


def test_fill_strategy_invalid():
    """Verify invalid fill strategy raises ValueError."""
    cutoff = date(2024, 3, 31)
    records = _build_synthetic_monthly_records(months_count=36, end_date=date(2024, 3, 1))
    report = evaluate_series_eligibility_records(records, data_cutoff=cutoff)
    s = report.eligible_series[0]
    with pytest.raises(ValueError, match="Unknown fill_strategy"):
        s.to_numpy_array(fill_strategy="unsupported_strategy")


def test_empty_observations_series():
    """Verify handling of records with empty or zero/null prices."""
    cutoff = date(2024, 3, 31)
    empty_records = [
        {
            "product_code": "rice_milled",
            "location_pcode": "MG11",
            "admin_level": 1,
            "actor_level": "retail",
            "month": date(2024, 1, 1),
            "median_price": None,
        }
    ]
    report = evaluate_series_eligibility_records(empty_records, data_cutoff=cutoff)
    assert report.eligible_count == 0
    assert report.excluded_count == 1


def test_audit_and_extract_eligible_series_session_mock():
    """Verify audit_series_eligibility and extract_eligible_series with session."""
    from unittest.mock import MagicMock

    cutoff = date(2024, 3, 31)
    records = _build_synthetic_monthly_records(months_count=36, end_date=date(2024, 3, 1))

    class MockRow:
        def __init__(self, d):
            for k, v in d.items():
                setattr(self, k, v)

    mock_rows = [MockRow(r) for r in records]
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = mock_rows

    from ketrika.ml.series import audit_series_eligibility, extract_eligible_series

    report = audit_series_eligibility(session=mock_session, data_cutoff=cutoff)
    assert report.eligible_count == 1
    assert report.excluded_count == 0

    series_list = extract_eligible_series(session=mock_session, data_cutoff=cutoff)
    assert len(series_list) == 1
    assert series_list[0].product_code == "rice_milled"

    # Compatibility override
    series_override = extract_eligible_series(session=mock_session, data_cutoff=cutoff, min_points=6)
    assert len(series_override) == 1
