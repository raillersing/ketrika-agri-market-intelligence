"""Matured forecast evaluation, multidimensional decomposition, and baseline benchmarking (SPECS §17.4, ADR-079, R3.8).

Enforces:
1. Strict temporal non-leakage: matured forecast actuals are confronted upon horizon maturity
   (target_period <= evaluation_date) without ever retroactively feeding future targets into
   the historical training set of the model run.
2. Tripartite chronological categorization:
   - 'as_of_holdout': out-of-sample certified holdout test evaluation.
   - 'matured_actual': prospective production forecast confronted with realized market price.
   - 'prospective_pending': forecast awaiting maturity (target_period > evaluation_date).
3. Mandatory multidimensional decomposition:
   - By product (product_code)
   - By geographic region (location_pcode)
   - By forecast horizon (h=1, 2, 3)
   - By seasonal regime (lean/soudure: Nov-Mar vs harvest/recolte: Apr-Oct)
   Strict prohibition of an isolated synthetic global average score.
4. Honest benchmarking against baselines:
   - Direct comparison of candidates (AutoETS, AutoARIMA) against baselines (NaiveLast, SeasonalNaive).
   - Parsimony rule: if candidate delta_WAPE <= 0.01 compared to baseline, baseline is declared winner.
5. Verifiable provenance (Rule 1 AGENTS.md):
   - Every evaluation row links forecast_id, model_run_id, and actual_observation_id.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.core.logging import get_logger
from ketrika.core.models.db import ForecastEvaluation

logger = get_logger(__name__)


def get_seasonality_regime(target_period: date) -> str:
    """Return seasonal regime for Madagascar agricultural markets.

    - 'soudure' (lean season / peak prices): November through March (months 11, 12, 1, 2, 3).
    - 'recolte' (harvest & post-harvest season): April through October (months 4 to 10).
    """
    if target_period.month in (11, 12, 1, 2, 3):
        return "soudure"
    return "recolte"


def wilson_score_interval_95(k: int, n: int) -> tuple[float, float]:
    """Calculate 95% Wilson score confidence interval for binomial proportion."""
    if n <= 0:
        return (0.0, 1.0)
    z = 1.959963984540054
    p_hat = k / n
    denom = 1.0 + (z**2) / n
    center = (p_hat + (z**2) / (2.0 * n)) / denom
    half_width = (z * math.sqrt((p_hat * (1.0 - p_hat) / n) + (z**2) / (4.0 * (n**2)))) / denom
    return (max(0.0, round(center - half_width, 4)), min(1.0, round(center + half_width, 4)))


@dataclass(frozen=True)
class EvaluationRecord:
    """Single point forecast evaluation record."""

    forecast_id: uuid.UUID
    model_run_id: uuid.UUID
    series_key: str
    product_code: str
    location_pcode: str | None
    actor_level: str
    target_period: date
    horizon: int
    evaluation_kind: str  # as_of_holdout | matured_actual | prospective_pending
    model_name: str
    is_baseline: bool
    predicted_p50: float | None
    predicted_p10: float | None
    predicted_p90: float | None
    actual_price: float | None
    actual_observation_id: uuid.UUID | None
    absolute_error: float | None
    percentage_error: float | None
    is_covered_80: bool | None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    evaluation_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": str(self.evaluation_id),
            "forecast_id": str(self.forecast_id),
            "model_run_id": str(self.model_run_id),
            "series_key": self.series_key,
            "product_code": self.product_code,
            "location_pcode": self.location_pcode,
            "actor_level": self.actor_level,
            "target_period": self.target_period.isoformat(),
            "horizon": self.horizon,
            "evaluation_kind": self.evaluation_kind,
            "model_name": self.model_name,
            "is_baseline": self.is_baseline,
            "predicted_p50": round(self.predicted_p50, 2)
            if self.predicted_p50 is not None
            else None,
            "predicted_p10": round(self.predicted_p10, 2)
            if self.predicted_p10 is not None
            else None,
            "predicted_p90": round(self.predicted_p90, 2)
            if self.predicted_p90 is not None
            else None,
            "actual_price": round(self.actual_price, 2) if self.actual_price is not None else None,
            "actual_observation_id": str(self.actual_observation_id)
            if self.actual_observation_id
            else None,
            "absolute_error": round(self.absolute_error, 2)
            if self.absolute_error is not None
            else None,
            "percentage_error": round(self.percentage_error, 4)
            if self.percentage_error is not None
            else None,
            "is_covered_80": self.is_covered_80,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


@dataclass(frozen=True)
class EvaluationMetrics:
    """Summary metrics calculated over a subset of evaluated forecasts."""

    wape: float | None
    mae: float | None
    smape: float | None
    coverage_80: float | None
    coverage_ci_95: tuple[float, float] | None
    mean_interval_width: float | None
    sample_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "wape": round(self.wape, 4) if self.wape is not None else None,
            "mae": round(self.mae, 2) if self.mae is not None else None,
            "smape": round(self.smape, 4) if self.smape is not None else None,
            "coverage_80": round(self.coverage_80, 4) if self.coverage_80 is not None else None,
            "coverage_ci_95": list(self.coverage_ci_95) if self.coverage_ci_95 else None,
            "mean_interval_width": round(self.mean_interval_width, 2)
            if self.mean_interval_width is not None
            else None,
            "sample_size": self.sample_size,
        }


@dataclass
class PerformanceTable:
    """Full multidimensional performance evaluation table (ADR-079)."""

    summary: EvaluationMetrics
    by_product: dict[str, EvaluationMetrics]
    by_location: dict[str, EvaluationMetrics]
    by_horizon: dict[int, EvaluationMetrics]
    by_seasonality: dict[str, EvaluationMetrics]
    records: list[EvaluationRecord]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "by_product": {k: v.to_dict() for k, v in self.by_product.items()},
            "by_location": {k: v.to_dict() for k, v in self.by_location.items()},
            "by_horizon": {str(k): v.to_dict() for k, v in self.by_horizon.items()},
            "by_seasonality": {k: v.to_dict() for k, v in self.by_seasonality.items()},
            "records": [r.to_dict() for r in self.records],
            "total_evaluations": len(self.records),
        }


def compute_metrics_for_records(records: list[EvaluationRecord]) -> EvaluationMetrics:
    """Compute WAPE, MAE, sMAPE, coverage_80, and Wilson CI over evaluated records."""
    valid_recs = [
        r
        for r in records
        if r.actual_price is not None
        and r.predicted_p50 is not None
        and not math.isnan(r.actual_price)
        and not math.isnan(r.predicted_p50)
    ]

    n = len(valid_recs)
    if n == 0:
        return EvaluationMetrics(
            wape=None,
            mae=None,
            smape=None,
            coverage_80=None,
            coverage_ci_95=None,
            mean_interval_width=None,
            sample_size=0,
        )

    actuals = np.array([r.actual_price for r in valid_recs], dtype=float)
    preds = np.array([r.predicted_p50 for r in valid_recs], dtype=float)

    abs_errors = np.abs(actuals - preds)
    sum_actuals = float(np.sum(actuals))

    wape = float(np.sum(abs_errors) / sum_actuals) if sum_actuals > 1e-6 else 0.0
    mae = float(np.mean(abs_errors))

    denom = np.abs(actuals) + np.abs(preds) + 1e-6
    smape = float(np.mean(2.0 * abs_errors / denom))

    # Coverage
    covered_items = [r for r in valid_recs if r.is_covered_80 is True]
    k_cov = len(covered_items)
    cov_80 = k_cov / n
    ci_95 = wilson_score_interval_95(k_cov, n)

    # Interval width
    widths: list[float] = []
    for r in valid_recs:
        if r.predicted_p10 is not None and r.predicted_p90 is not None:
            widths.append(float(r.predicted_p90 - r.predicted_p10))
    mean_w = float(np.mean(widths)) if widths else None

    return EvaluationMetrics(
        wape=wape,
        mae=mae,
        smape=smape,
        coverage_80=cov_80,
        coverage_ci_95=ci_95,
        mean_interval_width=mean_w,
        sample_size=n,
    )


def compute_performance_decomposition(records: list[EvaluationRecord]) -> PerformanceTable:
    """Build complete multidimensional performance table from evaluation records."""
    summary = compute_metrics_for_records(records)

    # By product
    by_product: dict[str, EvaluationMetrics] = {}
    products = sorted({r.product_code for r in records if r.product_code})
    for p in products:
        p_recs = [r for r in records if r.product_code == p]
        by_product[p] = compute_metrics_for_records(p_recs)

    # By location
    by_location: dict[str, EvaluationMetrics] = {}
    locations = sorted({r.location_pcode for r in records if r.location_pcode})
    for loc in locations:
        loc_recs = [r for r in records if r.location_pcode == loc]
        by_location[loc] = compute_metrics_for_records(loc_recs)

    # By horizon
    by_horizon: dict[int, EvaluationMetrics] = {}
    horizons = sorted({r.horizon for r in records})
    for h in horizons:
        h_recs = [r for r in records if r.horizon == h]
        by_horizon[h] = compute_metrics_for_records(h_recs)

    # By seasonality
    by_seasonality: dict[str, EvaluationMetrics] = {}
    for regime in ("soudure", "recolte"):
        regime_recs = [r for r in records if get_seasonality_regime(r.target_period) == regime]
        by_seasonality[regime] = compute_metrics_for_records(regime_recs)

    return PerformanceTable(
        summary=summary,
        by_product=by_product,
        by_location=by_location,
        by_horizon=by_horizon,
        by_seasonality=by_seasonality,
        records=records,
    )


class MaturedForecastEvaluator:
    """Evaluates forecasts against observed market realizations with full provenance and anti-leakage."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def evaluate_forecasts(
        self,
        evaluation_date: date | None = None,
        persist: bool = True,
    ) -> PerformanceTable:
        """Confront forecasts with ground truth observations as of evaluation_date.

        1. Fetches all forecasts with model lineage.
        2. Categorizes each into as_of_holdout, matured_actual, or prospective_pending.
        3. Retrieves verified ground-truth price observation from gold/obs schema.
        4. Calculates absolute error, percentage error, and 80% conformal coverage.
        5. Persists evaluation records into ml.forecast_evaluation if persist=True.
        6. Decomposes performance multidimensionally (product, location, horizon, seasonality).
        """
        eval_dt = evaluation_date or date.today()
        logger.info(
            "starting_forecast_evaluation", evaluation_date=eval_dt.isoformat(), persist=persist
        )

        # Query all forecasts joined with their model run and referenced product/location
        sql = """
            SELECT
                f.forecast_id,
                f.model_run_id,
                f.series_key,
                p.product_id,
                p.product_code,
                loc.location_id,
                loc.pcode AS location_pcode,
                f.actor_level,
                f.target_period,
                f.horizon,
                f.p10::float,
                f.p50::float,
                f.p90::float,
                COALESCE(f.model_effective, mr.model_name) AS model_name,
                f.is_baseline,
                mr.data_cutoff,
                mr.params->>'evaluation_kind' AS run_eval_kind
            FROM ml.forecast f
            JOIN ml.model_run mr ON f.model_run_id = mr.model_run_id
            JOIN ref.product p ON f.product_id = p.product_id
            LEFT JOIN ref.location loc ON f.location_id = loc.location_id
            ORDER BY f.target_period ASC, f.horizon ASC;
        """
        rows = self.session.execute(text(sql)).fetchall()

        records: list[EvaluationRecord] = []
        now_utc = datetime.now(UTC)

        for row in rows:
            fc_id = row.forecast_id
            run_id = row.model_run_id
            series_key = row.series_key
            prod_id = row.product_id
            prod_code = row.product_code
            loc_id = row.location_id
            loc_pcode = row.location_pcode
            actor_lvl = row.actor_level
            tgt_period = row.target_period
            horizon = int(row.horizon)
            p10 = float(row.p10) if row.p10 is not None else None
            p50 = float(row.p50) if row.p50 is not None else None
            p90 = float(row.p90) if row.p90 is not None else None
            model_name = str(row.model_name)
            is_baseline = bool(row.is_baseline)
            data_cutoff = row.data_cutoff
            run_eval_kind = row.run_eval_kind

            # 1. Determine evaluation kind
            if tgt_period > eval_dt:
                eval_kind = "prospective_pending"
                actual_price = None
                actual_obs_id = None
                abs_err = None
                pct_err = None
                is_cov = None
            else:
                if run_eval_kind == "as_of_holdout" or tgt_period <= data_cutoff:
                    eval_kind = "as_of_holdout"
                else:
                    eval_kind = "matured_actual"

                # 2. Look up realized actual price from gold.price_monthly_best or obs.price_observation
                # Prefer gold.price_monthly_best for normalized median, fallback to obs.price_observation
                obs_sql = """
                    SELECT
                        price_median_mga::float AS price,
                        NULL::uuid AS observation_id
                    FROM gold.price_monthly_best
                    WHERE product_id = :prod_id
                      AND actor_level = :actor_lvl
                      AND month = :month
                      AND (
                          (location_id IS NULL AND :loc_id IS NULL)
                          OR location_id = :loc_id
                      )
                    LIMIT 1;
                """
                obs_row = self.session.execute(
                    text(obs_sql),
                    {
                        "prod_id": prod_id,
                        "actor_lvl": actor_lvl,
                        "month": tgt_period,
                        "loc_id": loc_id,
                    },
                ).fetchone()

                if obs_row and obs_row.price is not None:
                    actual_price = float(obs_row.price)
                    # Get actual observation_id from obs.price_observation for full provenance
                    prov_sql = """
                        SELECT observation_id
                        FROM obs.price_observation
                        WHERE product_id = :prod_id
                          AND actor_level = :actor_lvl
                          AND period_start = :month
                          AND superseded_by IS NULL
                          AND (
                              (location_id IS NULL AND :loc_id IS NULL)
                              OR location_id = :loc_id
                          )
                        LIMIT 1;
                    """
                    prov_row = self.session.execute(
                        text(prov_sql),
                        {
                            "prod_id": prod_id,
                            "actor_lvl": actor_lvl,
                            "month": tgt_period,
                            "loc_id": loc_id,
                        },
                    ).fetchone()
                    actual_obs_id = prov_row[0] if prov_row else None
                else:
                    # No observation exists for this period yet
                    actual_price = None
                    actual_obs_id = None

                # Compute errors if actual_price is found
                if actual_price is not None and p50 is not None:
                    abs_err = abs(actual_price - p50)
                    pct_err = abs_err / actual_price if actual_price > 1e-6 else 0.0
                    if p10 is not None and p90 is not None:
                        is_cov = (p10 - 1e-4) <= actual_price <= (p90 + 1e-4)
                    else:
                        is_cov = None
                else:
                    abs_err = None
                    pct_err = None
                    is_cov = None

            record = EvaluationRecord(
                forecast_id=fc_id,
                model_run_id=run_id,
                series_key=series_key,
                product_code=prod_code,
                location_pcode=loc_pcode,
                actor_level=actor_lvl,
                target_period=tgt_period,
                horizon=horizon,
                evaluation_kind=eval_kind,
                model_name=model_name,
                is_baseline=is_baseline,
                predicted_p50=p50,
                predicted_p10=p10,
                predicted_p90=p90,
                actual_price=actual_price,
                actual_observation_id=actual_obs_id,
                absolute_error=abs_err,
                percentage_error=pct_err,
                is_covered_80=is_cov,
                evaluated_at=now_utc,
            )
            records.append(record)

        if persist and records:
            # Upsert / insert into ml.forecast_evaluation
            # Clean past evaluations for this evaluation date or insert fresh
            for r in records:
                db_eval = ForecastEvaluation(
                    evaluation_id=r.evaluation_id,
                    forecast_id=r.forecast_id,
                    model_run_id=r.model_run_id,
                    series_key=r.series_key,
                    product_code=r.product_code,
                    location_pcode=r.location_pcode,
                    actor_level=r.actor_level,
                    target_period=r.target_period,
                    horizon=r.horizon,
                    evaluation_kind=r.evaluation_kind,
                    model_name=r.model_name,
                    is_baseline=r.is_baseline,
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
                self.session.add(db_eval)
            self.session.commit()
            logger.info("persisted_forecast_evaluations", count=len(records))

        return compute_performance_decomposition(records)


def benchmark_against_baselines(records: list[EvaluationRecord]) -> dict[str, Any]:
    """Compare candidate statistical models against baselines under the parsimony principle (SPECS §17.4, ADR-079).

    Parsimony Rule:
    - If a candidate model (e.g. AutoETS, AutoARIMA) does not improve upon baseline WAPE by at least
      0.01 (1 percentage point: delta_WAPE = baseline_wape - candidate_wape > 0.01),
      the baseline is declared the winner by parsimony.
    - No phantom or statistically insignificant gain can be credited to complex models.
    """
    by_model: dict[str, list[EvaluationRecord]] = {}
    for r in records:
        by_model.setdefault(r.model_name, []).append(r)

    model_metrics: dict[str, EvaluationMetrics] = {}
    for m_name, recs in by_model.items():
        model_metrics[m_name] = compute_metrics_for_records(recs)

    # Identify best baseline
    baseline_names = [
        m
        for m, recs in by_model.items()
        if any(r.is_baseline for r in recs) or m in ("NaiveLast", "SeasonalNaive")
    ]
    best_baseline_name: str | None = None
    best_baseline_wape: float = float("inf")

    for b_name in baseline_names:
        bm = model_metrics.get(b_name)
        if bm and bm.wape is not None and bm.wape < best_baseline_wape:
            best_baseline_wape = bm.wape
            best_baseline_name = b_name

    comparisons: list[dict[str, Any]] = []
    for m_name, m_metrics in model_metrics.items():
        if m_name in baseline_names:
            continue

        if (
            m_metrics.wape is None
            or best_baseline_name is None
            or best_baseline_wape == float("inf")
        ):
            comparisons.append(
                {
                    "candidate_model": m_name,
                    "baseline_model": best_baseline_name,
                    "candidate_wape": m_metrics.wape,
                    "baseline_wape": best_baseline_wape
                    if best_baseline_wape != float("inf")
                    else None,
                    "delta_wape": None,
                    "verdict": "insufficient_data",
                    "reason": "Missing valid actual evaluations for comparison.",
                }
            )
            continue

        delta_wape = best_baseline_wape - m_metrics.wape  # positive means candidate is better
        is_significant_gain = delta_wape > 0.01

        if is_significant_gain:
            verdict = "candidate_winner"
            reason = f"Candidate achieves significant improvement of {delta_wape * 100:.2f} percentage points WAPE over baseline {best_baseline_name}."
        else:
            verdict = "baseline_winner"
            if delta_wape <= 0.0:
                reason = f"Baseline {best_baseline_name} performs better or equal to candidate (delta WAPE: {delta_wape * 100:.2f}%)."
            else:
                reason = f"Candidate gain ({delta_wape * 100:.2f}%) is below parsimony threshold (1.00%). Baseline {best_baseline_name} retained."

        comparisons.append(
            {
                "candidate_model": m_name,
                "baseline_model": best_baseline_name,
                "candidate_wape": round(m_metrics.wape, 4),
                "baseline_wape": round(best_baseline_wape, 4),
                "delta_wape": round(delta_wape, 4),
                "verdict": verdict,
                "reason": reason,
            }
        )

    return {
        "models": {k: v.to_dict() for k, v in model_metrics.items()},
        "best_baseline": best_baseline_name,
        "comparisons": comparisons,
    }
