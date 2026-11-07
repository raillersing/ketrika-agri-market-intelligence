"""Forecasts router (SPECS §17, §19, ADR-078).

Exposes current and historical price forecasts, conformal prediction intervals,
model run lineage (C4), and documented series abstentions with CSV/JSON exports.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.api.csv_utils import export_csv_response
from ketrika.api.gold_availability import require_gold_view
from ketrika.api.schemas import (
    ForecastAbstentionItem,
    ForecastEvaluationItem,
    ForecastItem,
    ForecastPerformanceResponse,
    ModelExtrapolationTrajectory,
    ModelRunDetailResponse,
    ModelRunSummaryItem,
    MultiModelExtrapolationResponse,
    PerformanceMetricsSummary,
)
from ketrika.core.db import get_db
from ketrika.core.taxonomy import resolve_product
from ketrika.ml.evaluation import (
    EvaluationRecord,
    MaturedForecastEvaluator,
    compute_performance_decomposition,
)

router = APIRouter(prefix="/v1/forecasts", tags=["forecasts"])


@router.get("", response_model=list[ForecastItem])
def get_forecasts(
    product: str | None = Query(None, description="Product code or UUID"),
    location: str | None = Query(None, description="Location P-code or UUID"),
    actor_level: str | None = Query(None, description="Actor level (e.g. retail, wholesale)"),
    model_run_id: str | None = Query(None, description="Specific historical model_run_id (UUID)"),
    limit: int = Query(100, ge=1, le=1000, description="Page limit (default 100, max 1000)"),
    offset: int = Query(0, ge=0, description="Page offset (default 0)"),
    format: str = Query("json", pattern="^(json|csv)$", description="Output format (json or csv)"),
    session: Session = Depends(get_db),
) -> Any:
    """Retrieve the latest or historical price forecasts with conformal intervals (SPECS §17, §19, ADR-078)."""
    if not model_run_id:
        require_gold_view(session, "forecast_latest")

    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if model_run_id:
        # Query specific historical run from ml schema
        sql = """
            SELECT
                f.forecast_id,
                f.model_run_id,
                f.series_key,
                p.product_code,
                p.canonical_name_fr AS product_name,
                loc.pcode AS location_pcode,
                loc.name AS location_name,
                f.actor_level,
                f.horizon,
                f.target_period::text,
                f.p10::float,
                f.p50::float,
                f.p90::float,
                f.model_requested,
                COALESCE(f.model_effective, mr.model_name) AS model_effective,
                f.is_baseline,
                f.is_calibrated,
                f.calibration_sample_size,
                f.status,
                f.fallback_reason,
                f.currency,
                f.unit,
                f.interval_width::float,
                f.coverage_rate_80::float,
                mr.data_cutoff::text,
                mr.params->>'dataset_fingerprint' AS dataset_fingerprint,
                mr.params->>'cohort' AS cohort
            FROM ml.forecast f
            JOIN ml.model_run mr ON f.model_run_id = mr.model_run_id
            LEFT JOIN ref.product p ON f.product_id = p.product_id
            LEFT JOIN ref.location loc ON f.location_id = loc.location_id
            WHERE f.model_run_id = :run_id
        """
        params["run_id"] = model_run_id
    else:
        # Query latest materialized view
        sql = """
            SELECT
                forecast_id,
                model_run_id,
                series_key,
                product_code,
                product_name,
                location_pcode,
                location_name,
                actor_level,
                horizon,
                target_period::text,
                p10::float,
                p50::float,
                p90::float,
                model_requested,
                model_effective,
                is_baseline,
                is_calibrated,
                calibration_sample_size,
                status,
                fallback_reason,
                currency,
                unit,
                interval_width::float,
                coverage_rate_80::float,
                data_cutoff::text,
                dataset_fingerprint,
                cohort
            FROM gold.forecast_latest
            WHERE 1=1
        """

    if product:
        resolved = resolve_product(product, min_confidence=0.9)
        canonical = resolved[0] if resolved else None
        if canonical and canonical != product:
            sql += " AND (product_code = :product OR product_code = :canonical OR product_id::text = :product)"
            params["canonical"] = canonical
        else:
            sql += " AND (product_code = :product OR product_id::text = :product)"
        params["product"] = product
    if location:
        sql += " AND (location_pcode = :loc OR location_id::text = :loc)"
        params["loc"] = location
    if actor_level:
        sql += " AND actor_level = :actor"
        params["actor"] = actor_level

    sql += " ORDER BY product_code, location_pcode, horizon ASC LIMIT :limit OFFSET :offset;"
    rows = session.execute(text(sql), params).fetchall()

    results: list[ForecastItem] = []
    csv_rows: list[dict[str, Any]] = []

    for r in rows:
        item = ForecastItem(
            forecast_id=r[0],
            model_run_id=r[1],
            series_key=r[2],
            product_code=r[3],
            product_name=r[4],
            location_pcode=r[5] or "MDG",
            location_name=r[6],
            actor_level=r[7],
            horizon=int(r[8]),
            target_period=str(r[9]),
            p10=float(r[10]) if r[10] is not None else None,
            p50=float(r[11]),
            p90=float(r[12]) if r[12] is not None else None,
            model_requested=r[13],
            model_effective=r[14] or "NaiveLast",
            model_name=r[14] or "NaiveLast",
            is_baseline=bool(r[15]),
            is_calibrated=bool(r[16]),
            calibration_sample_size=int(r[17] or 0),
            status=r[18] or "nominal",
            fallback_reason=r[19],
            currency=r[20] or "MGA",
            unit=r[21] or "kg",
            interval_width=float(r[22]) if r[22] is not None else None,
            coverage_rate_80=float(r[23]) if r[23] is not None else None,
            data_cutoff=str(r[24]) if r[24] is not None else None,
            dataset_fingerprint=r[25],
            cohort=r[26],
            value_kind="forecast",
        )
        results.append(item)
        csv_rows.append(item.model_dump())

    if format == "csv":
        return export_csv_response(csv_rows, filename="forecasts.csv")

    return results


@router.get("/extrapolations", response_model=MultiModelExtrapolationResponse)
def get_multi_model_extrapolations(
    product: str = Query(..., description="Product code (e.g. RICE_WHITE_IMPORTED, RICE_WHITE_LOCAL, VEG_OIL, MAIZE_GRAIN)"),
    location: str | None = Query(None, description="Location P-code (e.g. MDG, MDG12)"),
    horizon: int = Query(6, ge=1, le=12, description="Extrapolation horizon in months (1-12)"),
    session: Session = Depends(get_db),
) -> MultiModelExtrapolationResponse:
    """Generate multi-model comparative price extrapolations (SPECS §17).

    Compares dynamic trajectories and extrapolations across all candidate models:
    - CausalAgriculturalModel (Macro, climate, events & phenological seasonality)
    - AutoARIMA (Autoregressive integrated moving average)
    - AutoETS (Exponential smoothing state-space)
    - SeasonalNaive (12-month lag seasonal baseline)
    - NaiveLast (Martingale flat persistence baseline)
    """
    from datetime import date
    import numpy as np
    from sqlalchemy import select
    from ketrika.core.models.db import Event, MacroObservation
    from ketrika.ml.models import (
        AutoARIMAModel,
        AutoETSModel,
        NaiveLastModel,
        SeasonalNaiveModel,
    )
    from ketrika.ml.causal_model import CausalAgriculturalModel
    from ketrika.ml.series import extract_eligible_series, shift_months

    # Resolve product
    resolved = resolve_product(product, min_confidence=0.85)
    target_prod = resolved[0] if resolved else product.upper()

    # Load series up to latest cutoff
    all_series = extract_eligible_series(session, data_cutoff=date(2026, 10, 1), min_points=24)
    matching = [
        s for s in all_series
        if s.product_code == target_prod or s.product_code == product.upper()
    ]
    if not matching:
        raise HTTPException(
            status_code=404,
            detail=f"No eligible time series found for product '{product}'.",
        )

    # Filter location if provided
    selected_series = None
    if location:
        loc_upper = location.upper()
        for s in matching:
            if s.location_pcode.upper() == loc_upper:
                selected_series = s
                break
    if not selected_series:
        mdg_matches = [s for s in matching if s.location_pcode == "MDG"]
        selected_series = mdg_matches[0] if mdg_matches else matching[0]

    pts = [p for p in selected_series.grid if p.price is not None]
    if len(pts) < 12:
        raise HTTPException(status_code=400, detail="Insufficient price observations for extrapolation")

    s_dates = [p.month for p in pts]
    y = np.array([p.price for p in pts], dtype=float)
    last_price = round(float(y[-1]), 1)
    last_date = s_dates[-1]

    horizons = list(range(1, horizon + 1))
    target_periods = [shift_months(last_date, h_i).isoformat() for h_i in horizons]

    # Pre-fetch macro and events for causal model
    macro_rows = session.execute(
        select(MacroObservation)
        .where(MacroObservation.superseded_by.is_(None), MacroObservation.period_start <= last_date)
        .order_by(MacroObservation.period_start)
    ).scalars().all()
    macro_by_ind: dict[str, dict[date, float]] = {}
    for m_rec in macro_rows:
        if m_rec.value is not None:
            macro_by_ind.setdefault(m_rec.indicator_code, {})[m_rec.period_start] = float(m_rec.value)
    aligned_macro = {}
    for ind_code, dmap in macro_by_ind.items():
        arr = []
        last_known = 0.0
        for d in s_dates:
            if d in dmap:
                last_known = dmap[d]
            arr.append(last_known)
        aligned_macro[ind_code] = np.array(arr, dtype=float)

    event_rows = session.execute(
        select(Event).where(Event.event_date <= last_date).order_by(Event.event_date)
    ).scalars().all()
    events_payload = [
        {
            "event_id": str(ev.event_id),
            "event_type": ev.event_type,
            "title": ev.title,
            "event_date": ev.event_date,
            "severity": ev.severity,
        }
        for ev in event_rows
    ]

    # Latest model run metrics
    latest_run = session.execute(
        text("SELECT metrics FROM ml.model_run WHERE task = 'price_forecast' ORDER BY trained_at DESC LIMIT 1")
    ).fetchone()
    historical_metrics: dict[str, Any] = {}
    winning_model: str | None = None
    if latest_run and isinstance(latest_run[0], dict):
        by_series = latest_run[0].get("by_series", {})
        if selected_series.series_key in by_series:
            s_info = by_series[selected_series.series_key]
            winning_model = s_info.get("best_model")
            historical_metrics = s_info.get("evaluations", {})

    candidate_models = {
        "CausalAgriculturalModel": (CausalAgriculturalModel(season_length=12), False),
        "AutoARIMA": (AutoARIMAModel(season_length=12), False),
        "AutoETS": (AutoETSModel(season_length=12), False),
        "SeasonalNaive": (SeasonalNaiveModel(season_length=12), True),
        "NaiveLast": (NaiveLastModel(), True),
    }

    models_dict: dict[str, ModelExtrapolationTrajectory] = {}
    for m_name, (m_inst, is_base) in candidate_models.items():
        try:
            if m_name == "CausalAgriculturalModel":
                m_res = m_inst.fit_predict(
                    y,
                    h=horizon,
                    dates=s_dates,
                    series_key=selected_series.series_key,
                    macro_series=aligned_macro,
                    events=events_payload,
                )
            else:
                m_res = m_inst.fit_predict(y, h=horizon)

            preds = [round(float(p), 1) for p in m_res.prediction.mean[:horizon]]
            p10_vals = (
                [round(float(p), 1) for p in m_res.prediction.p10[:horizon]]
                if m_res.prediction.p10 is not None
                else None
            )
            p90_vals = (
                [round(float(p), 1) for p in m_res.prediction.p90[:horizon]]
                if m_res.prediction.p90 is not None
                else None
            )

            m_hist = historical_metrics.get(m_name, {})
            models_dict[m_name] = ModelExtrapolationTrajectory(
                model_name=m_name,
                is_baseline=is_base,
                predictions=preds,
                p10=p10_vals,
                p90=p90_vals,
                historical_wape=round(m_hist.get("wape"), 4) if m_hist.get("wape") is not None else None,
                historical_mae=round(m_hist.get("mae"), 1) if m_hist.get("mae") is not None else None,
            )
        except Exception:
            pass

    # Build Consensus Ensemble (Extrapolation entre les modèles pondérée par l'inverse de l'erreur)
    if len(models_dict) >= 2:
        valid_models = [m for m in models_dict.values() if len(m.predictions) == horizon]
        if valid_models:
            weights = []
            for m in valid_models:
                wape_val = m.historical_wape or 0.05
                weights.append(1.0 / max(wape_val, 0.005))
            total_w = sum(weights)
            norm_weights = [w / total_w for w in weights]

            ensemble_preds = []
            ensemble_p10 = []
            ensemble_p90 = []
            for step_idx in range(horizon):
                step_vals = [m.predictions[step_idx] for m in valid_models]
                step_w_mean = sum(val * w for val, w in zip(step_vals, norm_weights))
                ensemble_preds.append(round(step_w_mean, 1))

                all_p10 = [m.p10[step_idx] for m in valid_models if m.p10 is not None]
                all_p90 = [m.p90[step_idx] for m in valid_models if m.p90 is not None]
                ensemble_p10.append(round(min(all_p10), 1) if all_p10 else round(step_w_mean * 0.95, 1))
                ensemble_p90.append(round(max(all_p90), 1) if all_p90 else round(step_w_mean * 1.05, 1))

            avg_wape = sum((m.historical_wape or 0.05) * w for m, w in zip(valid_models, norm_weights))
            avg_mae = sum((m.historical_mae or 50.0) * w for m, w in zip(valid_models, norm_weights))

            models_dict["ConsensusEnsemble"] = ModelExtrapolationTrajectory(
                model_name="ConsensusEnsemble",
                is_baseline=False,
                predictions=ensemble_preds,
                p10=ensemble_p10,
                p90=ensemble_p90,
                historical_wape=round(avg_wape, 4),
                historical_mae=round(avg_mae, 1),
            )

    return MultiModelExtrapolationResponse(
        product_code=selected_series.product_code,
        product_name=selected_series.product_code.replace("_", " ").title(),
        location_pcode=selected_series.location_pcode,
        location_name=selected_series.location_pcode,
        unit=selected_series.unit,
        currency="MGA",
        data_cutoff=last_date.isoformat(),
        last_observed_price=last_price,
        horizons=horizons,
        target_periods=target_periods,
        winning_model=winning_model,
        models=models_dict,
    )


@router.get("/runs", response_model=list[ModelRunSummaryItem])
def get_forecast_runs(
    limit: int = Query(50, ge=1, le=1000, description="Page limit (default 50, max 1000)"),
    offset: int = Query(0, ge=0, description="Page offset (default 0)"),
    format: str = Query("json", pattern="^(json|csv)$", description="Output format (json or csv)"),
    session: Session = Depends(get_db),
) -> Any:
    """Retrieve historical forecasting model runs and lineage fingerprints (SPECS §17, ADR-078)."""
    sql = """
        SELECT
            model_run_id,
            task,
            model_name,
            model_version,
            data_cutoff::text,
            trained_at,
            params,
            metrics
        FROM ml.model_run
        WHERE task = 'price_forecast'
        ORDER BY trained_at DESC
        LIMIT :limit OFFSET :offset;
    """
    rows = session.execute(text(sql), {"limit": limit, "offset": offset}).fetchall()

    results: list[ModelRunSummaryItem] = []
    csv_rows: list[dict[str, Any]] = []

    for r in rows:
        params_dict = r[6] if isinstance(r[6], dict) else {}
        metrics_dict = r[7] if isinstance(r[7], dict) else {}
        item = ModelRunSummaryItem(
            model_run_id=r[0],
            task=r[1],
            model_name=r[2],
            model_version=r[3],
            data_cutoff=str(r[4]),
            trained_at=r[5],
            dataset_fingerprint=params_dict.get("dataset_fingerprint"),
            cohort=params_dict.get("cohort"),
            params=params_dict,
            metrics=metrics_dict,
        )
        results.append(item)
        csv_rows.append(
            {
                "model_run_id": str(r[0]),
                "task": r[1],
                "model_name": r[2],
                "model_version": r[3],
                "data_cutoff": str(r[4]),
                "trained_at": r[5].isoformat() if r[5] else None,
                "dataset_fingerprint": params_dict.get("dataset_fingerprint"),
                "cohort": params_dict.get("cohort"),
                "wape": metrics_dict.get("wape"),
                "mae": metrics_dict.get("mae"),
                "coverage_80": metrics_dict.get("coverage_80"),
                "n_series": metrics_dict.get("n_series"),
            }
        )

    if format == "csv":
        return export_csv_response(csv_rows, filename="forecast_runs.csv")

    return results


@router.get("/runs/{model_run_id}", response_model=ModelRunDetailResponse)
def get_forecast_run_detail(
    model_run_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> ModelRunDetailResponse:
    """Retrieve detailed execution information and predictions for a specific run."""
    run_sql = """
        SELECT
            model_run_id,
            task,
            model_name,
            model_version,
            data_cutoff::text,
            trained_at,
            params,
            metrics
        FROM ml.model_run
        WHERE model_run_id = :run_id;
    """
    row = session.execute(text(run_sql), {"run_id": model_run_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Model run not found")

    params_dict = row[6] if isinstance(row[6], dict) else {}
    metrics_dict = row[7] if isinstance(row[7], dict) else {}

    run_summary = ModelRunSummaryItem(
        model_run_id=row[0],
        task=row[1],
        model_name=row[2],
        model_version=row[3],
        data_cutoff=str(row[4]),
        trained_at=row[5],
        dataset_fingerprint=params_dict.get("dataset_fingerprint"),
        cohort=params_dict.get("cohort"),
        params=params_dict,
        metrics=metrics_dict,
    )

    fc_sql = """
        SELECT
            f.forecast_id,
            f.model_run_id,
            f.series_key,
            p.product_code,
            p.canonical_name_fr AS product_name,
            loc.pcode AS location_pcode,
            loc.name AS location_name,
            f.actor_level,
            f.horizon,
            f.target_period::text,
            f.p10::float,
            f.p50::float,
            f.p90::float,
            f.model_requested,
            COALESCE(f.model_effective, mr.model_name) AS model_effective,
            f.is_baseline,
            f.is_calibrated,
            f.calibration_sample_size,
            f.status,
            f.fallback_reason,
            f.currency,
            f.unit,
            f.interval_width::float,
            f.coverage_rate_80::float,
            mr.data_cutoff::text,
            mr.params->>'dataset_fingerprint' AS dataset_fingerprint,
            mr.params->>'cohort' AS cohort
        FROM ml.forecast f
        JOIN ml.model_run mr ON f.model_run_id = mr.model_run_id
        LEFT JOIN ref.product p ON f.product_id = p.product_id
        LEFT JOIN ref.location loc ON f.location_id = loc.location_id
        WHERE f.model_run_id = :run_id
        ORDER BY p.product_code, loc.pcode, f.horizon ASC;
    """
    fc_rows = session.execute(text(fc_sql), {"run_id": model_run_id}).fetchall()

    forecasts: list[ForecastItem] = []
    for r in fc_rows:
        forecasts.append(
            ForecastItem(
                forecast_id=r[0],
                model_run_id=r[1],
                series_key=r[2],
                product_code=r[3],
                product_name=r[4],
                location_pcode=r[5] or "MDG",
                location_name=r[6],
                actor_level=r[7],
                horizon=int(r[8]),
                target_period=str(r[9]),
                p10=float(r[10]) if r[10] is not None else None,
                p50=float(r[11]),
                p90=float(r[12]) if r[12] is not None else None,
                model_requested=r[13],
                model_effective=r[14] or "NaiveLast",
                model_name=r[14] or "NaiveLast",
                is_baseline=bool(r[15]),
                is_calibrated=bool(r[16]),
                calibration_sample_size=int(r[17] or 0),
                status=r[18] or "nominal",
                fallback_reason=r[19],
                currency=r[20] or "MGA",
                unit=r[21] or "kg",
                interval_width=float(r[22]) if r[22] is not None else None,
                coverage_rate_80=float(r[23]) if r[23] is not None else None,
                data_cutoff=str(r[24]) if r[24] is not None else None,
                dataset_fingerprint=r[25],
                cohort=r[26],
                value_kind="forecast",
            )
        )

    return ModelRunDetailResponse(run=run_summary, forecasts=forecasts)


@router.get("/abstentions", response_model=list[ForecastAbstentionItem])
def get_forecast_abstentions(
    product: str | None = Query(None, description="Filter by product code"),
    location: str | None = Query(None, description="Filter by location P-code"),
    limit: int = Query(100, ge=1, le=1000, description="Page limit (default 100, max 1000)"),
    offset: int = Query(0, ge=0, description="Page offset (default 0)"),
    format: str = Query("json", pattern="^(json|csv)$", description="Output format (json or csv)"),
    session: Session = Depends(get_db),
) -> Any:
    """Retrieve series exclusions and abstentions documented during the latest forecasting run."""
    # Fetch metrics from latest run
    sql = """
        SELECT metrics
        FROM ml.model_run
        WHERE task = 'price_forecast'
        ORDER BY trained_at DESC
        LIMIT 1;
    """
    row = session.execute(text(sql)).fetchone()
    abstentions_raw: list[dict[str, Any]] = []
    if row and isinstance(row[0], dict):
        abstentions_raw = row[0].get("abstentions", [])

    prod_set: set[str] | None = None
    if product:
        resolved = resolve_product(product, min_confidence=0.9)
        canonical = resolved[0] if resolved else None
        prod_set = {product, canonical} if canonical else {product}

    filtered: list[ForecastAbstentionItem] = []
    for item in abstentions_raw:
        if prod_set and item.get("product_code") not in prod_set:
            continue
        if location and item.get("location_pcode") != location:
            continue
        filtered.append(
            ForecastAbstentionItem(
                series_key=item.get("series_key", ""),
                product_code=item.get("product_code", ""),
                location_pcode=item.get("location_pcode", ""),
                actor_level=item.get("actor_level", ""),
                reason=item.get("reason", "unknown_abstention"),
                points_count=int(item.get("points_count", 0)),
            )
        )

    paginated = filtered[offset : offset + limit]

    if format == "csv":
        csv_rows = [it.model_dump() for it in paginated]
        return export_csv_response(csv_rows, filename="forecast_abstentions.csv")

    return paginated


@router.get("/performance", response_model=ForecastPerformanceResponse)
def get_forecast_performance(
    product: str | None = Query(None, description="Filter by product code"),
    location: str | None = Query(None, description="Filter by location P-code"),
    horizon: int | None = Query(None, ge=1, le=12, description="Filter by forecast horizon"),
    evaluation_kind: str | None = Query(
        None,
        description="Filter by evaluation kind: as_of_holdout | matured_actual | prospective_pending",
    ),
    limit: int = Query(500, ge=1, le=2000, description="Page limit (default 500, max 2000)"),
    offset: int = Query(0, ge=0, description="Page offset (default 0)"),
    format: str = Query("json", pattern="^(json|csv)$", description="Output format (json or csv)"),
    session: Session = Depends(get_db),
) -> Any:
    """Retrieve multidimensional forecast performance evaluation metrics and records (SPECS §17.4, ADR-079, R3.8)."""
    # Check if any evaluations exist, otherwise evaluate
    count_sql = "SELECT COUNT(*) FROM ml.forecast_evaluation;"
    count_evals = 0
    try:
        count_res = session.execute(text(count_sql)).fetchone()
        count_evals = int(count_res[0]) if count_res else 0
    except Exception:
        # Table might not exist or empty
        count_evals = 0

    if count_evals == 0:
        # Check if forecasts exist to evaluate
        fc_count_sql = "SELECT COUNT(*) FROM ml.forecast;"
        fc_count = 0
        try:
            fc_res = session.execute(text(fc_count_sql)).fetchone()
            fc_count = int(fc_res[0]) if fc_res else 0
        except Exception:
            fc_count = 0

        if fc_count > 0:
            evaluator = MaturedForecastEvaluator(session)
            evaluator.evaluate_forecasts(persist=True)

    # Fetch evaluations from table
    sql = """
        SELECT
            fe.evaluation_id,
            fe.forecast_id,
            fe.model_run_id,
            fe.series_key,
            fe.product_code,
            fe.location_pcode,
            fe.actor_level,
            fe.target_period,
            fe.horizon,
            fe.evaluation_kind,
            fe.model_name,
            fe.is_baseline,
            fe.predicted_p50::float,
            fe.predicted_p10::float,
            fe.predicted_p90::float,
            fe.actual_price::float,
            fe.actual_observation_id,
            fe.absolute_error::float,
            fe.percentage_error::float,
            fe.is_covered_80,
            fe.evaluated_at
        FROM ml.forecast_evaluation fe
        WHERE 1=1
    """
    params: dict[str, Any] = {}
    if product:
        sql += " AND fe.product_code = :product"
        params["product"] = product
    if location:
        sql += " AND fe.location_pcode = :location"
        params["location"] = location
    if horizon:
        sql += " AND fe.horizon = :horizon"
        params["horizon"] = horizon
    if evaluation_kind:
        sql += " AND fe.evaluation_kind = :eval_kind"
        params["eval_kind"] = evaluation_kind

    sql += " ORDER BY fe.target_period ASC, fe.horizon ASC;"

    rows = session.execute(text(sql), params).fetchall()

    records: list[EvaluationRecord] = []
    items: list[ForecastEvaluationItem] = []

    for r in rows:
        rec = EvaluationRecord(
            evaluation_id=r.evaluation_id,
            forecast_id=r.forecast_id,
            model_run_id=r.model_run_id,
            series_key=r.series_key,
            product_code=r.product_code,
            location_pcode=r.location_pcode,
            actor_level=r.actor_level,
            target_period=r.target_period,
            horizon=int(r.horizon),
            evaluation_kind=r.evaluation_kind,
            model_name=r.model_name,
            is_baseline=bool(r.is_baseline),
            predicted_p50=r.predicted_p50,
            predicted_p10=r.predicted_p10,
            predicted_p90=r.predicted_p90,
            actual_price=r.actual_price,
            actual_observation_id=r.actual_observation_id,
            absolute_error=r.absolute_error,
            percentage_error=r.percentage_error,
            is_covered_80=r.is_covered_80,
            evaluated_at=r.evaluated_at,
        )
        records.append(rec)
        items.append(
            ForecastEvaluationItem(
                evaluation_id=r.evaluation_id,
                forecast_id=r.forecast_id,
                model_run_id=r.model_run_id,
                series_key=r.series_key,
                product_code=r.product_code,
                location_pcode=r.location_pcode,
                actor_level=r.actor_level,
                target_period=r.target_period.isoformat(),
                horizon=int(r.horizon),
                evaluation_kind=r.evaluation_kind,
                model_name=r.model_name,
                is_baseline=bool(r.is_baseline),
                predicted_p50=r.predicted_p50,
                predicted_p10=r.predicted_p10,
                predicted_p90=r.predicted_p90,
                actual_price=r.actual_price,
                actual_observation_id=r.actual_observation_id,
                absolute_error=r.absolute_error,
                percentage_error=r.percentage_error,
                is_covered_80=r.is_covered_80,
                evaluated_at=r.evaluated_at.isoformat() if r.evaluated_at else None,
            )
        )

    perf_table = compute_performance_decomposition(records)

    paginated_items = items[offset : offset + limit]

    if format == "csv":
        csv_rows = [it.model_dump() for it in paginated_items]
        return export_csv_response(csv_rows, filename="forecast_performance_evaluations.csv")

    def _to_summary_schema(m: Any) -> PerformanceMetricsSummary:
        return PerformanceMetricsSummary(
            wape=m.wape,
            mae=m.mae,
            smape=m.smape,
            coverage_80=m.coverage_80,
            coverage_ci_95=list(m.coverage_ci_95) if m.coverage_ci_95 else None,
            mean_interval_width=m.mean_interval_width,
            sample_size=m.sample_size,
        )

    return ForecastPerformanceResponse(
        summary=_to_summary_schema(perf_table.summary),
        by_product={k: _to_summary_schema(v) for k, v in perf_table.by_product.items()},
        by_location={k: _to_summary_schema(v) for k, v in perf_table.by_location.items()},
        by_horizon={str(k): _to_summary_schema(v) for k, v in perf_table.by_horizon.items()},
        by_seasonality={k: _to_summary_schema(v) for k, v in perf_table.by_seasonality.items()},
        evaluations=paginated_items,
        total_evaluations=len(items),
    )
