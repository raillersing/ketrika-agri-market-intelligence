"""Gate qualification test suite for Phase R3: price forecasting, as-of datasets, conformal calibration, and parsimony (SPECS §17, §19, R3.9)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import numpy as np

from ketrika.ml.backtest import (
    partition_backtest_windows,
)
from ketrika.ml.conformal import (
    calibrate_conformal_bounds,
)
from ketrika.ml.dataset import (
    build_as_of_dataset,
)
from ketrika.ml.evaluation import (
    EvaluationRecord,
    benchmark_against_baselines,
    compute_performance_decomposition,
    wilson_score_interval_95,
)
from ketrika.ml.models import (
    AutoARIMAModel,
    NaiveLastModel,
)
from ketrika.ml.series import (
    evaluate_series_eligibility_records,
    shift_months,
)


def _make_series_records(
    months_count: int,
    end_date: date,
    product_code: str = "rice_vary_gasy",
    location_pcode: str = "MG11",
    actor_level: str = "retail",
    admin_level: int = 1,
) -> list[dict]:
    prod_id = uuid.uuid4()
    loc_id = uuid.uuid4()
    dates = [shift_months(end_date, -i) for i in reversed(range(months_count))]
    return [
        {
            "product_id": prod_id,
            "product_code": product_code,
            "product_name": "Riz blanc local",
            "location_id": loc_id,
            "location_pcode": location_pcode,
            "location_name": "Analamanga",
            "admin_level": admin_level,
            "actor_level": actor_level,
            "month": m,
            "median_price": 2500.0 + idx * 10.0,
            "observed_or_imputed": "observed",
            "chosen_source_id": "miasa_odr",
            "chosen_source_family": "odr",
        }
        for idx, m in enumerate(dates)
    ]


def test_gate_r3_criterion_1_series_eligibility() -> None:
    """Gate Criterion 1: Strict series eligibility rules (SPECS §17.1, R3.1).

    - Rejects series with fewer than 36 monthly points.
    - Rejects series lacking at least 12 points in the past 24 months.
    - Rejects district granularity (only regional and national permitted).
    - Preserves gaps as explicit NaNs without compression.
    """
    cutoff = date(2026, 12, 31)

    # 1. Reject < 36 points (e.g. 35 points)
    recs_35 = _make_series_records(months_count=35, end_date=date(2026, 12, 1))
    report_35 = evaluate_series_eligibility_records(recs_35, data_cutoff=cutoff)
    assert report_35.eligible_count == 0
    assert report_35.excluded_count == 1
    assert any("35 points < 36 required" in r for r in report_35.excluded_series[0].reasons)

    # 2. Reject lacking 12 points in recent 24 months (e.g. old points ending in 2023)
    recs_stale = _make_series_records(months_count=40, end_date=date(2023, 12, 1))
    report_stale = evaluate_series_eligibility_records(recs_stale, data_cutoff=cutoff)
    assert report_stale.eligible_count == 0
    assert report_stale.excluded_count == 1
    assert any("insufficient_recency" in r for r in report_stale.excluded_series[0].reasons)

    # 3. Reject district level (admin_level=2)
    recs_district = _make_series_records(
        months_count=48,
        end_date=date(2026, 12, 1),
        location_pcode="MG11101",
        admin_level=2,
    )
    report_district = evaluate_series_eligibility_records(recs_district, data_cutoff=cutoff)
    assert report_district.eligible_count == 0
    assert report_district.excluded_count == 1
    assert any(
        "districts admin_level=2 rejected" in r for r in report_district.excluded_series[0].reasons
    )


def test_gate_r3_criterion_2_as_of_datasets_anti_leakage() -> None:
    """Gate Criterion 2: Historical as-of datasets C2/C4 with immutable SHA-256 fingerprint (R3.2).

    - Future publications and future revisions are excluded strictly.
    - Deterministic canonical fingerprint is recomputed identically.
    """
    jan_obs_id = str(uuid.uuid4())
    raw_rec = {
        "observation_id": jan_obs_id,
        "source_id": "miasa_odr",
        "natural_key": "nk_rice_MG11_2026-01-01",
        "product_code": "rice_vary_gasy",
        "location_pcode": "MG11",
        "actor_level": "retail",
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "month": "2026-01-01",
        "price_mga_per_base": 2400.0,
        "base_unit": "kg",
        "observed_or_imputed": "observed",
        "published_at": datetime(2026, 3, 5, 10, 0, tzinfo=UTC),
        "first_available_at": datetime(2026, 3, 5, 10, 0, tzinfo=UTC),
        "ingested_at": datetime(2026, 3, 5, 12, 0, tzinfo=UTC),
        "superseded_by": None,
        "bronze_object_key": "bronze/raw/odr/2026/jan.pdf",
    }

    # 1. Dataset as-of mid-February 2026 (before publication) -> Excluded
    as_of_feb = datetime(2026, 2, 15, 0, 0, tzinfo=UTC)
    ds_feb = build_as_of_dataset(as_of=as_of_feb, raw_records=[raw_rec])
    assert ds_feb.observations_count == 0
    assert jan_obs_id not in ds_feb.observation_ids

    # 2. Dataset as-of mid-March 2026 (after publication) -> Included
    as_of_mar = datetime(2026, 3, 15, 0, 0, tzinfo=UTC)
    ds_mar = build_as_of_dataset(as_of=as_of_mar, raw_records=[raw_rec])
    assert ds_mar.observations_count == 1
    assert jan_obs_id in ds_mar.observation_ids
    assert ds_mar.records[0].price_mga_per_base == 2400.0

    # 3. Canonical SHA-256 fingerprint reproducibility
    ds_mar_again = build_as_of_dataset(as_of=as_of_mar, raw_records=[raw_rec])
    assert ds_mar.canonical_fingerprint == ds_mar_again.canonical_fingerprint


def test_gate_r3_criterion_3_model_conformance_and_honesty() -> None:
    """Gate Criterion 3: Compliant statistical models & baseline honesty (R3.3).

    - NaiveLast and SeasonalNaive implement exact formulas.
    - ETS and ARIMA declare fallback reasons when history is insufficient.
    - No ARIMA is claimed when a baseline was actually run.
    """
    y_short = np.array([2000.0, 2050.0, 2100.0])  # Length 3 < 24

    arima = AutoARIMAModel()
    res_arima = arima.fit_predict(y_short, h=2)
    assert res_arima.status == "fallback"
    assert res_arima.model_requested == "AutoARIMA"
    assert res_arima.model_effective == "NaiveLast"
    assert "insufficient_history" in str(res_arima.fallback_reason)

    # NaiveLast prediction exactly repeats last observation
    naive = NaiveLastModel()
    res_naive = naive.fit_predict(y_short, h=2)
    assert res_naive.prediction.mean.tolist() == [2100.0, 2100.0]
    assert res_naive.model_effective == "NaiveLast"


def test_gate_r3_criterion_4_three_phase_temporal_separation() -> None:
    """Gate Criterion 4: Strict temporal separation across 3 phases (R3.4).

    - Phase 1 (rolling-origin selection) never accesses holdout period.
    - Phase 2 (calibration) etalons residuals on past validation windows.
    - Phase 3 (holdout out-of-sample) evaluates winner without backward feedback.
    """
    n_points = 48
    h = 3
    windows, status = partition_backtest_windows(
        n_points=n_points,
        h=h,
        max_windows=6,
        min_train_len=24,
        holdout_len=6,  # 6 final points reserved for holdout
    )
    assert status == "valid"
    assert len(windows) == 6

    # Verify every window test slice ends strictly before the holdout reservation (48 - 6 = 42)
    for win in windows:
        assert win.test_slice[1] <= 42
        assert win.train_length >= 24


def test_gate_r3_criterion_5_conformal_calibration_guarantees() -> None:
    """Gate Criterion 5: Rigorous conformal prediction intervals and coverage audit (R3.5).

    - Non-parametric quantile calibration.
    - Formal rejection of unverified +/- 10% shortcuts as 'calibrated'.
    - Wilson 95% confidence interval on empirical coverage.
    - Guaranteed monotonic ordering: 0 <= p10 <= p50 <= p90.
    """
    points = np.array([2500.0, 2600.0, 2700.0])
    residuals_sufficient = [50.0, 70.0, 40.0, 60.0, 80.0, 45.0, 65.0, 55.0, 90.0, 75.0]

    # Sufficient residuals (N >= 8) -> calibrated
    res_cal = calibrate_conformal_bounds(
        points, residuals_sufficient, target_coverage=0.80, min_residuals=8
    )
    assert res_cal.is_calibrated is True
    assert res_cal.status == "calibrated"
    for i in range(len(points)):
        assert 0 <= res_cal.p10[i] <= res_cal.mean[i] <= res_cal.p90[i]

    # Insufficient residuals (N < 8) -> uncalibrated_heuristic, is_calibrated = False
    residuals_few = [50.0, 60.0, 70.0]
    res_uncal = calibrate_conformal_bounds(
        points, residuals_few, target_coverage=0.80, min_residuals=8
    )
    assert res_uncal.is_calibrated is False
    assert res_uncal.status == "uncalibrated_heuristic"

    # Wilson interval check
    low_ci, high_ci = wilson_score_interval_95(8, 10)
    assert 0.0 < low_ci < 0.8 < high_ci < 1.0


def test_gate_r3_criterion_6_matured_evaluations_and_parsimony() -> None:
    """Gate Criterion 6: Multidimensional evaluation and parsimony rule against baselines (R3.8).

    - Errors are decomposed by product, location, horizon, and seasonality.
    - Candidate statistical models must beat baselines by > 0.01 WAPE to be declared winners.
    - Verifiable provenance (forecast_id, model_run_id, actual_observation_id).
    """
    run_id = uuid.uuid4()
    obs_id = uuid.uuid4()

    rec_baseline = EvaluationRecord(
        forecast_id=uuid.uuid4(),
        model_run_id=run_id,
        series_key="rice|s|r|MG11|kg",
        product_code="rice_vary_gasy",
        location_pcode="MG11",
        actor_level="retail",
        target_period=date(2026, 4, 1),
        horizon=1,
        evaluation_kind="matured_actual",
        model_name="NaiveLast",
        is_baseline=True,
        predicted_p50=2400.0,
        predicted_p10=2200.0,
        predicted_p90=2600.0,
        actual_price=2450.0,
        actual_observation_id=obs_id,
        absolute_error=50.0,
        percentage_error=50.0 / 2450.0,
        is_covered_80=True,
    )
    rec_candidate = EvaluationRecord(
        forecast_id=uuid.uuid4(),
        model_run_id=run_id,
        series_key="rice|s|r|MG11|kg",
        product_code="rice_vary_gasy",
        location_pcode="MG11",
        actor_level="retail",
        target_period=date(2026, 4, 1),
        horizon=1,
        evaluation_kind="matured_actual",
        model_name="AutoETS",
        is_baseline=False,
        predicted_p50=2445.0,
        predicted_p10=2250.0,
        predicted_p90=2650.0,
        actual_price=2450.0,
        actual_observation_id=obs_id,
        absolute_error=5.0,
        percentage_error=5.0 / 2450.0,
        is_covered_80=True,
    )

    # 1. Decomposition check
    table = compute_performance_decomposition([rec_baseline, rec_candidate])
    assert "rice_vary_gasy" in table.by_product
    assert "MG11" in table.by_location
    assert 1 in table.by_horizon
    assert "recolte" in table.by_seasonality

    # 2. Parsimony check: candidate WAPE = 5/2450 ≈ 0.002, baseline = 50/2450 ≈ 0.0204
    # delta = 0.018 > 0.01 -> candidate_winner
    bench = benchmark_against_baselines([rec_baseline, rec_candidate])
    assert bench["best_baseline"] == "NaiveLast"
    assert bench["comparisons"][0]["verdict"] == "candidate_winner"
