"""Unit tests for exogenous price forecasting and ablation engine (R3.6, ADR-105)."""

from datetime import date

import numpy as np
import pytest

from ketrika.ml.exogenous import (
    ExogenousFeatureConfig,
    ExogenousGradientBoostedModel,
    build_exogenous_features,
    evaluate_feature_ablation,
    validate_no_lookahead_leakage,
)


@pytest.fixture
def synthetic_history():
    """Generates 48 months of consistent monthly prices, exchange rate, and rainfall."""
    start_year = 2020
    dates = []
    for y in range(start_year, start_year + 4):
        for m in range(1, 13):
            dates.append(date(y, m, 1))

    np.random.seed(42)
    n = len(dates)
    trend = np.linspace(2500, 3800, n)
    seasonal = 300 * np.sin(2 * np.pi * np.array([d.month for d in dates]) / 12.0)
    noise = np.random.normal(0, 50, n)
    prices = trend + seasonal + noise

    # Macro series (USD/MGA exchange rate with slight lag relationship)
    macro_usd = np.linspace(3600, 4600, n) + np.random.normal(0, 30, n)

    # Climate series (rainfall anomaly in mm)
    climate_rain = 50 * np.sin(
        2 * np.pi * np.array([d.month for d in dates]) / 12.0
    ) + np.random.normal(0, 10, n)

    return dates, prices, {"usd_mga": macro_usd}, {"rainfall_anomaly": climate_rain}


def test_build_exogenous_features_dimensions_and_alignment(synthetic_history):
    dates, prices, macro, climate = synthetic_history
    cfg = ExogenousFeatureConfig(lags=(1, 2, 3, 12))

    X, y, f_names = build_exogenous_features(
        dates=dates,
        prices=prices,
        macro_series=macro,
        climate_series=climate,
        config=cfg,
    )

    max_lag = 12
    expected_rows = len(prices) - max_lag
    assert X.shape[0] == expected_rows
    assert len(y) == expected_rows
    assert "price_lag_1" in f_names
    assert "price_lag_12" in f_names
    assert "month_sin" in f_names
    assert "macro_usd_mga_lag1" in f_names
    assert "climate_rainfall_anomaly_lag1" in f_names


def test_validate_no_lookahead_leakage():
    dates = [date(2023, 1, 1), date(2023, 2, 1), date(2023, 3, 1)]
    # Target date is 2023-03-01 (index 2)
    # Valid past features
    validate_no_lookahead_leakage(
        dates, origin_index=2, feature_timestamps=[date(2023, 1, 1), date(2023, 2, 1)]
    )

    # Fatal leakage: feature timestamp equals or exceeds target date
    with pytest.raises(ValueError, match="Lookahead leakage detected"):
        validate_no_lookahead_leakage(dates, origin_index=2, feature_timestamps=[date(2023, 3, 1)])

    with pytest.raises(ValueError, match="Lookahead leakage detected"):
        validate_no_lookahead_leakage(dates, origin_index=2, feature_timestamps=[date(2023, 4, 1)])


def test_exogenous_gradient_boosted_model_fit_predict(synthetic_history):
    dates, prices, macro, climate = synthetic_history
    X, y, _ = build_exogenous_features(dates, prices, macro, climate)

    train_X, test_X = X[:-3], X[-3:]
    train_y = y[:-3]

    model = ExogenousGradientBoostedModel(n_estimators=20, max_depth=3)
    model.fit(train_X, train_y)
    preds = model.predict(test_X)

    assert len(preds) == 3
    assert np.all(np.isfinite(preds))
    assert np.all(preds > 2000)


def test_evaluate_feature_ablation_decision_rule(synthetic_history):
    dates, prices, macro, climate = synthetic_history

    report = evaluate_feature_ablation(
        dates=dates,
        prices=prices,
        macro_series=macro,
        climate_series=climate,
        series_id="MDG-RICE-ANOSIBE",
        product_code="rice_local",
        location="Analamanga",
        n_folds=4,
        min_train_size=24,
    )

    assert report.series_id == "MDG-RICE-ANOSIBE"
    assert "price_only" in report.family_results
    assert "price_plus_macro" in report.family_results
    assert "price_plus_climate" in report.family_results
    assert "price_full" in report.family_results

    # Baseline WAPE must be strictly positive
    assert report.baseline_wape > 0.0

    # Decision reason must be explicit
    assert len(report.decision_reason) > 10
    assert isinstance(report.retained, bool)

    report_dict = report.to_dict()
    assert report_dict["baseline_wape"] > 0
    assert len(report_dict["family_results"]) == 4
    # Scientific rigor: phrase 'statistically significant' must not be claimed without formal test (C022)
    assert "statistically significant" not in report.decision_reason.lower()


def test_exogenous_feature_config_rejects_zero_or_negative_lags() -> None:
    """Ensure lag <= 0 is strictly rejected to prevent target leakage (C022)."""
    with pytest.raises(ValueError, match="Lag must be an integer >= 1"):
        ExogenousFeatureConfig(lags=(0,))

    with pytest.raises(ValueError, match="Lag must be an integer >= 1"):
        ExogenousFeatureConfig(lags=(-1, 2))

    with pytest.raises(ValueError, match="At least one lag must be specified"):
        ExogenousFeatureConfig(lags=())


def test_build_exogenous_features_rejects_non_monotonic_dates() -> None:
    """Ensure unordered or duplicate dates are rejected before feature generation."""
    unordered_dates = [date(2023, 2, 1), date(2023, 1, 1), date(2023, 3, 1)]
    prices = np.array([2000.0, 2100.0, 2200.0])
    with pytest.raises(ValueError, match="Dates must be strictly monotonically increasing"):
        build_exogenous_features(
            dates=unordered_dates,
            prices=prices,
            config=ExogenousFeatureConfig(lags=(1,)),
        )


def test_evaluate_feature_ablation_abstains_on_insufficient_history() -> None:
    """Ensure explicit parsimony abstention when history is too short for selection and holdout."""
    dates = [date(2023, m, 1) for m in range(1, 13)]
    prices = np.linspace(2000, 2500, 12)

    report = evaluate_feature_ablation(
        dates=dates,
        prices=prices,
        min_train_size=24,
        n_folds=4,
        holdout_folds=2,
    )

    assert report.retained is False
    assert report.best_family == "price_only"
    assert "Insufficient history" in report.decision_reason
    assert "Explicit parsimony abstention" in report.decision_reason
    assert report.family_results == {}


def test_build_exogenous_features_demand_as_of_when_declared(synthetic_history) -> None:
    """Declaring as-of availability requires every exogenous series to be covered (C022)."""
    dates, prices, macro, climate = synthetic_history

    with pytest.raises(ValueError, match="Missing declared as-of availability dates"):
        build_exogenous_features(
            dates=dates,
            prices=prices,
            macro_series=macro,
            climate_series=climate,
            series_as_of={"macro:usd_mga": list(dates)},
        )

    with pytest.raises(ValueError, match="length"):
        build_exogenous_features(
            dates=dates,
            prices=prices,
            macro_series=macro,
            series_as_of={"macro:usd_mga": list(dates)[:4]},
        )


def test_build_exogenous_features_refuses_delayed_publication(synthetic_history) -> None:
    """A value whose REAL availability equals the target date is fatal leakage (C022)."""
    dates, prices, macro = synthetic_history[0], synthetic_history[1], synthetic_history[2]

    # Simulate a value published with a one-period delay: the macro level at index i-1
    # is only actually available at dates[i], ie exactly the target date.
    delayed_as_of = list(dates[1:]) + [dates[-1]]

    with pytest.raises(ValueError, match="Lookahead leakage detected"):
        build_exogenous_features(
            dates=dates,
            prices=prices,
            macro_series=macro,
            series_as_of={"macro:usd_mga": delayed_as_of},
        )


def test_evaluate_feature_ablation_reports_holdout_separation(synthetic_history) -> None:
    """Reported metrics come from the independent holdout; selection folds stay separate (C022)."""
    dates, prices, macro, climate = synthetic_history

    report = evaluate_feature_ablation(
        dates=dates,
        prices=prices,
        macro_series=macro,
        climate_series=climate,
        n_folds=4,
        min_train_size=24,
        holdout_folds=2,
    )

    assert report.baseline_wape > 0
    price_only = report.family_results["price_only"]
    # Headline metrics are computed ONLY on the two holdout folds, not on all six
    assert price_only.n_samples == 2, "Holdout metrics must be measured on holdout folds only"
    # Phase separation must be explicit in the decision reason (C022)
    assert "holdout" in report.decision_reason.lower()
    # No statistical significance wording anywhere in the decision (C022)
    assert "statistically significant" not in report.decision_reason.lower()


def test_evaluate_feature_ablation_refuses_zero_folds() -> None:
    dates = [date(2024, m, 1) for m in range(1, 13)]
    prices = np.linspace(2000, 2600, 12)

    with pytest.raises(ValueError, match="at least one selection fold"):
        evaluate_feature_ablation(dates=dates, prices=prices, min_train_size=6, n_folds=0)

    with pytest.raises(ValueError, match="one holdout fold"):
        evaluate_feature_ablation(dates=dates, prices=prices, min_train_size=6, holdout_folds=0)
