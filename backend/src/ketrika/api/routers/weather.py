"""Weather and climate anomalies router (SPECS §19)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.api.gold_availability import require_gold_view
from ketrika.api.schemas import WeatherAnomalyItem
from ketrika.core.db import get_db

router = APIRouter(prefix="/v1/weather", tags=["weather"])


@router.get("/anomalies", response_model=list[WeatherAnomalyItem])
def get_weather_anomalies(
    location: str | None = Query(None, description="District P-code or UUID"),
    from_date: str | None = Query(None, alias="from", description="Start month (YYYY-MM-01)"),
    to_date: str | None = Query(None, alias="to", description="End month (YYYY-MM-01)"),
    session: Session = Depends(get_db),
) -> list[WeatherAnomalyItem]:
    """Retrieve monthly weather observations, precip anomalies and temperatures (SPECS §19)."""
    require_gold_view(session, "weather_monthly")

    sql = """
        SELECT
            location_pcode,
            location_name,
            month::text AS month,
            precip_total_mm::float,
            (rain_anom_pct * 100.0)::float AS precip_anomaly_pct,
            ((t2m_max_avg_c + t2m_min_avg_c) / 2.0)::float AS t2m_mean
        FROM gold.weather_monthly
        WHERE 1=1
    """
    params: dict[str, Any] = {}
    if location:
        sql += " AND (location_pcode = :loc OR location_id::text = :loc)"
        params["loc"] = location
    if from_date:
        sql += " AND month >= :from_date::date"
        params["from_date"] = from_date
    if to_date:
        sql += " AND month <= :to_date::date"
        params["to_date"] = to_date

    sql += " ORDER BY month ASC, location_pcode;"
    rows = session.execute(text(sql), params).fetchall()

    results: list[WeatherAnomalyItem] = []
    for r in rows:
        results.append(
            WeatherAnomalyItem(
                district_pcode=r[0],
                district_name=r[1],
                month=r[2],
                precip_total_mm=float(r[3]),
                precip_anomaly_pct=float(r[4]) if r[4] is not None else None,
                t2m_mean=float(r[5]) if r[5] is not None else None,
                value_kind="observed",
                sources=["nasa_power"],
            )
        )
    return results
