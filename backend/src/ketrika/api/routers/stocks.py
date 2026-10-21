"""Stocks router (SPECS §19)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.api.schemas import StockItem
from ketrika.core.db import get_db
from ketrika.gold.compatibility import is_gold_view_populated

router = APIRouter(prefix="/v1/stocks", tags=["stocks"])


@router.get("", response_model=list[StockItem])
def get_stocks(
    product: str | None = Query(None, description="Product code or UUID"),
    location: str | None = Query(None, description="Location P-code or UUID"),
    session: Session = Depends(get_db),
) -> list[StockItem]:
    """Retrieve the latest observed stock status by product and location (SPECS §19)."""
    if not is_gold_view_populated(session, "stock_latest"):
        return []

    sql = """
        SELECT
            product_code,
            location_pcode,
            location_name,
            stock_status,
            coverage_days::float,
            trend
        FROM gold.stock_latest
        WHERE 1=1
    """
    params: dict[str, Any] = {}
    if product:
        sql += " AND (product_code = :product OR product_id::text = :product)"
        params["product"] = product
    if location:
        sql += " AND (location_pcode = :loc OR location_id::text = :loc)"
        params["loc"] = location

    sql += " ORDER BY product_code, location_pcode;"
    rows = session.execute(text(sql), params).fetchall()

    results: list[StockItem] = []
    for r in rows:
        results.append(
            StockItem(
                product_code=r[0],
                location_pcode=r[1],
                location_name=r[2],
                stock_status=r[3],
                coverage_days=float(r[4]) if r[4] is not None else None,
                trend_3obs=r[5],
                value_kind="observed",
                sources=["mincc_ppn"],
            )
        )
    return results
