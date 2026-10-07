"""Forecasts router (SPECS §19)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.api.schemas import ForecastItem
from ketrika.core.db import get_db

router = APIRouter(prefix="/v1/forecasts", tags=["forecasts"])


@router.get("", response_model=list[ForecastItem])
def get_forecasts(
    product: str | None = Query(None, description="Product code or UUID"),
    location: str | None = Query(None, description="Location P-code or UUID"),
    actor_level: str | None = Query(None, description="Actor level (e.g. retail, wholesale)"),
    session: Session = Depends(get_db),
) -> list[ForecastItem]:
    """Retrieve the latest price forecasts, prediction intervals and models (SPECS §17, §19)."""
    sql = """
        SELECT
            product_code,
            location_pcode,
            horizon,
            target_period::text,
            p10::float,
            p50::float,
            p90::float,
            model_name
        FROM gold.forecast_latest
        WHERE 1=1
    """
    params: dict[str, Any] = {}
    if product:
        sql += " AND (product_code = :product OR product_id::text = :product)"
        params["product"] = product
    if location:
        sql += " AND (location_pcode = :loc OR location_id::text = :loc)"
        params["loc"] = location
    if actor_level:
        sql += " AND actor_level = :actor"
        params["actor"] = actor_level

    sql += " ORDER BY product_code, location_pcode, horizon ASC;"
    rows = session.execute(text(sql), params).fetchall()

    results: list[ForecastItem] = []
    for r in rows:
        results.append(
            ForecastItem(
                product_code=r[0],
                location_pcode=r[1],
                horizon=int(r[2]),
                target_period=str(r[3]),
                p10=float(r[4]),
                p50=float(r[5]),
                p90=float(r[6]),
                model_name=r[7],
                value_kind="forecast",
            )
        )
    return results
