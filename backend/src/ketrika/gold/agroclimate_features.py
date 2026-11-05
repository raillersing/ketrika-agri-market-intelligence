"""Agroclimatic Phenological Modeling and Crop Stage Stress Features (SPECS §27, ADR-164).

Combines verified rainfall anomalies from gold.weather_monthly with official crop calendars
(taxonomy/crop_calendar.yaml) to compute biologically weighted phenological stress indices
for Madagascar staple crops (RICE, MAIZE, CASSAVA).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.geo.calendar import detect_phenological_stage
from ketrika.geo.contracts import CropCalendarRecord, load_crop_calendar

logger = logging.getLogger(__name__)

# Normative vulnerability weights by phenological stage (SPECS §27.1.3)
STAGE_WEIGHTS: dict[str, float] = {
    "flowering": 0.50,  # Critical flower fertilization / grain filling
    "grain_filling": 0.50,
    "peak_harvest": 0.50,  # Critical peak maturation/filling
    "tillering": 0.25,  # Vegetative biomass development
    "growing": 0.25,
    "vegetative": 0.25,
    "planting": 0.20,  # Seed germination & seedling establishment
    "establishment": 0.20,
    "harvest": 0.05,  # Harvest stage (dry matter secured, slight waterlogging risk)
    "off_season": 0.00,
}

PCODE_TO_BASIN: dict[str, str] = {
    "MDG11": "ZONE_CENTRE",
    "MDG12": "ZONE_CENTRE",
    "MDG13": "ZONE_CENTRE",
    "MDG31": "ZONE_EST",
    "MDG32": "ZONE_ALAOTRA",
    "MDG33": "ZONE_EST",
    "MDG41": "ZONE_BOENY",
    "MDG51": "ZONE_SUD",
    "MDG52": "ZONE_SUD",
    "MDG53": "ZONE_SUD",
}


def _shift_months(d: date, months: int) -> date:
    """Shift date by a given number of calendar months, anchoring on day 1."""
    y = d.year + (d.month + months - 1) // 12
    m = (d.month + months - 1) % 12 + 1
    return date(y, m, 1)


@dataclass(frozen=True)
class MonthlyStageEvaluation:
    month_date: date
    month_int: int
    stage: str
    weight: float
    observed_precip_mm: float | None
    baseline_precip_mm: float | None
    rain_anom_pct: float | None
    deficit_stress: float
    excess_stress: float


def get_crop_calendar_for_region(
    records: list[CropCalendarRecord],
    zone_code: str,
    product_code: str,
) -> CropCalendarRecord | None:
    """Find the verified active crop calendar for given basin and product."""
    for rec in records:
        if not rec.is_active or not rec.verified:
            continue
        if rec.zone_code == zone_code and rec.product_code == product_code:
            return rec
    # Fallback to crop family match (e.g. RICE_WHITE_LOCAL maps to RICE_PADDY calendar)
    if product_code in ("RICE_WHITE_LOCAL", "RICE_WHITE_IMPORTED", "RICE_PADDY"):
        for rec in records:
            if rec.is_active and rec.verified and rec.zone_code == zone_code and rec.crop == "RICE":
                return rec
    return None


def query_weather_monthly_history(
    session: Session,
    location_pcode: str,
    start_month: date,
    end_month: date,
) -> dict[date, dict[str, float]]:
    """Query gold.weather_monthly for a given location and range without future data leakage."""
    sql = text("""
        SELECT
            month,
            precip_total_mm::float,
            baseline_precip_mm::float,
            rain_anom_pct::float
        FROM gold.weather_monthly
        WHERE (location_pcode = :loc OR location_id::text = :loc)
          AND month >= :start_month
          AND month <= :end_month
        ORDER BY month ASC;
    """)
    rows = session.execute(
        sql,
        {"loc": location_pcode, "start_month": start_month, "end_month": end_month},
    ).fetchall()

    history: dict[date, dict[str, float]] = {}
    for r in rows:
        m = r[0]
        precip = float(r[1]) if r[1] is not None else 0.0
        base = float(r[2]) if r[2] is not None else 0.0
        anom = float(r[3]) if r[3] is not None else 0.0
        history[m] = {
            "precip_total_mm": precip,
            "baseline_precip_mm": base,
            "rain_anom_pct": anom,
        }
    return history


def compute_phenological_stress(
    session: Session,
    location_pcode: str,
    product_code: str,
    as_of_date: date,
    lookback_months: int = 3,
) -> dict[str, Any] | None:
    """Compute biologically weighted phenological stress score (ADR-164).

    Evaluates the last `lookback_months` preceding `as_of_date`.
    Scores range from:
      -1.0 : extreme drought during critical flowering/growth stages
       0.0 : optimal baseline agroclimatic conditions
      +1.0 : extreme rainfall excess / flooding during ripening or flowering
    """
    zone_code = PCODE_TO_BASIN.get(location_pcode)
    if not zone_code:
        # If not in top basins, check location name or default to ZONE_CENTRE
        zone_code = "ZONE_CENTRE"

    all_calendars = load_crop_calendar()
    calendar = get_crop_calendar_for_region(all_calendars, zone_code, product_code)
    if not calendar:
        return None

    end_month = as_of_date.replace(day=1)
    start_month = _shift_months(end_month, -lookback_months + 1)

    weather_data = query_weather_monthly_history(
        session=session,
        location_pcode=location_pcode,
        start_month=start_month,
        end_month=end_month,
    )

    stage_evaluations: list[MonthlyStageEvaluation] = []
    total_weight = 0.0
    weighted_deficit_sum = 0.0
    weighted_excess_sum = 0.0

    curr = start_month
    while curr <= end_month:
        month_int = curr.month
        raw_stage = detect_phenological_stage(calendar, month_int)
        stage_key = raw_stage or "off_season"
        weight = STAGE_WEIGHTS.get(stage_key, 0.0)

        w_row = weather_data.get(curr)
        precip = w_row["precip_total_mm"] if w_row else None
        base = w_row["baseline_precip_mm"] if w_row else None
        anom = w_row["rain_anom_pct"] if w_row else None

        deficit = 0.0
        excess = 0.0
        if anom is not None:
            # Deficit: rain below normal (anom < 0)
            if anom < 0:
                # clamp deficit intensity between 0 and 1 (where -1.0 means 100% rain missing)
                deficit = min(1.0, abs(anom))
            else:
                # Excess: rain above normal (anom > 0, capped at 1.0 for +100% anomaly)
                excess = min(1.0, anom)

        if weight > 0.0:
            total_weight += weight
            weighted_deficit_sum += weight * deficit
            weighted_excess_sum += weight * excess

        stage_evaluations.append(
            MonthlyStageEvaluation(
                month_date=curr,
                month_int=month_int,
                stage=stage_key,
                weight=weight,
                observed_precip_mm=precip,
                baseline_precip_mm=base,
                rain_anom_pct=anom,
                deficit_stress=round(deficit, 3),
                excess_stress=round(excess, 3),
            )
        )
        curr = _shift_months(curr, 1)

    if total_weight > 0.0:
        net_deficit_score = weighted_deficit_sum / total_weight
        net_excess_score = weighted_excess_sum / total_weight
        # Composite score: deficit is negative [-1, 0], excess is positive [0, 1]
        composite_stress = round(net_excess_score - net_deficit_score, 3)
    else:
        composite_stress = 0.0

    # Categorical assessment
    if composite_stress <= -0.40:
        stress_category = "severe_deficit"
    elif composite_stress <= -0.15:
        stress_category = "moderate_deficit"
    elif composite_stress >= 0.40:
        stress_category = "severe_excess_flood_risk"
    elif composite_stress >= 0.15:
        stress_category = "moderate_excess"
    else:
        stress_category = "optimal"

    # Identify primary vulnerability stage
    critical_stages = [e for e in stage_evaluations if e.weight >= 0.25 and e.stage != "off_season"]
    primary_stage = critical_stages[-1].stage if critical_stages else (stage_evaluations[-1].stage if stage_evaluations else "off_season")

    return {
        "location_pcode": location_pcode,
        "product_code": product_code,
        "crop": calendar.crop,
        "zone_code": zone_code,
        "zone_name": calendar.zone_name,
        "crop_cycle": calendar.season_name,
        "as_of_date": as_of_date.isoformat(),
        "lookback_months": lookback_months,
        "phenological_stress_index": composite_stress,
        "stress_category": stress_category,
        "primary_stage": primary_stage,
        "active_calendar_verified": calendar.verified,
        "calendar_source": calendar.source_reference,
        "stage_evaluations": [
            {
                "month": e.month_date.isoformat(),
                "stage": e.stage,
                "weight": e.weight,
                "precip_mm": e.observed_precip_mm,
                "baseline_precip_mm": e.baseline_precip_mm,
                "rain_anom_pct": round(e.rain_anom_pct * 100.0, 1) if e.rain_anom_pct is not None else None,
                "deficit_stress": e.deficit_stress,
                "excess_stress": e.excess_stress,
            }
            for e in stage_evaluations
        ],
    }


def get_regional_phenological_stress_series(
    session: Session,
    location_pcode: str,
    product_code: str,
    start_date: date | None = None,
    end_date: date | None = None,
    lookback_months: int = 3,
) -> list[dict[str, Any]]:
    """Generate time series of phenological stress scores for ML causal regressor features."""
    start = start_date or date(2024, 1, 1)
    end = end_date or date(2026, 10, 1)
    series: list[dict[str, Any]] = []

    curr = start.replace(day=1)
    while curr <= end:
        res = compute_phenological_stress(
            session=session,
            location_pcode=location_pcode,
            product_code=product_code,
            as_of_date=curr,
            lookback_months=lookback_months,
        )
        if res:
            series.append(res)
        curr = _shift_months(curr, 1)

    return series
