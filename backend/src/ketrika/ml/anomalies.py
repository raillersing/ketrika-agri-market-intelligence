"""Price anomaly detection engine using robust z-scores and price variations (SPECS §16, §17, §18)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.core.logging import get_logger
from ketrika.core.models.db import ModelRun

logger = get_logger(__name__)


@dataclass
class PriceAnomaly:
    """Detected price anomaly based on robust statistical z-score and monthly variation."""

    anomaly_type: Literal["PRICE_SPIKE", "PRICE_DROP", "OUTLIER"]
    product_id: uuid.UUID
    product_code: str
    product_name: str
    location_id: uuid.UUID | None
    location_pcode: str | None
    location_name: str | None
    month: date
    median_price: float
    chg_1m: float | None
    z_score_robust: float
    severity: Literal["low", "medium", "high"]
    chosen_source_id: str | None
    sources: list[str] = field(default_factory=list)
    n_sources: int = 1
    n_independent_families: int = 1
    evidence: dict[str, Any] = field(default_factory=dict)


def detect_price_anomalies(
    session: Session,
    z_threshold: float = 3.0,
    chg_threshold: float = 0.15,
    data_cutoff: date | None = None,
) -> list[PriceAnomaly]:
    """Detect statistical price anomalies from Gold analytical layer.

    Anomalies evaluated per SPECS §17 & §18, ADR-100 (R6.6):
    - PRICE_SPIKE: z > 3.0 and chg_1m > 0.15 (severity 'high' ONLY if >= 2 truly independent source families, else 'medium')
    - PRICE_DROP: z < -3.0 and chg_1m < -0.15 (severity 'medium')
    - OUTLIER: |z| > 3.0 but relative variation does not meet spike/drop thresholds (severity 'low')
    """
    cutoff_clause = "AND pc.month <= :data_cutoff" if data_cutoff is not None else ""
    params: dict[str, Any] = {"z_thresh": z_threshold}
    if data_cutoff is not None:
        params["data_cutoff"] = data_cutoff

    query = text(
        f"""
        WITH anomaly_points AS (
            SELECT
                pc.product_id,
                pc.product_code,
                pc.product_name,
                pc.location_id,
                pc.location_pcode,
                pc.location_name,
                pc.month,
                pc.median_price,
                pc.chg_1m,
                pc.z_score_robust,
                pc.chosen_source_id
            FROM gold.price_changes pc
            WHERE abs(pc.z_score_robust) > :z_thresh
              {cutoff_clause}
        ),
        source_counts AS (
            SELECT
                pm.product_id,
                pm.location_id,
                pm.month,
                count(DISTINCT pm.source_id) AS n_sources,
                array_agg(DISTINCT pm.source_id) AS sources
            FROM gold.price_monthly pm
            GROUP BY pm.product_id, pm.location_id, pm.month
        )
        SELECT
            ap.product_id,
            ap.product_code,
            ap.product_name,
            ap.location_id,
            ap.location_pcode,
            ap.location_name,
            ap.month,
            ap.median_price,
            ap.chg_1m,
            ap.z_score_robust,
            ap.chosen_source_id,
            COALESCE(src.n_sources, 1) AS n_sources,
            COALESCE(src.sources, ARRAY[ap.chosen_source_id]::text[]) AS sources
        FROM anomaly_points ap
        LEFT JOIN source_counts src
          ON ap.product_id = src.product_id
         AND ap.location_id = src.location_id
         AND ap.month = src.month
        ORDER BY ap.month DESC, abs(ap.z_score_robust) DESC;
        """
    )

    rows = session.execute(query, params).fetchall()
    anomalies: list[PriceAnomaly] = []

    # Import source independence auditor (ADR-100 / R6.6)
    from ketrika.gold.kpi import audit_source_family_independence

    for r in rows:
        z = round(float(r.z_score_robust), 2)
        chg = float(r.chg_1m) if r.chg_1m is not None else None
        n_src = int(getattr(r, "n_sources", 1) or 1)
        raw_srcs = getattr(r, "sources", None)
        chosen_src = getattr(r, "chosen_source_id", None)
        srcs = (
            [str(s) for s in raw_srcs if s]
            if raw_srcs
            else ([str(chosen_src)] if chosen_src else [])
        )

        independence_audit = audit_source_family_independence(srcs)
        n_indep = int(independence_audit.get("n_independent_families", 1))

        if z > z_threshold and chg is not None and chg > chg_threshold:
            anomaly_type: Literal["PRICE_SPIKE", "PRICE_DROP", "OUTLIER"] = "PRICE_SPIKE"
            # High severity requires >= 2 TRULY INDEPENDENT source families (ADR-100)
            severity: Literal["low", "medium", "high"] = "high" if n_indep >= 2 else "medium"
        elif z < -z_threshold and chg is not None and chg < -chg_threshold:
            anomaly_type = "PRICE_DROP"
            severity = "medium"
        else:
            anomaly_type = "OUTLIER"
            severity = "low"

        evidence = {
            "rule": anomaly_type,
            "anomaly_type": anomaly_type,
            "product_code": r.product_code,
            "product_name": r.product_name,
            "location_pcode": r.location_pcode,
            "location_name": r.location_name,
            "month": str(r.month),
            "median_price": float(r.median_price),
            "chg_1m": chg,
            "z_score": z,
            "z_score_robust": z,
            "n_sources": n_src,
            "sources": srcs,
            "n_independent_families": n_indep,
            "independent_families": independence_audit.get("independent_families", []),
            "has_dependent_derivation": independence_audit.get("has_dependent_derivation", False),
            "chosen_source_id": r.chosen_source_id,
        }

        anomalies.append(
            PriceAnomaly(
                anomaly_type=anomaly_type,
                product_id=r.product_id,
                product_code=r.product_code,
                product_name=r.product_name,
                location_id=r.location_id,
                location_pcode=r.location_pcode,
                location_name=r.location_name,
                month=r.month,
                median_price=float(r.median_price),
                chg_1m=chg,
                z_score_robust=z,
                severity=severity,
                chosen_source_id=r.chosen_source_id,
                sources=srcs,
                n_sources=n_src,
                n_independent_families=n_indep,
                evidence=evidence,
            )
        )

    logger.info("Detected %d price anomalies (|z| > %s)", len(anomalies), z_threshold)
    return anomalies


def record_anomaly_model_run(
    session: Session,
    anomalies: list[PriceAnomaly],
    z_threshold: float = 3.0,
    chg_threshold: float = 0.15,
    data_cutoff: date | None = None,
) -> ModelRun:
    """Record an anomaly detection model run in ml.model_run table."""
    now = datetime.now(UTC)
    cutoff = data_cutoff or date.today()

    spikes_count = sum(1 for a in anomalies if a.anomaly_type == "PRICE_SPIKE")
    drops_count = sum(1 for a in anomalies if a.anomaly_type == "PRICE_DROP")
    outliers_count = sum(1 for a in anomalies if a.anomaly_type == "OUTLIER")

    metrics = {
        "total_anomalies": len(anomalies),
        "spikes_count": spikes_count,
        "drops_count": drops_count,
        "outliers_count": outliers_count,
    }

    params = {
        "z_threshold": z_threshold,
        "chg_threshold": chg_threshold,
        "method": "robust_zscore_mad_12",
    }

    model_run = ModelRun(
        model_run_id=uuid.uuid4(),
        task="anomaly",
        model_name="robust_zscore",
        model_version="zscore@v1",
        data_cutoff=cutoff,
        trained_at=now,
        params=params,
        metrics=metrics,
    )

    session.add(model_run)
    session.flush()
    logger.info("Persisted anomaly ModelRun %s: %s", model_run.model_run_id, metrics)
    return model_run
