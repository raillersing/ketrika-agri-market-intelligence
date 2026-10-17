"""Unit tests for matured forecast evaluation, multidimensional decomposition, and parsimony benchmarking (SPECS §17.4, ADR-079, R3.8)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from ketrika.api.main import app
from ketrika.core.db import get_db
from ketrika.ml.evaluation import (
    EvaluationRecord,
    MaturedForecastEvaluator,
    benchmark_against_baselines,
    compute_metrics_for_records,
    compute_performance_decomposition,
    get_seasonality_regime,
    wilson_score_interval_95,
)


def test_wilson_score_interval_95() -> None:
    """Check Wilson score confidence intervals for coverage."""
    # Degenerate cases
    assert wilson_score_interval_95(0, 0) == (0.0, 1.0)
    assert wilson_score_interval_95(0, 10) == (0.0, 0.2775)

    # Standard case 8/10 covered (80%)
    low, high = wilson_score_interval_95(8, 10)
    assert 0.49 <= low <= 0.55
    assert 0.93 <= high <= 0.98

    # High sample size 80/100
    low_100, high_100 = wilson_score_interval_95(80, 100)
    assert 0.70 <= low_100 <= 0.73
    assert 0.86 <= high_100 <= 0.88


def test_seasonality_regime_madagascar() -> None:
    """Verify seasonal regime classification for Madagascar markets."""
    # Soudure (lean season): Nov to Mar
    assert get_seasonality_regime(date(2026, 11, 1)) == "soudure"
    assert get_seasonality_regime(date(2026, 12, 1)) == "soudure"
    assert get_seasonality_regime(date(2026, 1, 1)) == "soudure"
    assert get_seasonality_regime(date(2026, 2, 1)) == "soudure"
    assert get_seasonality_regime(date(2026, 3, 1)) == "soudure"

    # Recolte (harvest season): Apr to Oct
    assert get_seasonality_regime(date(2026, 4, 1)) == "recolte"
    assert get_seasonality_regime(date(2026, 5, 1)) == "recolte"
    assert get_seasonality_regime(date(2026, 7, 1)) == "recolte"
    assert get_seasonality_regime(date(2026, 10, 1)) == "recolte"


def test_compute_metrics_for_records() -> None:
    """Verify exact formula calculation for WAPE, MAE, sMAPE, coverage_80, and interval width."""
    # Empty case
    empty_m = compute_metrics_for_records([])
    assert empty_m.wape is None
    assert empty_m.mae is None
    assert empty_m.smape is None
    assert empty_m.coverage_80 is None
    assert empty_m.sample_size == 0

    run_id = uuid.uuid4()
    records = [
        EvaluationRecord(
            forecast_id=uuid.uuid4(),
            model_run_id=run_id,
            series_key="rice_vary_gasy|standard|retail|MG11|kg",
            product_code="rice_vary_gasy",
            location_pcode="MG11",
            actor_level="retail",
            target_period=date(2026, 5, 1),
            horizon=1,
            evaluation_kind="matured_actual",
            model_name="AutoETS",
            is_baseline=False,
            predicted_p50=2500.0,
            predicted_p10=2300.0,
            predicted_p90=2700.0,
            actual_price=2600.0,
            actual_observation_id=uuid.uuid4(),
            absolute_error=100.0,
            percentage_error=100.0 / 2600.0,
            is_covered_80=True,
        ),
        EvaluationRecord(
            forecast_id=uuid.uuid4(),
            model_run_id=run_id,
            series_key="rice_vary_gasy|standard|retail|MG11|kg",
            product_code="rice_vary_gasy",
            location_pcode="MG11",
            actor_level="retail",
            target_period=date(2026, 6, 1),
            horizon=2,
            evaluation_kind="matured_actual",
            model_name="AutoETS",
            is_baseline=False,
            predicted_p50=2800.0,
            predicted_p10=2400.0,
            predicted_p90=3000.0,
            actual_price=2400.0,
            actual_observation_id=uuid.uuid4(),
            absolute_error=400.0,
            percentage_error=400.0 / 2400.0,
            is_covered_80=True,
        ),
        EvaluationRecord(
            forecast_id=uuid.uuid4(),
            model_run_id=run_id,
            series_key="rice_vary_gasy|standard|retail|MG11|kg",
            product_code="rice_vary_gasy",
            location_pcode="MG11",
            actor_level="retail",
            target_period=date(2026, 7, 1),
            horizon=3,
            evaluation_kind="matured_actual",
            model_name="AutoETS",
            is_baseline=False,
            predicted_p50=3200.0,
            predicted_p10=2800.0,
            predicted_p90=3400.0,
            actual_price=3600.0,
            actual_observation_id=uuid.uuid4(),
            absolute_error=400.0,
            percentage_error=400.0 / 3600.0,
            is_covered_80=False,
        ),
    ]

    metrics = compute_metrics_for_records(records)
    assert metrics.sample_size == 3

    # Total actual = 2600 + 2400 + 3600 = 8600
    # Total abs_err = 100 + 400 + 400 = 900
    # WAPE = 900 / 8600 ≈ 0.10465
    assert pytest.approx(metrics.wape, rel=1e-3) == 900.0 / 8600.0
    # MAE = 900 / 3 = 300.0
    assert pytest.approx(metrics.mae, rel=1e-3) == 300.0
    # Coverage = 2 / 3 ≈ 0.6667
    assert pytest.approx(metrics.coverage_80, rel=1e-3) == 2.0 / 3.0
    assert metrics.coverage_ci_95 is not None
    # Mean width = (400 + 600 + 600) / 3 = 533.33
    assert pytest.approx(metrics.mean_interval_width, rel=1e-3) == 1600.0 / 3.0


def test_multidimensional_decomposition() -> None:
    """Verify strict multidimensional breakdown by product, location, horizon, and seasonality."""
    run_id = uuid.uuid4()
    records = [
        # Product rice_vary_gasy, Region MG11, Horizon 1, Month May (recolte)
        EvaluationRecord(
            forecast_id=uuid.uuid4(),
            model_run_id=run_id,
            series_key="rice_vary_gasy|standard|retail|MG11|kg",
            product_code="rice_vary_gasy",
            location_pcode="MG11",
            actor_level="retail",
            target_period=date(2026, 5, 1),
            horizon=1,
            evaluation_kind="matured_actual",
            model_name="AutoETS",
            is_baseline=False,
            predicted_p50=2500.0,
            predicted_p10=2300.0,
            predicted_p90=2700.0,
            actual_price=2500.0,
            actual_observation_id=uuid.uuid4(),
            absolute_error=0.0,
            percentage_error=0.0,
            is_covered_80=True,
        ),
        # Product maize, Region MG22, Horizon 2, Month December (soudure)
        EvaluationRecord(
            forecast_id=uuid.uuid4(),
            model_run_id=run_id,
            series_key="maize|standard|retail|MG22|kg",
            product_code="maize",
            location_pcode="MG22",
            actor_level="retail",
            target_period=date(2026, 12, 1),
            horizon=2,
            evaluation_kind="matured_actual",
            model_name="AutoETS",
            is_baseline=False,
            predicted_p50=1800.0,
            predicted_p10=1600.0,
            predicted_p90=2000.0,
            actual_price=2000.0,
            actual_observation_id=uuid.uuid4(),
            absolute_error=200.0,
            percentage_error=200.0 / 2000.0,
            is_covered_80=True,
        ),
    ]

    table = compute_performance_decomposition(records)

    # Check products
    assert "rice_vary_gasy" in table.by_product
    assert "maize" in table.by_product
    assert table.by_product["rice_vary_gasy"].wape == 0.0
    assert table.by_product["maize"].wape == 200.0 / 2000.0

    # Check locations
    assert "MG11" in table.by_location
    assert "MG22" in table.by_location
    assert table.by_location["MG11"].mae == 0.0
    assert table.by_location["MG22"].mae == 200.0

    # Check horizons
    assert 1 in table.by_horizon
    assert 2 in table.by_horizon
    assert table.by_horizon[1].sample_size == 1
    assert table.by_horizon[2].sample_size == 1

    # Check seasonality
    assert "recolte" in table.by_seasonality
    assert "soudure" in table.by_seasonality
    assert table.by_seasonality["recolte"].sample_size == 1
    assert table.by_seasonality["soudure"].sample_size == 1


def test_baseline_benchmarking_parsimony() -> None:
    """Verify parsimony rule: baseline wins if candidate gain <= 0.01 WAPE."""
    run_id = uuid.uuid4()

    # Case 1: Candidate gain is > 0.01 (significant)
    # Baseline WAPE = 0.20, Candidate WAPE = 0.15 -> delta = +0.05 > 0.01 -> candidate_winner
    rec_baseline = EvaluationRecord(
        forecast_id=uuid.uuid4(),
        model_run_id=run_id,
        series_key="rice|s|r|MG|kg",
        product_code="rice",
        location_pcode="MG",
        actor_level="retail",
        target_period=date(2026, 6, 1),
        horizon=1,
        evaluation_kind="matured_actual",
        model_name="NaiveLast",
        is_baseline=True,
        predicted_p50=2000.0,
        predicted_p10=1800.0,
        predicted_p90=2200.0,
        actual_price=2500.0,  # abs_err = 500, wape = 500/2500 = 0.20
        actual_observation_id=uuid.uuid4(),
        absolute_error=500.0,
        percentage_error=0.20,
        is_covered_80=False,
    )
    rec_candidate_sig = EvaluationRecord(
        forecast_id=uuid.uuid4(),
        model_run_id=run_id,
        series_key="rice|s|r|MG|kg",
        product_code="rice",
        location_pcode="MG",
        actor_level="retail",
        target_period=date(2026, 6, 1),
        horizon=1,
        evaluation_kind="matured_actual",
        model_name="AutoETS",
        is_baseline=False,
        predicted_p50=2375.0,
        predicted_p10=2100.0,
        predicted_p90=2600.0,
        actual_price=2500.0,  # abs_err = 125, wape = 125/2500 = 0.05
        actual_observation_id=uuid.uuid4(),
        absolute_error=125.0,
        percentage_error=0.05,
        is_covered_80=True,
    )

    res_sig = benchmark_against_baselines([rec_baseline, rec_candidate_sig])
    assert res_sig["best_baseline"] == "NaiveLast"
    comp_sig = res_sig["comparisons"][0]
    assert comp_sig["verdict"] == "candidate_winner"
    assert comp_sig["delta_wape"] > 0.01

    # Case 2: Candidate gain is marginal <= 0.01 (parsimony wins)
    # Baseline WAPE = 0.20, Candidate WAPE = 0.195 -> delta = +0.005 <= 0.01 -> baseline_winner
    rec_candidate_marginal = EvaluationRecord(
        forecast_id=uuid.uuid4(),
        model_run_id=run_id,
        series_key="rice|s|r|MG|kg",
        product_code="rice",
        location_pcode="MG",
        actor_level="retail",
        target_period=date(2026, 6, 1),
        horizon=1,
        evaluation_kind="matured_actual",
        model_name="AutoARIMA",
        is_baseline=False,
        predicted_p50=2012.5,
        predicted_p10=1800.0,
        predicted_p90=2200.0,
        actual_price=2500.0,  # abs_err = 487.5, wape = 487.5/2500 = 0.195
        actual_observation_id=uuid.uuid4(),
        absolute_error=487.5,
        percentage_error=0.195,
        is_covered_80=False,
    )

    res_parsimony = benchmark_against_baselines([rec_baseline, rec_candidate_marginal])
    comp_parsimony = res_parsimony["comparisons"][0]
    assert comp_parsimony["verdict"] == "baseline_winner"
    assert "parsimony threshold" in comp_parsimony["reason"]


def test_matured_forecast_evaluator_workflow() -> None:
    """Test MaturedForecastEvaluator with mock DB execution and tripartite status categorization."""
    mock_session = MagicMock()

    # Setup mock rows from ml.forecast query
    forecast_row_1 = MagicMock(
        forecast_id=uuid.uuid4(),
        model_run_id=uuid.uuid4(),
        series_key="rice_vary_gasy|standard|retail|MG11|kg",
        product_id=uuid.uuid4(),
        product_code="rice_vary_gasy",
        location_id=uuid.uuid4(),
        location_pcode="MG11",
        actor_level="retail",
        target_period=date(2026, 4, 1),  # matured
        horizon=1,
        p10=2200.0,
        p50=2400.0,
        p90=2600.0,
        model_name="AutoETS",
        is_baseline=False,
        data_cutoff=date(2026, 3, 1),
        run_eval_kind=None,
    )
    forecast_row_2 = MagicMock(
        forecast_id=uuid.uuid4(),
        model_run_id=uuid.uuid4(),
        series_key="rice_vary_gasy|standard|retail|MG11|kg",
        product_id=uuid.uuid4(),
        product_code="rice_vary_gasy",
        location_id=uuid.uuid4(),
        location_pcode="MG11",
        actor_level="retail",
        target_period=date(2026, 12, 1),  # prospective pending
        horizon=2,
        p10=2300.0,
        p50=2500.0,
        p90=2700.0,
        model_name="AutoETS",
        is_baseline=False,
        data_cutoff=date(2026, 3, 1),
        run_eval_kind=None,
    )

    # First call returns the forecasts
    mock_session.execute.return_value.fetchall.return_value = [forecast_row_1, forecast_row_2]

    # Obs queries return mock price
    obs_mock = MagicMock(price=2450.0)
    obs_uuid = uuid.uuid4()
    prov_mock = (obs_uuid,)

    def execute_side_effect(sql, params=None):
        sql_str = str(sql)
        res = MagicMock()
        if "FROM ml.forecast f" in sql_str:
            res.fetchall.return_value = [forecast_row_1, forecast_row_2]
        elif "FROM gold.price_monthly_best" in sql_str:
            res.fetchone.return_value = obs_mock
        elif "FROM obs.price_observation" in sql_str:
            res.fetchone.return_value = prov_mock
        else:
            res.fetchall.return_value = []
            res.fetchone.return_value = None
        return res

    mock_session.execute.side_effect = execute_side_effect

    evaluator = MaturedForecastEvaluator(mock_session)
    # Evaluate as of May 1, 2026
    perf_table = evaluator.evaluate_forecasts(
        evaluation_date=date(2026, 5, 1),
        persist=False,
    )

    assert len(perf_table.records) == 2

    # Verify rec 1 is matured_actual
    rec1 = perf_table.records[0]
    assert rec1.evaluation_kind == "matured_actual"
    assert rec1.actual_price == 2450.0
    assert rec1.actual_observation_id == obs_uuid
    assert rec1.absolute_error == 50.0  # |2450 - 2400|
    assert rec1.is_covered_80 is True  # 2200 <= 2450 <= 2600

    # Verify rec 2 is prospective_pending (target Dec 2026 > eval May 2026)
    rec2 = perf_table.records[1]
    assert rec2.evaluation_kind == "prospective_pending"
    assert rec2.actual_price is None
    assert rec2.actual_observation_id is None
    assert rec2.absolute_error is None


def test_api_forecast_performance_endpoint() -> None:
    """Verify GET /v1/forecasts/performance with JSON and CSV exports."""
    mock_session = MagicMock()

    # Mock count = 1 so it doesn't try to trigger evaluation
    mock_session.execute.return_value.fetchone.return_value = (1,)

    eval_uuid = uuid.uuid4()
    fc_uuid = uuid.uuid4()
    run_uuid = uuid.uuid4()
    obs_uuid = uuid.uuid4()

    mock_eval_row = MagicMock(
        evaluation_id=eval_uuid,
        forecast_id=fc_uuid,
        model_run_id=run_uuid,
        series_key="rice_vary_gasy|standard|retail|MG11|kg",
        product_code="rice_vary_gasy",
        location_pcode="MG11",
        actor_level="retail",
        target_period=date(2026, 5, 1),
        horizon=1,
        evaluation_kind="matured_actual",
        model_name="AutoETS",
        is_baseline=False,
        predicted_p50=2500.0,
        predicted_p10=2300.0,
        predicted_p90=2700.0,
        actual_price=2550.0,
        actual_observation_id=obs_uuid,
        absolute_error=50.0,
        percentage_error=50.0 / 2550.0,
        is_covered_80=True,
        evaluated_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    def execute_side_effect(sql, params=None):
        sql_str = str(sql)
        res = MagicMock()
        if "COUNT(*)" in sql_str:
            res.fetchone.return_value = (1,)
        elif "FROM ml.forecast_evaluation" in sql_str:
            res.fetchall.return_value = [mock_eval_row]
        else:
            res.fetchall.return_value = []
            res.fetchone.return_value = None
        return res

    mock_session.execute.side_effect = execute_side_effect

    app.dependency_overrides[get_db] = lambda: mock_session
    client = TestClient(app)

    try:
        # 1. Test JSON response
        resp = client.get("/v1/forecasts/performance?product=rice_vary_gasy")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "by_product" in data
        assert "by_location" in data
        assert "by_horizon" in data
        assert "by_seasonality" in data
        assert "evaluations" in data
        assert data["total_evaluations"] == 1
        eval_item = data["evaluations"][0]
        assert eval_item["product_code"] == "rice_vary_gasy"
        assert eval_item["is_covered_80"] is True
        assert eval_item["actual_price"] == 2550.0

        # 2. Test CSV export
        resp_csv = client.get("/v1/forecasts/performance?format=csv")
        assert resp_csv.status_code == 200
        assert "text/csv" in resp_csv.headers["content-type"]
        assert "rice_vary_gasy" in resp_csv.text
        assert "2550.0" in resp_csv.text
    finally:
        app.dependency_overrides.clear()
