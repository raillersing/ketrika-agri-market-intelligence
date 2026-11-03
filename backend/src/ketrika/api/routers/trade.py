"""International trade router (SPECS §19)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.api.gold_availability import require_gold_view
from ketrika.api.schemas import TradeItem
from ketrika.core.db import get_db
from ketrika.core.taxonomy import resolve_product

router = APIRouter(prefix="/v1/trade", tags=["trade"])


@router.get("", response_model=list[TradeItem])
def get_trade(
    product: str | None = Query(None, description="Product code or UUID"),
    flow: str | None = Query(None, description="Trade flow: import or export"),
    from_date: str | None = Query(None, alias="from", description="Start month (YYYY-MM-01)"),
    to_date: str | None = Query(None, alias="to", description="End month (YYYY-MM-01)"),
    session: Session = Depends(get_db),
) -> list[TradeItem]:
    """Retrieve monthly trade flows (import / export) for PPN commodities (SPECS §19)."""
    require_gold_view(session, "trade_monthly")

    sql = """
        SELECT
            product_code,
            flow,
            month::text AS month,
            weight_tonnes::float,
            value_mga::float,
            value_usd::float
        FROM gold.trade_monthly
        WHERE 1=1
    """
    params: dict[str, Any] = {}
    if product:
        resolved = resolve_product(product)
        canonical = resolved[0] if resolved else None
        if canonical and canonical != product:
            sql += " AND (product_code = :product OR product_code = :canonical OR product_id::text = :product)"
            params["canonical"] = canonical
        else:
            sql += " AND (product_code = :product OR product_id::text = :product)"
        params["product"] = product
    if flow:
        sql += " AND flow = :flow"
        params["flow"] = flow
    if from_date:
        sql += " AND month >= :from_date::date"
        params["from_date"] = from_date
    if to_date:
        sql += " AND month <= :to_date::date"
        params["to_date"] = to_date

    sql += " ORDER BY month ASC, product_code, flow;"
    rows = session.execute(text(sql), params).fetchall()

    results: list[TradeItem] = []
    for r in rows:
        results.append(
            TradeItem(
                product_code=r[0],
                flow=r[1],
                month=r[2],
                weight_tons=float(r[3]),
                value_mga=float(r[4]) if r[4] is not None else None,
                value_usd=float(r[5]) if r[5] is not None else None,
                value_kind="observed",
                sources=["douanes_stats", "faostat"],
            )
        )
    return results
