"""Unit tests for normative benchmarks, model conformance, and fallback traceability (SPECS §17, ADR-075, R3.3)."""

from __future__ import annotations

import numpy as np
import pytest

from ketrika.ml.backtest import (
    MODEL_SIMPLICITY,
    select_best_model,
)
from ketrika.ml.models import (
    AutoARIMAModel,
    AutoETSModel,
    ModelForecastResult,
    NaiveLastModel,
    SeasonalNaiveModel,
    impute_training_gaps,
)


def test_naive_last_exact_calculation():
    """Verify NaiveLast produces exact hand-calculated forward constant forecast and valid intervals."""
    y = np.array([2100.0, 2150.0, 2200.0, 2250.0, 2300.0], dtype=float)
    h = 3
    model = NaiveLastModel()

    res: ModelForecastResult = model.fit_predict(y, h=h, unit="kg", currency="MGA")
    assert res.model_requested == "NaiveLast"
    assert res.model_effective == "NaiveLast"
    assert res.status == "fitted"
    assert res.fallback_reason is None
    assert res.unit == "kg"
    assert res.currency == "MGA"

    # Exact hand calculation: last value is 2300.0
    expected_mean = np.array([2300.0, 2300.0, 2300.0])
    np.testing.assert_allclose(res.mean, expected_mean)
    assert (res.p10 <= res.mean).all()
    assert (res.mean <= res.p90).all()
    assert (res.p10 >= 0).all()


def test_seasonal_naive_annual_exact_calculation():
    """Verify SeasonalNaive with season_length=12 takes values from 12 months prior."""
    # Construct 24 months of data with known seasonal pattern
    base_pattern = [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0, 180.0, 190.0, 200.0, 210.0]
    # Year 2 slightly higher
    y = np.array(base_pattern + [v + 10.0 for v in base_pattern], dtype=float)
    assert len(y) == 24

    model = SeasonalNaiveModel(season_length=12)
    res = model.fit_predict(y, h=3, unit="kg", currency="MGA")

    assert res.model_requested == "SeasonalNaive"
    assert res.model_effective == "SeasonalNaive"
    assert res.status == "fitted"
    assert res.unit == "kg"
    assert res.currency == "MGA"

    # Season length is 12: h=1 corresponds to y[-12] (which is index 12 in 24 months)
    # y[-12] = 110.0, y[-11] = 120.0, y[-10] = 130.0
    expected_h1 = y[-12]
    expected_h2 = y[-11]
    expected_h3 = y[-10]
    expected = np.array([expected_h1, expected_h2, expected_h3])
    np.testing.assert_allclose(res.mean, expected, rtol=1e-3)


def test_insufficient_history_explicit_fallback_traceability_a09():
    """Verify A09 anti-cheat: models report insufficient history and NEVER claim AutoARIMA on fallback."""
    short_series = np.array([2000.0, 2050.0, 2100.0, 2150.0, 2200.0], dtype=float)  # 5 points
    h = 3

    # 1. SeasonalNaive with 5 points (< 12)
    s_naive = SeasonalNaiveModel(season_length=12)
    res_sn = s_naive.fit_predict(short_series, h=h)
    assert res_sn.model_requested == "SeasonalNaive"
    assert res_sn.model_effective == "NaiveLast"
    assert res_sn.status == "fallback"
    assert "insufficient_history" in (res_sn.fallback_reason or "")
    # Check that predictions are still valid numbers (from NaiveLast)
    assert len(res_sn.mean) == h
    assert (res_sn.mean == 2200.0).all()

    # 2. AutoETS with 15 points (< 24 required for annual ETS)
    medium_series = np.array([2000.0 + 10.0 * i for i in range(15)], dtype=float)
    ets = AutoETSModel(season_length=12)
    res_ets = ets.fit_predict(medium_series, h=h)
    assert res_ets.model_requested == "AutoETS"
    assert res_ets.model_effective in ("SeasonalNaive", "NaiveLast")
    assert res_ets.status == "fallback"
    assert "insufficient_history" in (res_ets.fallback_reason or "")

    # 3. AutoARIMA with 15 points (< 24 required for seasonal ARIMA)
    arima = AutoARIMAModel(season_length=12)
    res_arima = arima.fit_predict(medium_series, h=h)
    assert res_arima.model_requested == "AutoARIMA"
    assert res_arima.model_effective != "AutoARIMA"  # Crucial A09 assertion: never display ARIMA when fallback ran
    assert res_arima.model_effective in ("SeasonalNaive", "NaiveLast", "DeterministicBaseline")
    assert res_arima.status == "fallback"
    assert "insufficient_history" in (res_arima.fallback_reason or "")


def test_training_gap_imputation_clean_and_interpolated():
    """Verify training gap imputation on regular calendar grids (SPECS §17.3, ADR-075)."""
    # 1. No gaps: identical array returned
    clean = np.array([100.0, 110.0, 120.0, 130.0])
    imputed, reason = impute_training_gaps(clean)
    assert reason is None
    assert imputed is not None
    np.testing.assert_array_equal(imputed, clean)

    # 2. Moderate internal gap (2 missing months out of 10 = 20% < 30%, gap=2 <= 4)
    with_gap = np.array([100.0, 110.0, np.nan, np.nan, 140.0, 150.0, 160.0, 170.0, 180.0, 190.0])
    imputed, reason = impute_training_gaps(with_gap, max_gap=4, max_missing_ratio=0.30)
    assert reason is None
    assert imputed is not None
    # Linear interpolation between 110.0 and 140.0 over 3 steps: 120.0 and 130.0
    assert imputed[2] == pytest.approx(120.0, abs=1e-3)
    assert imputed[3] == pytest.approx(130.0, abs=1e-3)

    # 3. Excessive consecutive gap: 5 consecutive missing months > max_gap=4
    excessive_gap = np.array([100.0, np.nan, np.nan, np.nan, np.nan, np.nan, 200.0, 210.0, 220.0, 230.0])
    imputed, reason = impute_training_gaps(excessive_gap, max_gap=4, max_missing_ratio=0.60)
    assert imputed is None
    assert "excessive_consecutive_gap" in (reason or "")

    # 4. Excessive missing ratio: 4 out of 10 missing = 40% > max_missing_ratio=0.30
    excessive_ratio = np.array([100.0, np.nan, 120.0, np.nan, 140.0, np.nan, 160.0, np.nan, 180.0, 190.0])
    imputed, reason = impute_training_gaps(excessive_ratio, max_gap=4, max_missing_ratio=0.30)
    assert imputed is None
    assert "excessive_missing_ratio" in (reason or "")


def test_models_with_imputed_gaps():
    """Verify that candidate models successfully forecast when training series contains admissible gaps."""
    # 24 months with 2 missing points
    base = [2000.0 + 20.0 * i for i in range(24)]
    y = np.array(base, dtype=float)
    y[5] = np.nan
    y[14] = np.nan

    model = NaiveLastModel()
    res = model.fit_predict(y, h=3)
    assert res.status == "fitted"
    assert not np.isnan(res.mean).any()

    # Seasonal Naive
    sn = SeasonalNaiveModel(season_length=12)
    res_sn = sn.fit_predict(y, h=3)
    assert res_sn.status == "fitted"
    assert not np.isnan(res_sn.mean).any()


def test_deterministic_reproducibility():
    """Verify that multiple fits on the exact same dataset yield 100% identical forecasts."""
    y = np.array([2000.0 + 15.0 * i + (i % 3) * 10.0 for i in range(36)], dtype=float)
    h = 3

    models = [
        NaiveLastModel(),
        SeasonalNaiveModel(season_length=12),
        AutoETSModel(season_length=12),
        AutoARIMAModel(season_length=12),
    ]

    for model in models:
        res1 = model.fit_predict(y, h=h)
        res2 = model.fit_predict(y, h=h)
        np.testing.assert_array_equal(res1.mean, res2.mean)
        np.testing.assert_array_equal(res1.p10, res2.p10)
        np.testing.assert_array_equal(res1.p90, res2.p90)
        assert res1.model_effective == res2.model_effective


def test_naive_baseline_can_win_selection():
    """Verify that a normative naive baseline can legitimately win selection when competitive (R3.3)."""
    # Flat series: NaiveLast will have near zero error
    y = np.full(36, 2500.0, dtype=float)
    # Add minor noise
    y += np.array([0.0 if i % 2 == 0 else 1.0 for i in range(36)])

    candidates = [
        NaiveLastModel(),
        SeasonalNaiveModel(season_length=12),
        AutoETSModel(season_length=12),
        AutoARIMAModel(season_length=12),
    ]

    result = select_best_model(
        series_key="test_flat_series",
        y=y,
        candidates=candidates,
        h=3,
        max_windows=4,
    )

    # NaiveLast or SeasonalNaive should win due to simplicity and minimal WAPE
    assert result.best_model_name in ("NaiveLast", "SeasonalNaive")
    assert result.best_metrics.wape <= 0.05
    assert "NaiveLast" in result.evaluations


def test_model_failure_does_not_abort_selection():
    """Verify that if one candidate fails or has an error, others proceed and a winner is chosen."""

    class BuggyModel:
        @property
        def name(self) -> str:
            return "BuggyModel"

        def fit_predict(self, y: np.ndarray, h: int, **kwargs) -> ModelForecastResult:
            raise RuntimeError("Synthetic model crash for resilience test")

    y = np.array([2000.0 + 10.0 * i for i in range(36)], dtype=float)
    candidates = [
        BuggyModel(),  # Will crash
        NaiveLastModel(),
    ]

    # Should not raise exception
    res = select_best_model(
        series_key="resilience_series",
        y=y,
        candidates=candidates,  # type: ignore
        h=3,
        max_windows=3,
    )
    assert res.best_model_name == "NaiveLast"
    assert "BuggyModel" in res.evaluations


def test_model_simplicity_ranking():
    """Verify simplicity hierarchy: NaiveLast (0) < SeasonalNaive (1) < AutoETS (2) < AutoARIMA (3)."""
    assert MODEL_SIMPLICITY["NaiveLast"] < MODEL_SIMPLICITY["SeasonalNaive"]
    assert MODEL_SIMPLICITY["SeasonalNaive"] < MODEL_SIMPLICITY["AutoETS"]
    assert MODEL_SIMPLICITY["AutoETS"] < MODEL_SIMPLICITY["AutoARIMA"]
