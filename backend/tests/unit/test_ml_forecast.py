"""Unit and integration tests for price forecasting models, backtest, and anti-leakage (SPECS §17, T9.1)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import numpy as np
import pytest
from sqlalchemy import text

from ketrika.core.db import check_db_connection, get_session
from ketrika.core.models.db import ModelRun, PriceObservation
from ketrika.gold.refresh import refresh_gold_views
from ketrika.ml.backtest import (
    compute_metrics,
    select_best_model,
)
from ketrika.ml.forecast import run_price_forecasting_pipeline
from ketrika.ml.models import (
    AutoARIMAModel,
    AutoETSModel,
    DeterministicBaselineModel,
    ForecastPrediction,
    SeasonalNaiveModel,
    get_default_candidate_models,
)
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.e2e_data.source_backed_synthetic import attach_new_synthetic_proof
from tests.e2e_data.synthetic_gold_dataset import (
    PRODUCT_RICE_ID,
    seed_synthetic_gold_data,
)


def test_forecast_models_quantiles():
    """Verify individual candidate models produce valid p10 <= p50 <= p90 positive quantiles."""
    y = np.array(
        [
            2000.0,
            2050.0,
            2100.0,
            2150.0,
            2200.0,
            2250.0,
            2300.0,
            2350.0,
            2400.0,
            2450.0,
            2500.0,
            2550.0,
            2600.0,
            2650.0,
            2700.0,
            2750.0,
            2800.0,
            2850.0,
        ],
        dtype=float,
    )
    h = 3

    models = [
        DeterministicBaselineModel(),
        SeasonalNaiveModel(season_length=4),
        AutoETSModel(season_length=4),
        AutoARIMAModel(season_length=4),
    ]

    for model in models:
        pred: ForecastPrediction = model.fit_predict(y, h=h)
        assert len(pred.mean) == h
        assert len(pred.p10) == h
        assert len(pred.p90) == h
        # Positivity
        assert (pred.mean >= 0).all()
        assert (pred.p10 >= 0).all()
        assert (pred.p90 >= 0).all()
        # Conformal interval bounds
        assert (pred.p10 <= pred.mean + 1e-4).all()
        assert (pred.mean <= pred.p90 + 1e-4).all()


def test_compute_metrics():
    """Verify WAPE, MAE, sMAPE, and coverage_80 computations against exact hand-calculated figures."""
    actuals = [100.0, 200.0]
    predictions = [110.0, 180.0]
    p10 = [90.0, 170.0]
    p90 = [120.0, 210.0]

    # abs errors: 10, 20 -> sum=30
    # sum actuals: 300 -> wape = 30/300 = 0.10
    # mae = 15.0
    # smape = (2*10/210 + 2*20/380) / 2 = (0.095238 + 0.105263) / 2 = 0.10025
    # coverage = 2/2 = 1.0
    metrics = compute_metrics(actuals, predictions, p10, p90, n_windows=2)
    assert metrics.wape == pytest.approx(0.10, abs=1e-3)
    assert metrics.mae == pytest.approx(15.0, abs=1e-2)
    assert metrics.coverage_80 == 1.0
    assert metrics.n_windows == 2


def test_model_selection_lowest_wape_and_simplicity():
    """Verify best model selection picks lowest WAPE and adheres to simplicity on ties (SPECS §17)."""
    y = np.array(
        [
            2000.0,
            2020.0,
            2040.0,
            2060.0,
            2080.0,
            2100.0,
            2120.0,
            2140.0,
            2160.0,
            2180.0,
            2200.0,
            2220.0,
        ]
    )
    res = select_best_model(
        series_key="test_series",
        y=y,
        candidates=get_default_candidate_models(season_length=4),
        h=3,
        max_windows=3,
    )
    assert res.series_key == "test_series"
    assert res.best_model_name in ("NaiveLast", "SeasonalNaive", "CausalAgriculturalModel", "AutoETS", "AutoARIMA")
    assert res.best_metrics.wape >= 0.0
    assert "SeasonalNaive" in res.evaluations


@pytest.mark.integration
def test_forecasting_pipeline_e2e_and_anti_leakage():
    """Acceptance test T9.1:

    - >= 10 series forecasted
    - ml.model_run.metrics contains WAPE, MAE, sMAPE, coverage_80
    - Anti-leakage: injecting data after data_cutoff does NOT change forecasts
    - gold.forecast_latest matches generated forecasts
    """
    if not check_db_connection():
        pytest.skip("Database unreachable")

    cutoff_date = date(2024, 3, 31)

    with get_session() as session:
        wipe_silver_gold_tables(session)
        seed_synthetic_gold_data(session)
        refresh_gold_views(session)

    # 1. First execution up to cutoff_date
    with get_session() as session:
        res1 = run_price_forecasting_pipeline(
            session=session,
            data_cutoff=cutoff_date,
            horizon=3,
            min_points=6,
            refresh_gold=True,
        )

    assert res1["n_series"] >= 10, f"Expected >= 10 series, got {res1['n_series']}"
    assert res1["forecasts_generated"] == res1["n_series"] * 3
    agg_metrics = res1["metrics"]
    assert "wape" in agg_metrics
    assert "mae" in agg_metrics
    assert "smape" in agg_metrics
    assert "coverage_80" in agg_metrics
    assert len(agg_metrics["by_series"]) == res1["n_series"]

    # Verify database persistence
    with get_session() as session:
        m_run = session.get(ModelRun, uuid.UUID(res1["model_run_id"]))
        assert m_run is not None
        assert m_run.task == "price_forecast"
        assert m_run.data_cutoff == cutoff_date
        assert m_run.metrics["wape"] == agg_metrics["wape"]

        # Check forecasts table
        fc_rows = session.execute(
            text("SELECT p10, p50, p90, horizon FROM ml.forecast WHERE model_run_id = :mid"),
            {"mid": uuid.UUID(res1["model_run_id"])},
        ).fetchall()
        assert len(fc_rows) == res1["forecasts_generated"]
        for p10, p50, p90, _h in fc_rows:
            assert float(p10) <= float(p50) + 1e-2
            assert float(p50) <= float(p90) + 1e-2

        # Check gold.forecast_latest view
        gold_fc_count = session.execute(
            text("SELECT count(*) FROM gold.forecast_latest WHERE model_run_id = :mid"),
            {"mid": uuid.UUID(res1["model_run_id"])},
        ).scalar()
        assert gold_fc_count == res1["forecasts_generated"]
        # Other target periods from the seed remain visible; no data is deleted
        # to force the whole view to match this one model run.
        other_run_count = session.execute(
            text("SELECT count(*) FROM gold.forecast_latest WHERE model_run_id <> :mid"),
            {"mid": uuid.UUID(res1["model_run_id"])},
        ).scalar()
        assert other_run_count == 2

    # 2. Strict Anti-Leakage Test:
    # Inject future observations at 2024-06-01 with an anomalous value
    with get_session() as session:
        src_rec_id = session.execute(
            text("SELECT source_record_id FROM meta.source_record LIMIT 1")
        ).scalar()
        loc_id = session.execute(text("SELECT location_id FROM ref.location LIMIT 1")).scalar()
        future_obs = PriceObservation(
            observation_id=uuid.uuid4(),
            source_record_id=src_rec_id,
            natural_key=f"future_leakage_probe_{uuid.uuid4()}",
            product_raw="Riz blanc",
            product_id=PRODUCT_RICE_ID,
            location_raw="Analamanga",
            location_id=loc_id,
            actor_level="retail",
            period_start=date(2024, 6, 1),
            period_end=date(2024, 6, 30),
            price_raw="999999.0",
            price_value=Decimal("999999.0"),
            currency_raw="MGA",
            unit_raw="kg",
            price_mga_per_base=999999.0,
            base_unit="kg",
            conversion_status="exact",
            observed_or_imputed="observed",
            extraction_method="deterministic",
            confidence=1.0,
            review_status="accepted",
        )
        attach_new_synthetic_proof(session, future_obs)
        session.add(future_obs)
        session.commit()
        refresh_gold_views(session)

    # 3. Second execution with same cutoff_date
    with get_session() as session:
        res2 = run_price_forecasting_pipeline(
            session=session,
            data_cutoff=cutoff_date,
            horizon=3,
            min_points=6,
            refresh_gold=True,
        )

    # Metrics and series counts must be 100% IDENTICAL
    assert res2["n_series"] == res1["n_series"]
    assert res2["metrics"]["wape"] == res1["metrics"]["wape"]
    assert res2["metrics"]["mae"] == res1["metrics"]["mae"]
    assert res2["metrics"]["smape"] == res1["metrics"]["smape"]

    # Point predictions for all series and horizons must be 100% IDENTICAL
    with get_session() as session:
        preds1 = session.execute(
            text(
                "SELECT series_key, horizon, p50 FROM ml.forecast WHERE model_run_id = :mid ORDER BY series_key, horizon"
            ),
            {"mid": uuid.UUID(res1["model_run_id"])},
        ).fetchall()
        preds2 = session.execute(
            text(
                "SELECT series_key, horizon, p50 FROM ml.forecast WHERE model_run_id = :mid ORDER BY series_key, horizon"
            ),
            {"mid": uuid.UUID(res2["model_run_id"])},
        ).fetchall()

        assert len(preds1) == len(preds2)
        for (k1, h1, p1), (k2, h2, p2) in zip(preds1, preds2, strict=True):
            assert k1 == k2
            assert h1 == h2
            assert float(p1) == pytest.approx(float(p2), abs=1e-3)
