"""Macroeconomic observation router (SPECS §19, ADR-069)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.api.schemas import MacroItem
from ketrika.core.db import get_db

router = APIRouter(prefix="/v1/macro", tags=["macro"])


@router.get("", response_model=list[MacroItem])
def get_macro(
    indicator: str | None = Query(None, description="Indicator code (e.g. GDP_NOMINAL_MGA, FX_USD_MGA)"),
    geo_scope: str | None = Query(None, description="Geographic scope (e.g. national, pcode)"),
    vintage: str | None = Query(None, description="Vintage / release status (e.g. preliminary, final)"),
    from_date: dt.date | None = Query(None, alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: dt.date | None = Query(None, alias="to", description="End date (YYYY-MM-DD)"),
    session: Session = Depends(get_db),
) -> list[MacroItem]:
    """Retrieve macroeconomic observations (SPECS §19, ADR-069)."""
    sql = """
        SELECT
            m.observation_id,
            m.indicator_code,
            m.indicator_name,
            m.geo_scope,
            m.frequency,
            m.unit,
            m.base_period,
            m.period_start,
            m.period_end,
            m.vintage,
            m.value::float,
            m.value_raw,
            m.observed_or_imputed,
            m.first_available_at,
            m.published_at,
            sr.source_id
        FROM obs.macro_observation m
        JOIN meta.source_record sr ON m.source_record_id = sr.source_record_id
        WHERE m.superseded_by IS NULL
    """
    params: dict[str, Any] = {}
    if indicator:
        sql += " AND m.indicator_code = :indicator"
        params["indicator"] = indicator
    if geo_scope:
        sql += " AND m.geo_scope = :geo_scope"
        params["geo_scope"] = geo_scope
    if vintage:
        sql += " AND m.vintage = :vintage"
        params["vintage"] = vintage
    if from_date:
        sql += " AND m.period_end >= :from_date"
        params["from_date"] = from_date
    if to_date:
        sql += " AND m.period_start <= :to_date"
        params["to_date"] = to_date

    sql += " ORDER BY m.indicator_code, m.period_start ASC, m.vintage ASC;"
    rows = session.execute(text(sql), params).fetchall()

    results: list[MacroItem] = []
    for r in rows:
        results.append(
            MacroItem(
                observation_id=r[0],
                indicator_code=r[1],
                indicator_name=r[2],
                geo_scope=r[3],
                frequency=r[4],
                unit=r[5],
                base_period=r[6],
                period_start=r[7].isoformat() if hasattr(r[7], "isoformat") else str(r[7]),
                period_end=r[8].isoformat() if hasattr(r[8], "isoformat") else str(r[8]),
                vintage=r[9],
                value=float(r[10]) if r[10] is not None else None,
                value_raw=r[11],
                observed_or_imputed=r[12],
                first_available_at=r[13],
                published_at=r[14],
                sources=[r[15]] if r[15] else [],
            )
        )
    return results
