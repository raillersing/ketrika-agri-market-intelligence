"""Trade Corridor Spatial Friction and Inland Logistics Modeling (SPECS §27, ADR-164).

Models transport costs and physical/security friction across the 3 primary logistics axes:
- RN2: Toamasina Port -> Antananarivo (Import Parity Corridor, 350 km)
- RN4: Mahajanga / Marovoay -> Antananarivo (Rice Granary Corridor, 570 km)
- RN34: Miandrivazo / Menabe -> Antsirabe -> Antananarivo (Cereals & Pulses Feeder, 400 km)
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

CORRIDOR_METADATA: dict[str, dict[str, Any]] = {
    "RN2": {
        "name": "Corridor RN2 (Toamasina - Antananarivo)",
        "distance_km": 350,
        "origin": "Toamasina Port",
        "destination": "Antananarivo (Anosibe)",
        "primary_flows": ["RICE_WHITE_IMPORTED", "VEG_OIL", "WHEAT_FLOUR", "SUGAR"],
        "criticality": "high_import_dependency",
    },
    "RN4": {
        "name": "Corridor RN4 (Mahajanga / Marovoay - Antananarivo)",
        "distance_km": 570,
        "origin": "Marovoay Plains / Mahajanga",
        "destination": "Antananarivo",
        "primary_flows": ["RICE_WHITE_LOCAL", "RICE_PADDY"],
        "criticality": "domestic_rice_supply",
    },
    "RN34": {
        "name": "Corridor RN34 (Miandrivazo - Antsirabe - Antananarivo)",
        "distance_km": 400,
        "origin": "Menabe / Miandrivazo Basin",
        "destination": "Antananarivo / Antsirabe",
        "primary_flows": ["MAIZE_GRAIN", "CASSAVA_DRIED", "BEANS_DRY", "GROUNDNUT"],
        "criticality": "feeder_cereals_and_pulses",
    },
}


def _shift_months(d: date, months: int) -> date:
    """Shift date by a given number of calendar months, anchoring on day 1."""
    y = d.year + (d.month + months - 1) // 12
    m = (d.month + months - 1) % 12 + 1
    return date(y, m, 1)


def get_macro_value_as_of(
    session: Session,
    indicator_code: str,
    as_of_date: date,
    max_lookback_months: int = 4,
) -> tuple[float, date, str, str] | None:
    """Query macro observation as of a cutoff date without future leakage.

    Strictly guarantees that:
    1. period_start is <= as_of_date and within the lookback window.
    2. published_at / first_available_at (when present) does not exceed as_of_date (anti-leakage).
    3. The observation was not superseded on or before as_of_date.

    Returns:
        tuple of (value, period_start, source_id, content_sha256) or None.
    """
    earliest_cutoff = _shift_months(as_of_date, -max_lookback_months)
    as_of_cutoff_dt = datetime.combine(as_of_date, time(23, 59, 59), tzinfo=UTC)
    sql = text("""
        SELECT
            mo.value::float,
            mo.period_start,
            sr.source_id,
            sr.content_sha256
        FROM obs.macro_observation mo
        JOIN meta.source_record sr ON mo.source_record_id = sr.source_record_id
        WHERE mo.indicator_code = :indicator
          AND mo.period_start <= :as_of_date
          AND mo.period_start >= :earliest_cutoff
          AND (mo.published_at IS NULL OR mo.published_at <= :as_of_cutoff_dt)
          AND (mo.first_available_at IS NULL OR mo.first_available_at <= :as_of_cutoff_dt)
          AND (
              mo.superseded_by IS NULL
              OR mo.superseded_by NOT IN (
                  SELECT sub_mo.observation_id
                  FROM obs.macro_observation sub_mo
                  WHERE sub_mo.published_at <= :as_of_cutoff_dt
              )
          )
        ORDER BY mo.period_start DESC, mo.published_at DESC NULLS LAST
        LIMIT 1;
    """)
    row = session.execute(
        sql,
        {
            "indicator": indicator_code,
            "as_of_date": as_of_date,
            "earliest_cutoff": earliest_cutoff,
            "as_of_cutoff_dt": as_of_cutoff_dt,
        },
    ).fetchone()
    if not row:
        return None
    return float(row[0]), row[1], str(row[2]), str(row[3])


def compute_corridor_friction(
    session: Session,
    corridor_code: str,
    as_of_date: date,
) -> dict[str, Any] | None:
    """Compute detailed transport logistics cost and friction breakdown for a corridor (ADR-164).

    Formula:
        TotalFrictionMultiplier = RoadFactor * (1.0 + SecurityFrictionPct / 100.0)
        EffectiveTransportCostMT = BaseCostMT * TotalFrictionMultiplier
    """
    code = corridor_code.upper()
    meta = CORRIDOR_METADATA.get(code)
    if not meta:
        return None

    base_indicator = f"CORRIDOR_BASE_COST_{code}_TON_MGA"
    road_indicator = f"CORRIDOR_ROAD_FACTOR_{code}"
    security_indicator = f"CORRIDOR_SECURITY_FRICTION_{code}_PCT"

    base_res = get_macro_value_as_of(session, base_indicator, as_of_date)
    road_res = get_macro_value_as_of(session, road_indicator, as_of_date)
    sec_res = get_macro_value_as_of(session, security_indicator, as_of_date)

    if not base_res:
        return None

    base_cost_mt, base_period, base_src, base_sha = base_res
    road_factor = road_res[0] if road_res else 1.0
    sec_friction_pct = sec_res[0] if sec_res else 0.0

    # Diesel reference
    diesel_res = get_macro_value_as_of(session, "FUEL_DIESEL", as_of_date)
    diesel_price = diesel_res[0] if diesel_res else None

    # Effective Transport Cost
    total_multiplier = road_factor * (1.0 + (sec_friction_pct / 100.0))
    effective_cost_mt = round(base_cost_mt * total_multiplier, 2)
    effective_cost_kg = round(effective_cost_mt / 1000.0, 2)
    friction_surplus_mt = round(effective_cost_mt - base_cost_mt, 2)
    total_friction_pct = round((total_multiplier - 1.0) * 100.0, 1)

    # Status classification
    if total_friction_pct >= 25.0:
        status = "critical_friction"
    elif total_friction_pct >= 10.0:
        status = "moderate_friction"
    else:
        status = "normal_flow"

    provenance = [
        {
            "indicator": base_indicator,
            "source_id": base_src,
            "sha256": base_sha,
            "period": base_period.isoformat(),
        }
    ]
    if road_res:
        provenance.append(
            {
                "indicator": road_indicator,
                "source_id": road_res[2],
                "sha256": road_res[3],
                "period": road_res[1].isoformat(),
            }
        )
    if sec_res:
        provenance.append(
            {
                "indicator": security_indicator,
                "source_id": sec_res[2],
                "sha256": sec_res[3],
                "period": sec_res[1].isoformat(),
            }
        )

    return {
        "corridor_code": code,
        "corridor_name": meta["name"],
        "distance_km": meta["distance_km"],
        "origin": meta["origin"],
        "destination": meta["destination"],
        "primary_flows": meta["primary_flows"],
        "as_of_date": as_of_date.isoformat(),
        "diesel_mga_liter": diesel_price,
        "base_cost_mga_mt": round(base_cost_mt, 2),
        "road_factor": round(road_factor, 2),
        "security_friction_pct": round(sec_friction_pct, 1),
        "total_friction_pct": total_friction_pct,
        "effective_cost_mga_mt": effective_cost_mt,
        "effective_cost_mga_kg": effective_cost_kg,
        "friction_surplus_mga_mt": friction_surplus_mt,
        "status": status,
        "qualification": "authenticated_bronze_silver",
        "provenance_records": provenance,
    }


def get_all_corridors_summary(session: Session, as_of_date: date) -> list[dict[str, Any]]:
    """Retrieve friction and transport costs for all 3 major corridors as of a cutoff date."""
    summaries: list[dict[str, Any]] = []
    for code in CORRIDOR_METADATA:
        res = compute_corridor_friction(session, code, as_of_date)
        if res:
            summaries.append(res)
    return summaries
