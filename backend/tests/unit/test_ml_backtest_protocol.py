"""Unit tests for three-phase evaluation protocol, leak-free rolling backtest, and holdout separation (SPECS §17.3, ADR-076, R3.4)."""

from __future__ import annotations

import numpy as np

from ketrika.ml.backtest import (
    compute_metrics,
    evaluate_final_holdout,
    partition_backtest_windows,
    select_best_model,
)
from ketrika.ml.models import (
    AutoETSModel,
    NaiveLastModel,
    SeasonalNaiveModel,
)


def test_partition_backtest_windows_strict_temporal_bounds():
    """Verify that every rolling window strictly trains on the past before its test slice (ADR-076)."""
    n_points = 36
    h = 3
    max_windows = 6
    min_train_len = 24
    holdout_len = 3

    windows, status = partition_backtest_windows(
        n_points=n_points,
        h=h,
        max_windows=max_windows,
        min_train_len=min_train_len,
        holdout_len=holdout_len,
    )

    assert status == "valid"
    assert len(windows) == max_windows

    for win in windows:
        # Strict anti-leakage temporal order: train ends exactly where test begins
        assert win.train_slice[0] == 0
        assert win.train_slice[1] == win.test_slice[0]
        assert win.test_slice[1] == win.test_slice[0] + h
        # Test slice never overlaps holdout
        assert win.test_slice[1] <= n_points - holdout_len
        # Minimum training length enforced
        assert win.train_length >= min_train_len
        assert win.is_eligible is True


def test_insufficient_history_marks_experimental_status():
    """Verify that insufficient history does not quietly truncate windows but reports experimental status (R3.4)."""
    # 26 points total: cannot support 6 windows with train >= 24 (26 - 3 - 24 + 1 = 0)
    n_points = 26
    h = 3
    max_windows = 6
    min_train_len = 24

    windows, status = partition_backtest_windows(
        n_points=n_points,
        h=h,
        max_windows=max_windows,
        min_train_len=min_train_len,
    )

    assert status == "experimental_insufficient_windows"
    # Protocol flags that the series does not meet normative 6-window eligibility
    assert any(not w.is_eligible for w in windows)


def test_model_selection_never_sees_holdout_errors():
    """Verify that model selection outcome is strictly invariant to future holdout perturbations (anti-leakage)."""
    # 36 months history + 6 months holdout = 42 points
    np.random.seed(42)
    base_history = [2000.0 + 10.0 * i + (i % 4) * 20.0 for i in range(36)]
    holdout_normal = [2360.0, 2370.0, 2380.0, 2390.0, 2400.0, 2410.0]
    holdout_perturbed = [999999.0, 999999.0, 999999.0, 999999.0, 999999.0, 999999.0]

    series_normal = np.array(base_history + holdout_normal, dtype=float)
    series_perturbed = np.array(base_history + holdout_perturbed, dtype=float)

    candidates = [
        NaiveLastModel(),
        SeasonalNaiveModel(season_length=12),
        AutoETSModel(season_length=12),
    ]

    # Select best model reserving 6 points of holdout
    res1 = select_best_model(
        series_key="rice_pilot",
        y=series_normal,
        candidates=candidates,
        h=3,
        max_windows=6,
        holdout_len=6,
    )

    res2 = select_best_model(
        series_key="rice_pilot",
        y=series_perturbed,
        candidates=candidates,
        h=3,
        max_windows=6,
        holdout_len=6,
    )

    # The chosen model MUST be 100% IDENTICAL because holdout data is strictly sealed
    assert res1.best_model_name == res2.best_model_name
    assert res1.best_metrics.wape == res2.best_metrics.wape
    assert res1.best_metrics.mae == res2.best_metrics.mae
    assert res1.best_metrics.smape == res2.best_metrics.smape

    # Meanwhile, the holdout metrics themselves DO reflect the perturbation
    assert res1.holdout_metrics is not None
    assert res2.holdout_metrics is not None
    assert res2.holdout_metrics.wape > res1.holdout_metrics.wape


def test_per_horizon_metrics_decomposition():
    """Verify metrics breakdown by forecast step h in {1, 2, 3} (R3.4 requirement)."""
    actuals = [100.0, 200.0, 300.0, 110.0, 210.0, 310.0]
    predictions = [105.0, 190.0, 315.0, 112.0, 205.0, 312.0]
    p10 = [90.0, 170.0, 280.0, 95.0, 180.0, 290.0]
    p90 = [120.0, 220.0, 330.0, 125.0, 230.0, 330.0]
    horizons = [1, 2, 3, 1, 2, 3]

    metrics = compute_metrics(
        actuals=actuals,
        predictions=predictions,
        p10_bounds=p10,
        p90_bounds=p90,
        n_windows=2,
        horizon_steps=horizons,
    )

    assert metrics.wape > 0.0
    assert metrics.n_windows == 2
    assert metrics.sample_size == 6

    # Verify breakdown
    assert 1 in metrics.by_horizon
    assert 2 in metrics.by_horizon
    assert 3 in metrics.by_horizon

    # Check horizon 1: actuals [100, 110], preds [105, 112], errors [5, 2], sum=7, sum actuals=210 -> wape=7/210=0.0333
    h1 = metrics.by_horizon[1]
    assert h1.horizon == 1
    assert h1.sample_size == 2
    assert h1.mae == 3.5
    assert h1.coverage_80 == 1.0


def test_zero_actuals_division_by_zero_safety():
    """Verify that zero actuals do not cause division by zero or NaN propagation."""
    actuals = [0.0, 0.0, 0.0]
    predictions = [0.0, 0.0, 0.0]
    p10 = [0.0, 0.0, 0.0]
    p90 = [0.0, 0.0, 0.0]

    metrics = compute_metrics(
        actuals=actuals,
        predictions=predictions,
        p10_bounds=p10,
        p90_bounds=p90,
        n_windows=1,
    )

    assert metrics.wape == 0.0
    assert metrics.mae == 0.0
    assert metrics.smape == 0.0
    assert metrics.coverage_80 == 1.0


def test_evaluate_final_holdout_standalone():
    """Verify Phase 3 final holdout evaluation runs independently on test period."""
    y = np.array([2000.0 + 15.0 * i for i in range(30)], dtype=float)
    model = NaiveLastModel()

    holdout_res = evaluate_final_holdout(model=model, y=y, holdout_len=3)
    assert holdout_res.status == "holdout_evaluated"
    assert holdout_res.sample_size == 3
    assert holdout_res.wape >= 0.0
    assert 1 in holdout_res.by_horizon
    assert 2 in holdout_res.by_horizon
    assert 3 in holdout_res.by_horizon
