"""Orchestrator for price forecasting pipeline and persistence (SPECS §17).

Extracts eligible series up to data_cutoff, conducts rolling-origin backtests,
fits selected models, generates p10/p50/p90 quantiles, and persists runs & forecasts.
"""

from __future__ import annotations

import subprocess
import uuid
from datetime import UTC, date, datetime
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from ketrika.core.logging import get_logger
from ketrika.core.models.db import Forecast, ModelRun
from ketrika.gold.refresh import refresh_gold_views
from ketrika.ml.backtest import BacktestResult, select_best_model
from ketrika.ml.models import (
    AutoARIMAModel,
    AutoETSModel,
    DeterministicBaselineModel,
    ForecastPrediction,
    SeasonalNaiveModel,
)
from ketrika.ml.series import extract_eligible_series

logger = get_logger(__name__)


def get_git_sha() -> str:
    """Return short git commit sha or fallback."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        )
        return out.decode("ascii").strip()
    except Exception:
        return "local"


def get_future_month_starts(base_date: date, count: int) -> list[date]:
    """Compute 1st day of subsequent months following base_date."""
    year = base_date.year
    month = base_date.month
    dates: list[date] = []
    for _ in range(count):
        month += 1
        if month > 12:
            month = 1
            year += 1
        dates.append(date(year, month, 1))
    return dates


def _instantiate_model(name: str) -> Any:
    """Instantiate model by its name."""
    if name == "AutoETS":
        return AutoETSModel()
    elif name == "AutoARIMA":
        return AutoARIMAModel()
    elif name == "SeasonalNaive":
        return SeasonalNaiveModel()
    else:
        return DeterministicBaselineModel(name=name)


def run_price_forecasting_pipeline(
    session: Session,
    data_cutoff: date,
    horizon: int = 3,
    min_points: int | None = None,
    refresh_gold: bool = True,
) -> dict[str, Any]:
    """Execute complete price forecasting workflow per SPECS §17.

    1. Extract eligible price series up to data_cutoff (strictly anti-leakage).
    2. Rolling-origin backtest on each series across candidate models.
    3. Select best model based on WAPE.
    4. Fit and predict h=1..horizon steps ahead.
    5. Persist run and forecast rows in ml schema.
    6. Refresh gold.forecast_latest materialized view.
    """
    logger.info(
        "starting_price_forecasting",
        data_cutoff=data_cutoff.isoformat(),
        horizon=horizon,
        min_points=min_points,
    )

    series_list = extract_eligible_series(
        session=session,
        data_cutoff=data_cutoff,
        min_points=min_points,
    )

    if not series_list:
        logger.warning(
            "no_eligible_series_for_forecasting",
            data_cutoff=data_cutoff.isoformat(),
        )
        return {
            "status": "skipped",
            "reason": "no_eligible_series",
            "n_series": 0,
            "forecasts_generated": 0,
        }

    target_dates = get_future_month_starts(data_cutoff, horizon)
    model_version = f"1.0.0@{get_git_sha()}"

    by_series_metrics: dict[str, Any] = {}
    forecast_objects: list[Forecast] = []
    wapes: list[float] = []
    maes: list[float] = []
    smapes: list[float] = []
    coverages: list[float] = []

    model_run_id = uuid.uuid4()

    for s in series_list:
        y = np.array([pt.price for pt in s.points], dtype=float)

        # 1. Backtest selection
        bt_res: BacktestResult = select_best_model(
            series_key=s.series_key,
            y=y,
            h=horizon,
            max_windows=6,
        )

        wapes.append(bt_res.best_metrics.wape)
        maes.append(bt_res.best_metrics.mae)
        smapes.append(bt_res.best_metrics.smape)
        coverages.append(bt_res.best_metrics.coverage_80)

        by_series_metrics[s.series_key] = {
            "product_code": s.product_code,
            "location_pcode": s.location_pcode,
            "actor_level": s.actor_level,
            "best_model": bt_res.best_model_name,
            "metrics": bt_res.best_metrics.to_dict(),
            "evaluations": {name: m.to_dict() for name, m in bt_res.evaluations.items()},
        }

        # 2. Fit winner on all history and generate final predictions
        winner_model = _instantiate_model(bt_res.best_model_name)
        pred: ForecastPrediction = winner_model.fit_predict(y, h=horizon)

        # 3. Create Forecast entities for horizons 1..horizon
        for h_step in range(1, horizon + 1):
            idx = h_step - 1
            tgt_date = target_dates[idx]
            fc = Forecast(
                forecast_id=uuid.uuid4(),
                model_run_id=model_run_id,
                series_key=s.series_key,
                product_id=s.product_id,
                location_id=s.location_id,
                actor_level=s.actor_level,
                target_period=tgt_date,
                horizon=h_step,
                p10=float(pred.p10[idx]),
                p50=float(pred.mean[idx]),
                p90=float(pred.p90[idx]),
                generated_at=datetime.now(UTC),
            )
            forecast_objects.append(fc)

    # Calculate overall aggregate metrics
    overall_metrics = {
        "wape": round(float(np.mean(wapes)), 4) if wapes else 0.0,
        "mae": round(float(np.mean(maes)), 2) if maes else 0.0,
        "smape": round(float(np.mean(smapes)), 4) if smapes else 0.0,
        "coverage_80": round(float(np.mean(coverages)), 4) if coverages else 0.0,
        "n_series": len(series_list),
        "by_series": by_series_metrics,
    }

    model_run = ModelRun(
        model_run_id=model_run_id,
        task="price_forecast",
        model_name="best_model_selection",
        model_version=model_version,
        data_cutoff=data_cutoff,
        trained_at=datetime.now(UTC),
        params={"horizon": horizon, "candidates": ["SeasonalNaive", "AutoETS", "AutoARIMA"]},
        metrics=overall_metrics,
    )

    session.add(model_run)
    for fc in forecast_objects:
        session.add(fc)
    session.flush()

    if refresh_gold:
        refresh_gold_views(session, views=["forecast_latest"])

    logger.info(
        "price_forecasting_complete",
        model_run_id=str(model_run_id),
        n_series=len(series_list),
        n_forecasts=len(forecast_objects),
        avg_wape=overall_metrics["wape"],
    )

    return {
        "model_run_id": str(model_run_id),
        "n_series": len(series_list),
        "forecasts_generated": len(forecast_objects),
        "metrics": overall_metrics,
    }
