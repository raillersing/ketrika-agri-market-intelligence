"""Orchestrator for price forecasting pipeline, metadata, and persistence (SPECS §17, §19, ADR-078).

Extracts eligible series up to data_cutoff, conducts rolling-origin backtests,
fits selected models, calibrates conformal intervals, preserves abstentions and lineage,
and persists runs & forecasts without destructive overwrites.
"""

from __future__ import annotations

import hashlib
import subprocess
import uuid
from datetime import UTC, date, datetime
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.core.logging import get_logger
from ketrika.core.models.db import Event, Forecast, MacroObservation, ModelRun, WeatherObservation
from ketrika.gold.refresh import refresh_gold_views
from ketrika.ml.backtest import BacktestResult, select_best_model
from ketrika.ml.causal_model import CausalAgriculturalModel
from ketrika.ml.conformal import calibrate_conformal_bounds
from ketrika.ml.models import (
    AutoARIMAModel,
    AutoETSModel,
    DeterministicBaselineModel,
    ForecastModel,
    ModelForecastResult,
    NaiveLastModel,
    SeasonalNaiveModel,
)
from ketrika.ml.series import audit_series_eligibility

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


def _instantiate_model(name: str) -> ForecastModel | DeterministicBaselineModel:
    """Instantiate candidate model by its canonical name."""
    if name == "NaiveLast":
        return NaiveLastModel()
    elif name == "CausalAgriculturalModel":
        return CausalAgriculturalModel()
    elif name == "AutoETS":
        return AutoETSModel()
    elif name == "AutoARIMA":
        return AutoARIMAModel()
    elif name == "SeasonalNaive":
        return SeasonalNaiveModel()
    else:
        return DeterministicBaselineModel(name=name)


def compute_series_fingerprint(data_cutoff: date, series_list: list[Any]) -> str:
    """Compute deterministic SHA-256 fingerprint for forecasting input snapshot."""
    hasher = hashlib.sha256()
    hasher.update(data_cutoff.isoformat().encode("utf-8"))
    for s in sorted(series_list, key=lambda x: str(x.series_key)):
        hasher.update(str(s.series_key).encode("utf-8"))
        for pt in s.points:
            pt_repr = f"{pt.month.isoformat()}:{pt.price}:{pt.observed_or_imputed}"
            hasher.update(pt_repr.encode("utf-8"))
    return hasher.hexdigest()


def run_price_forecasting_pipeline(
    session: Session,
    data_cutoff: date,
    horizon: int = 6,
    min_points: int | None = None,
    cohort: str = "all",
    dataset_fingerprint: str | None = None,
    refresh_gold: bool = True,
) -> dict[str, Any]:
    """Execute complete price forecasting workflow per SPECS §17 and ADR-078.

    1. Audit and extract eligible price series up to data_cutoff (strictly anti-leakage).
    2. Collect documented abstentions and series exclusions with normative reasons.
    3. Rolling-origin backtest on each series across candidate models (6 windows, h=3).
    4. Select winning model based on WAPE and simplicity ranking.
    5. Fit winner and predict h=1..horizon steps ahead.
    6. Calibrate conformal intervals (p10, p90) on past residuals with N_calib >= 8 check.
    7. Persist run and forecast rows in ml schema with immutable lineage (C4).
    8. Refresh gold.forecast_latest materialized view.
    """
    logger.info(
        "starting_price_forecasting",
        data_cutoff=data_cutoff.isoformat(),
        horizon=horizon,
        min_points=min_points,
        cohort=cohort,
    )

    # 1. Audit series eligibility and identify exclusions
    require_observed_only = cohort == "pure_observed"
    audit_report = audit_series_eligibility(
        session=session,
        data_cutoff=data_cutoff,
        min_total_points=min_points or 36,
        require_observed_only=require_observed_only,
    )

    eligible_series = audit_report.eligible_series
    abstentions_list: list[dict[str, Any]] = [
        {
            "series_key": ex.series_key,
            "product_code": ex.product_code,
            "location_pcode": ex.location_pcode,
            "actor_level": ex.actor_level,
            "reason": ", ".join(ex.reasons) if ex.reasons else "excluded",
            "points_count": ex.total_valid_points,
        }
        for ex in audit_report.excluded_series
    ]

    # Compute lineage fingerprint
    computed_fingerprint = dataset_fingerprint or compute_series_fingerprint(
        data_cutoff, eligible_series
    )

    if not eligible_series:
        logger.warning(
            "no_eligible_series_for_forecasting",
            data_cutoff=data_cutoff.isoformat(),
            n_excluded=len(abstentions_list),
        )
        return {
            "status": "abstained",
            "reason": "no_eligible_series",
            "n_series": 0,
            "forecasts_generated": 0,
            "n_abstentions": len(abstentions_list),
            "abstentions": abstentions_list,
            "dataset_fingerprint": computed_fingerprint,
        }

    target_dates = get_future_month_starts(data_cutoff, horizon)
    model_version = f"1.0.0@{get_git_sha()}"
    model_run_id = uuid.uuid4()

    # Pre-fetch macroeconomic indicators up to data_cutoff (anti-leakage C022)
    macro_records = (
        session.execute(
            select(MacroObservation)
            .where(
                MacroObservation.superseded_by.is_(None),
                MacroObservation.period_start <= data_cutoff,
            )
            .order_by(MacroObservation.period_start)
        )
        .scalars()
        .all()
    )
    macro_by_ind: dict[str, dict[date, float]] = {}
    for m_rec in macro_records:
        if m_rec.value is not None:
            macro_by_ind.setdefault(m_rec.indicator_code, {})[m_rec.period_start] = float(m_rec.value)

    # Pre-fetch events up to data_cutoff
    event_records = (
        session.execute(
            select(Event)
            .where(Event.event_date <= data_cutoff)
            .order_by(Event.event_date)
        )
        .scalars()
        .all()
    )
    events_payload = [
        {
            "event_id": str(ev.event_id),
            "event_type": ev.event_type,
            "title": ev.title,
            "event_date": ev.event_date,
            "severity": ev.severity,
            "product_ids": [str(p) for p in (ev.product_ids or [])],
            "location_ids": [str(loc) for loc in (ev.location_ids or [])],
        }
        for ev in event_records
    ]

    by_series_metrics: dict[str, Any] = {}
    forecast_objects: list[Forecast] = []
    wapes: list[float] = []
    maes: list[float] = []
    smapes: list[float] = []
    coverages: list[float] = []

    for s in eligible_series:
        pts = [p for p in s.grid if p.price is not None]
        s_dates = [p.month for p in pts]
        y = np.array([p.price for p in pts], dtype=float)

        # Align macro indicators to series dates
        aligned_macro: dict[str, np.ndarray] = {}
        for ind_code, date_val_map in macro_by_ind.items():
            arr = []
            last_known = 0.0
            for d in s_dates:
                if d in date_val_map:
                    last_known = date_val_map[d]
                arr.append(last_known)
            aligned_macro[ind_code] = np.array(arr, dtype=float)

        # 2. Backtest selection (rolling-origin 6 windows)
        bt_res: BacktestResult = select_best_model(
            series_key=s.series_key,
            y=y,
            h=horizon,
            max_windows=6,
            dates=s_dates,
            macro_series=aligned_macro,
            events=events_payload,
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

        # 3. Fit winner on historical series and generate predictions
        winner_instance = _instantiate_model(bt_res.best_model_name)
        if getattr(winner_instance, "name", "") == "CausalAgriculturalModel":
            fit_res: ModelForecastResult = winner_instance.fit_predict(  # type: ignore
                y,
                h=horizon,
                unit=s.unit,
                currency="MGA",
                dates=s_dates,
                series_key=s.series_key,
                macro_series=aligned_macro,
                events=events_payload,
            )
        else:
            fit_res = winner_instance.fit_predict(
                y,
                h=horizon,
                unit=s.unit,
                currency="MGA",
            )

        # 4. Conformal calibration on historical residuals
        valid_y = y[~np.isnan(y)]
        past_residuals: list[float] = []
        if len(valid_y) > 1:
            past_residuals = [
                float(abs(valid_y[i] - valid_y[i - 1])) for i in range(1, len(valid_y))
            ]

        # Calibrate bounds via non-parametric conformal quantile
        conformal_res = calibrate_conformal_bounds(
            point_forecasts=fit_res.prediction.mean,
            calibration_residuals=past_residuals,
            target_coverage=0.80,
            min_residuals=8,
        )

        is_calibrated = conformal_res.is_calibrated
        calib_size = conformal_res.calibration_sample_size
        final_p10 = conformal_res.p10
        final_p90 = conformal_res.p90
        interval_widths = conformal_res.width

        is_baseline = bt_res.best_model_name in (
            "NaiveLast",
            "SeasonalNaive",
        ) or fit_res.model_effective in ("NaiveLast", "SeasonalNaive")
        series_status = (
            "baseline_fallback" if (fit_res.status == "fallback" or is_baseline) else fit_res.status
        )

        # 5. Create Forecast entities for horizons 1..horizon
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
                p10=float(final_p10[idx]),
                p50=float(fit_res.prediction.mean[idx]),
                p90=float(final_p90[idx]),
                model_requested=fit_res.model_requested,
                model_effective=fit_res.model_effective,
                is_baseline=is_baseline,
                is_calibrated=is_calibrated,
                calibration_sample_size=calib_size,
                status=series_status,
                fallback_reason=fit_res.fallback_reason,
                currency="MGA",
                unit=s.unit,
                interval_width=float(interval_widths[idx]),
                coverage_rate_80=float(bt_res.best_metrics.coverage_80),
                generated_at=datetime.now(UTC),
            )
            forecast_objects.append(fc)

    # Calculate overall aggregate metrics
    overall_metrics = {
        "wape": round(float(np.mean(wapes)), 4) if wapes else 0.0,
        "mae": round(float(np.mean(maes)), 2) if maes else 0.0,
        "smape": round(float(np.mean(smapes)), 4) if smapes else 0.0,
        "coverage_80": round(float(np.mean(coverages)), 4) if coverages else 0.0,
        "n_series": len(eligible_series),
        "by_series": by_series_metrics,
        "abstentions": abstentions_list,
    }

    # 6. Persist ModelRun entity
    model_run = ModelRun(
        model_run_id=model_run_id,
        task="price_forecast",
        model_name="best_model_selection",
        model_version=model_version,
        data_cutoff=data_cutoff,
        trained_at=datetime.now(UTC),
        params={
            "horizon": horizon,
            "candidates": [
                "NaiveLast",
                "SeasonalNaive",
                "CausalAgriculturalModel",
                "AutoETS",
                "AutoARIMA",
            ],
            "cohort": cohort,
            "dataset_fingerprint": computed_fingerprint,
        },
        metrics=overall_metrics,
    )

    session.add(model_run)
    for fc in forecast_objects:
        session.add(fc)
    session.flush()

    if refresh_gold:
        try:
            refresh_gold_views(session, views=["forecast_latest"])
        except Exception as exc:
            logger.warning("gold_refresh_fallback_sql", reason=str(exc))
            from sqlalchemy import text
            session.execute(text("REFRESH MATERIALIZED VIEW gold.forecast_latest;"))
            session.flush()

    session.commit()

    logger.info(
        "price_forecasting_complete",
        model_run_id=str(model_run_id),
        n_series=len(eligible_series),
        n_forecasts=len(forecast_objects),
        n_abstentions=len(abstentions_list),
        avg_wape=overall_metrics["wape"],
    )

    return {
        "model_run_id": str(model_run_id),
        "n_series": len(eligible_series),
        "forecasts_generated": len(forecast_objects),
        "n_abstentions": len(abstentions_list),
        "abstentions": abstentions_list,
        "metrics": overall_metrics,
        "dataset_fingerprint": computed_fingerprint,
    }


if __name__ == "__main__":
    import argparse

    from ketrika.core.db import get_session

    parser = argparse.ArgumentParser(description="Run Ketrika price forecasting pipeline")
    parser.add_argument("--cutoff", type=str, default=None, help="Cutoff date YYYY-MM-DD")
    parser.add_argument("--horizon", type=int, default=6, help="Forecast horizon (months)")
    parser.add_argument("--cohort", type=str, default="all", help="pure_observed, mixed, or all")
    args = parser.parse_args()

    cutoff_date = date.fromisoformat(args.cutoff) if args.cutoff else date.today()
    with get_session() as session:
        res = run_price_forecasting_pipeline(
            session=session,
            data_cutoff=cutoff_date,
            horizon=args.horizon,
            cohort=args.cohort,
            refresh_gold=True,
        )
        session.commit()
        print(
            f"Forecasting complete: {res['forecasts_generated']} forecasts generated across {res['n_series']} series."
        )
