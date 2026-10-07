"""KPI and Market Health router (SPECS §19)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.api.schemas import MarketHealthItem
from ketrika.core.db import get_db

router = APIRouter(prefix="/v1/kpis", tags=["kpis"])


@router.get("/market-health", response_model=list[MarketHealthItem])
def get_market_health(
    product: str | None = Query(None, description="Product code or UUID"),
    location: str | None = Query(None, description="Region P-code or UUID"),
    month: str | None = Query(None, description="Month (YYYY-MM-01)"),
    session: Session = Depends(get_db),
) -> list[MarketHealthItem]:
    """Retrieve Market Health Score (0-100) and its 4 underlying components (SPECS §16, §19)."""
    sql = """
        SELECT
            product_code,
            location_pcode,
            location_name,
            month::text AS month,
            score_stability::float,
            score_affordability::float,
            score_availability::float,
            score_climate::float,
            coverage::float,
            market_health_score::float
        FROM gold.market_health
        WHERE 1=1
    """
    params: dict[str, Any] = {}
    if product:
        sql += " AND (product_code = :product OR product_id::text = :product)"
        params["product"] = product
    if location:
        sql += " AND (location_pcode = :loc OR location_id::text = :loc)"
        params["loc"] = location
    if month:
        sql += " AND month = :month::date"
        params["month"] = month

    sql += " ORDER BY month DESC, product_code, location_pcode;"
    rows = session.execute(text(sql), params).fetchall()

    results: list[MarketHealthItem] = []
    for r in rows:
        comps_present = []
        if r[4] is not None:
            comps_present.append("price_stability")
        if r[5] is not None:
            comps_present.append("affordability")
        if r[6] is not None:
            comps_present.append("availability")
        if r[7] is not None:
            comps_present.append("climate_risk")

        results.append(
            MarketHealthItem(
                product_code=r[0],
                region_pcode=r[1],
                region_name=r[2],
                month=r[3],
                price_stability_score=float(r[4]) if r[4] is not None else None,
                affordability_score=float(r[5]) if r[5] is not None else None,
                availability_score=float(r[6]) if r[6] is not None else None,
                climate_risk_score=float(r[7]) if r[7] is not None else None,
                coverage=float(r[8]),
                composite_score=float(r[9]) if r[9] is not None else None,
                value_kind="composite",
                components_present=comps_present,
            )
        )
    return results
