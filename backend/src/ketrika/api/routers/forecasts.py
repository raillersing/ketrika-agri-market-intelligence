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
from ketrika.api.schemas import (
    ForecastAbstentionItem,
    ForecastEvaluationItem,
    ForecastItem,
    ForecastPerformanceResponse,
    ModelRunDetailResponse,
    ModelRunSummaryItem,
    PerformanceMetricsSummary,
)
from ketrika.core.db import get_db
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

    filtered: list[ForecastAbstentionItem] = []
    for item in abstentions_raw:
        if product and item.get("product_code") != product:
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
