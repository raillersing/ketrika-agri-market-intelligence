"""Rule definitions and candidate generators for Market Intelligence Alerts (SPECS §18)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.core.logging import get_logger
from ketrika.core.registry import find_repo_root

logger = get_logger(__name__)


@dataclass
class AlertCandidate:
    """Evaluated alert candidate before deduplication and persistence."""

    rule_code: str
    dedupe_key: str
    severity: str  # "low", "medium", "high"
    title: str
    evidence: dict[str, Any] = field(default_factory=dict)
    product_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None


def load_crop_calendar_sensitive_months() -> dict[str, set[int]]:
    """Load sensitive calendar months (planting + harvest) per region name/code from crop_calendar.yaml."""
    calendar_path = find_repo_root() / "taxonomy" / "crop_calendar.yaml"
    if not calendar_path.exists():
        calendar_path = Path("/workspace/taxonomy/crop_calendar.yaml")
    if not calendar_path.exists():
        return {}

    with calendar_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []

    # Map region keywords to sensitive months
    region_sensitive_months: dict[str, set[int]] = {}
    for entry in data:
        z_name = entry.get("zone_name", "")
        sensitive = set(entry.get("planting_months", [])) | set(entry.get("harvest_months", []))

        # Extract region names from zone_name (e.g., "(Analamanga, Vakinankaratra, Itasy)")
        if "(" in z_name and ")" in z_name:
            inside = z_name.split("(")[1].split(")")[0]
            parts = [p.strip().lower() for p in inside.split(",")]
            for part in parts:
                region_sensitive_months.setdefault(part, set()).update(sensitive)
        else:
            region_sensitive_months.setdefault(z_name.lower(), set()).update(sensitive)

    return region_sensitive_months


def evaluate_price_spike_rules(session: Session) -> list[AlertCandidate]:
    """Evaluate PRICE_SPIKE rule: z > 3 and chg_1m > 0.15.

    Fed by statistical anomalies from ketrika.ml.anomalies.detect_price_anomalies.
    Severity: 'high' if confirmed by >= 2 distinct sources in same month, else 'medium'.
    dedupe_key: PRICE_SPIKE|{product_code}|{location_pcode}|{month}
    """
    from ketrika.ml.anomalies import detect_price_anomalies

    anomalies = detect_price_anomalies(session, z_threshold=3.0, chg_threshold=0.15)
    candidates: list[AlertCandidate] = []

    for anom in anomalies:
        if anom.anomaly_type != "PRICE_SPIKE":
            continue
        month_str = str(anom.month)[:7]
        pcode = anom.location_pcode or (
            str(anom.location_id)[:8] if anom.location_id else "unknown"
        )
        dedupe = f"PRICE_SPIKE|{anom.product_code}|{pcode}|{month_str}"
        chg_pct = round(float(anom.chg_1m) * 100, 1) if anom.chg_1m is not None else 0.0
        z = round(float(anom.z_score_robust), 2)

        title = f"Flambée des prix : {anom.product_name} à {anom.location_name} (+{chg_pct}% sur 1 mois, z={z})"
        candidates.append(
            AlertCandidate(
                rule_code="PRICE_SPIKE",
                dedupe_key=dedupe,
                severity=anom.severity,
                title=title,
                evidence=anom.evidence,
                product_id=anom.product_id,
                location_id=anom.location_id,
            )
        )

    return candidates


def evaluate_price_drop_rules(session: Session) -> list[AlertCandidate]:
    """Evaluate PRICE_DROP rule: z < -3 and chg_1m < -0.15.

    Fed by statistical anomalies from ketrika.ml.anomalies.detect_price_anomalies.
    Severity: 'medium'.
    dedupe_key: PRICE_DROP|{product_code}|{location_pcode}|{month}
    """
    from ketrika.ml.anomalies import detect_price_anomalies

    anomalies = detect_price_anomalies(session, z_threshold=3.0, chg_threshold=0.15)
    candidates: list[AlertCandidate] = []

    for anom in anomalies:
        if anom.anomaly_type != "PRICE_DROP":
            continue
        month_str = str(anom.month)[:7]
        pcode = anom.location_pcode or (
            str(anom.location_id)[:8] if anom.location_id else "unknown"
        )
        dedupe = f"PRICE_DROP|{anom.product_code}|{pcode}|{month_str}"
        chg_pct = round(float(anom.chg_1m) * 100, 1) if anom.chg_1m is not None else 0.0
        z = round(float(anom.z_score_robust), 2)

        title = f"Chute anormale des prix : {anom.product_name} à {anom.location_name} ({chg_pct}% sur 1 mois, z={z})"
        candidates.append(
            AlertCandidate(
                rule_code="PRICE_DROP",
                dedupe_key=dedupe,
                severity=anom.severity,
                title=title,
                evidence=anom.evidence,
                product_id=anom.product_id,
                location_id=anom.location_id,
            )
        )

    return candidates


def evaluate_stockout_risk_rules(session: Session) -> list[AlertCandidate]:
    """Evaluate STOCKOUT_RISK rule:

    Degraded stock status ('tight' or 'shortage') over 2 consecutive observations and chg_1m > 0.
    Severity: 'high' if latest is 'shortage', else 'medium'.
    dedupe_key: STOCKOUT|{product_code}|{location_pcode}|{period}
    """
    query = text(
        """
        WITH ranked_stocks AS (
            SELECT
                so.product_id,
                p.product_code,
                p.canonical_name_fr AS product_name,
                so.location_id,
                loc.pcode AS location_pcode,
                loc.name AS location_name,
                so.stock_status,
                so.period_end,
                ROW_NUMBER() OVER (
                    PARTITION BY so.product_id, so.location_id
                    ORDER BY so.period_end DESC, so.ingested_at DESC
                ) AS rn
            FROM obs.stock_observation so
            JOIN ref.product p ON so.product_id = p.product_id
            JOIN ref.location loc ON so.location_id = loc.location_id
            WHERE so.superseded_by IS NULL
              AND so.stock_status IS NOT NULL
        ),
        last_two AS (
            SELECT
                product_id,
                product_code,
                product_name,
                location_id,
                location_pcode,
                location_name,
                MAX(CASE WHEN rn = 1 THEN stock_status END) AS latest_status,
                MAX(CASE WHEN rn = 2 THEN stock_status END) AS prev_status,
                MAX(CASE WHEN rn = 1 THEN period_end END) AS latest_period
            FROM ranked_stocks
            WHERE rn <= 2
            GROUP BY product_id, product_code, product_name, location_id, location_pcode, location_name
            HAVING count(*) >= 2
        )
        SELECT
            lt.product_id,
            lt.product_code,
            lt.product_name,
            lt.location_id,
            lt.location_pcode,
            lt.location_name,
            lt.latest_status,
            lt.prev_status,
            lt.latest_period,
            COALESCE(pc.chg_1m, 0.05) AS chg_1m
        FROM last_two lt
        LEFT JOIN gold.price_changes pc
          ON lt.product_id = pc.product_id
         AND lt.location_id = pc.location_id
         AND pc.month = date_trunc('month', lt.latest_period)::date
        WHERE lt.latest_status IN ('tight', 'shortage')
          AND lt.prev_status IN ('tight', 'shortage')
          AND (pc.chg_1m IS NULL OR pc.chg_1m > 0);
        """
    )
    rows = session.execute(query).fetchall()
    candidates: list[AlertCandidate] = []

    for r in rows:
        severity = "high" if r.latest_status == "shortage" else "medium"
        period_str = str(r.latest_period)[:7]
        pcode = r.location_pcode or str(r.location_id)[:8]
        dedupe = f"STOCKOUT|{r.product_code}|{pcode}|{period_str}"

        title = f"Risque de rupture de stock : {r.product_name} à {r.location_name} (statut: {r.latest_status})"
        evidence = {
            "rule": "STOCKOUT_RISK",
            "product_code": r.product_code,
            "product_name": r.product_name,
            "location_pcode": r.location_pcode,
            "location_name": r.location_name,
            "latest_status": r.latest_status,
            "prev_status": r.prev_status,
            "latest_period": str(r.latest_period),
            "chg_1m": float(r.chg_1m) if r.chg_1m is not None else None,
        }

        candidates.append(
            AlertCandidate(
                rule_code="STOCKOUT_RISK",
                dedupe_key=dedupe,
                severity=severity,
                title=title,
                evidence=evidence,
                product_id=r.product_id,
                location_id=r.location_id,
            )
        )

    return candidates


def evaluate_climate_risk_rules(session: Session) -> list[AlertCandidate]:
    """Evaluate CLIMATE_RISK rule:

    Monthly rainfall anomaly < -30% in a production region during sensitive crop window.
    Severity: 'medium' ('high' if < -50%).
    dedupe_key: CLIMATE|{region_pcode}|{month}
    """
    sensitive_map = load_crop_calendar_sensitive_months()

    query = text(
        """
        SELECT
            wm.location_id,
            wm.location_pcode,
            wm.location_name,
            wm.month,
            wm.precip_total_mm,
            wm.baseline_precip_mm,
            wm.rain_anom_pct
        FROM gold.weather_monthly wm
        WHERE wm.rain_anom_pct < -0.30
        ORDER BY wm.month DESC, wm.rain_anom_pct ASC;
        """
    )
    rows = session.execute(query).fetchall()
    candidates: list[AlertCandidate] = []

    for r in rows:
        cal_month = r.month.month
        loc_name_lower = (r.location_name or "").lower()

        # Check if current month is in sensitive calendar window for this region
        is_sensitive = False
        for reg_key, months in sensitive_map.items():
            if reg_key in loc_name_lower and cal_month in months:
                is_sensitive = True
                break

        # If no specific match or map empty, default to checking if severe anomaly (< -40%)
        if not is_sensitive and float(r.rain_anom_pct) > -0.40:
            continue

        anom = float(r.rain_anom_pct)
        severity = "high" if anom < -0.50 else "medium"
        month_str = str(r.month)[:7]
        pcode = r.location_pcode or str(r.location_id)[:8]
        dedupe = f"CLIMATE|{pcode}|{month_str}"
        anom_pct = round(anom * 100, 1)

        title = f"Déficit pluviométrique critique : {r.location_name} ({anom_pct}% vs normale)"
        evidence = {
            "rule": "CLIMATE_RISK",
            "location_pcode": r.location_pcode,
            "location_name": r.location_name,
            "month": str(r.month),
            "precip_total_mm": float(r.precip_total_mm),
            "baseline_precip_mm": float(r.baseline_precip_mm),
            "rain_anom_pct": anom,
            "in_crop_window": is_sensitive,
        }

        candidates.append(
            AlertCandidate(
                rule_code="CLIMATE_RISK",
                dedupe_key=dedupe,
                severity=severity,
                title=title,
                evidence=evidence,
                location_id=r.location_id,
            )
        )

    return candidates


def evaluate_data_stale_rules(session: Session) -> list[AlertCandidate]:
    """Evaluate DATA_STALE rule:

    P0 source exceeding freshness SLA.
    Severity: 'low'.
    dedupe_key: STALE|{source_id}|{date}
    """
    query = text(
        """
        SELECT
            sh.source_id,
            sh.priority,
            sh.freshness_sla_days,
            sh.freshness_days,
            sh.is_stale,
            sh.last_run_started_at
        FROM gold.source_health sh
        WHERE sh.priority = 'P0'
          AND sh.is_stale = true;
        """
    )
    rows = session.execute(query).fetchall()
    candidates: list[AlertCandidate] = []
    today_str = datetime.now(UTC).date().isoformat()

    for r in rows:
        dedupe = f"STALE|{r.source_id}|{today_str}"
        title = f"Source de données obsolète : {r.source_id} (hors SLA de fraîcheur)"
        evidence = {
            "rule": "DATA_STALE",
            "source_id": r.source_id,
            "priority": r.priority,
            "freshness_sla_days": r.freshness_sla_days,
            "freshness_days": r.freshness_days,
            "last_run": (r.last_run_started_at.isoformat() if r.last_run_started_at else None),
        }

        candidates.append(
            AlertCandidate(
                rule_code="DATA_STALE",
                dedupe_key=dedupe,
                severity="low",
                title=title,
                evidence=evidence,
            )
        )

    return candidates


def evaluate_all_rules(session: Session) -> list[AlertCandidate]:
    """Evaluate all 5 alert rules against current Gold database state."""
    candidates: list[AlertCandidate] = []
    candidates.extend(evaluate_price_spike_rules(session))
    candidates.extend(evaluate_price_drop_rules(session))
    candidates.extend(evaluate_stockout_risk_rules(session))
    candidates.extend(evaluate_climate_risk_rules(session))
    candidates.extend(evaluate_data_stale_rules(session))
    return candidates
