"""Unit tests for conformal prediction intervals, calibration thresholds, and coverage monitoring (SPECS §17.3, ADR-077, R3.5)."""

from __future__ import annotations

import numpy as np
import pytest

from ketrika.ml.conformal import (
    audit_interval_coverage,
    calibrate_conformal_bounds,
    compute_wilson_score_interval,
)


def test_conformal_quantiles_strictly_ordered_and_positive():
    """Verify 0 <= p10 <= p50 <= p90 with finite values under various price levels."""
    forecasts = np.array([2100.0, 2150.0, 2200.0])
    # 12 real historical residuals
    residuals = [-40.0, -25.0, -10.0, -5.0, 0.0, 5.0, 15.0, 20.0, 30.0, 35.0, -15.0, 18.0]

    res = calibrate_conformal_bounds(
        point_forecasts=forecasts,
        calibration_residuals=residuals,
        target_coverage=0.80,
    )

    assert res.is_calibrated is True
    assert res.status == "calibrated"
    assert res.calibration_sample_size == 12

    # Monotonicity and positivity checks
    assert (res.p10 >= 0.0).all()
    assert (res.p10 <= res.mean + 1e-4).all()
    assert (res.mean <= res.p90 + 1e-4).all()
    assert (np.isfinite(res.p10)).all()
    assert (np.isfinite(res.p90)).all()
    assert len(res.width) == 3
    assert all(w > 0.0 for w in res.width)


def test_insufficient_residuals_prevents_calibrated_label():
    """Verify absence of calibration (< 8 residuals) strictly prevents 'calibrated' label (ADR-077, R3.5)."""
    forecasts = np.array([2000.0, 2020.0, 2040.0])
    # Only 4 residuals (< min_residuals=8)
    short_residuals = [10.0, -15.0, 5.0, -8.0]

    res = calibrate_conformal_bounds(
        point_forecasts=forecasts,
        calibration_residuals=short_residuals,
        min_residuals=8,
    )

    # MUST NOT be marked calibrated
    assert res.is_calibrated is False
    assert res.status == "uncalibrated_heuristic"
    assert res.calibration_sample_size == 4
    # Bounds still valid numbers
    assert (res.p10 <= res.mean).all()
    assert (res.mean <= res.p90).all()


def test_wilson_score_interval_exactness():
    """Verify Wilson score confidence interval matches mathematical ground-truth."""
    # 80 successes out of 100 (p_hat = 0.80)
    lo, hi = compute_wilson_score_interval(successes=80, total=100, confidence=0.95)
    # Theoretical Wilson 95% for 80/100: [0.7115, 0.8666]
    assert lo == pytest.approx(0.7115, abs=0.01)
    assert hi == pytest.approx(0.8666, abs=0.01)

    # Edge case 0/10: bounds within [0, 1]
    lo_zero, hi_zero = compute_wilson_score_interval(successes=0, total=10)
    assert lo_zero == 0.0
    assert hi_zero > 0.0

    # Edge case total=0
    lo_empty, hi_empty = compute_wilson_score_interval(successes=0, total=0)
    assert lo_empty == 0.0
    assert hi_empty == 1.0


def test_audit_interval_coverage_full_breakdown():
    """Verify audit_interval_coverage computes empirical coverage, width, and per-horizon decomposition."""
    actuals = [100.0, 110.0, 120.0, 200.0, 210.0, 220.0]
    p10 = [90.0, 95.0, 115.0, 190.0, 205.0, 215.0]
    p90 = [115.0, 125.0, 130.0, 215.0, 225.0, 230.0]
    horizons = [1, 2, 3, 1, 2, 3]

    report = audit_interval_coverage(
        actuals=actuals,
        p10_bounds=p10,
        p90_bounds=p90,
        horizon_steps=horizons,
        target_level=0.80,
    )

    # All 6 actuals fall between p10 and p90 -> coverage = 1.0
    assert report.empirical_coverage == 1.0
    assert report.sample_size == 6
    assert report.covered_count == 6
    assert report.wilson_ci_95[0] > 0.50
    assert report.mean_width > 0.0

    # Check by-horizon breakdown
    assert 1 in report.by_horizon_coverage
    assert 2 in report.by_horizon_coverage
    assert 3 in report.by_horizon_coverage
    assert report.by_horizon_coverage[1] == 1.0


def test_empty_actuals_safe_handling():
    """Verify empty inputs return safe uncalibrated/empty audit report without error."""
    report = audit_interval_coverage(
        actuals=[],
        p10_bounds=[],
        p90_bounds=[],
    )
    assert report.sample_size == 0
    assert report.empirical_coverage == 0.0
    assert report.is_sufficient_sample is False
