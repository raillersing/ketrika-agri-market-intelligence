"""Interpretable Economic Dashboard router (SPECS §19, ADR-070, R2.8)."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.api.csv_utils import export_csv_response
from ketrika.api.schemas import (
    DimensionSummaryOut,
    EconomicDashboardOut,
    EconomicMetricCardItem,
    IndicatorObservationOut,
    PilotEconomicContextOut,
)
from ketrika.core.db import get_db
from ketrika.gold.economic import (
    ECONOMIC_METRIC_CARDS,
    REASON_MISSING_SERIES,
    audit_inflation_vs_market_price_distinctness,
    calculate_import_unit_cost,
    query_economic_dashboard_from_db,
)
from ketrika.gold.provenance_gate import tables_for_views

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/economic", tags=["economic"])


@router.get("/indicators", response_model=list[EconomicMetricCardItem])
def get_economic_indicators(
    limit: int = Query(100, ge=1, le=1000, description="Page limit (default 100, max 1000)"),
    offset: int = Query(0, ge=0, description="Page offset (default 0)"),
    format: str = Query("json", description="Output format (json or csv)"),
) -> Any:
    """Return the normative catalog of economic metric cards with pagination and CSV export (ADR-071)."""
    cards = [
        EconomicMetricCardItem(
            metric_id=card.metric_id,
            dimension=card.dimension,
            title=card.title,
            definition=card.definition,
            formula=card.formula,
            unit=card.unit,
            frequency=card.frequency,
            geo_scope=card.geo_scope,
            primary_source=card.primary_source,
            source_family=card.source_family,
            publication_lag_days=card.publication_lag_days,
            limitations=card.limitations,
        )
        for card in ECONOMIC_METRIC_CARDS.values()
    ]
    actual_limit = int(limit.default) if hasattr(limit, "default") else int(limit)
    actual_offset = int(offset.default) if hasattr(offset, "default") else int(offset)
    actual_format = str(format.default) if hasattr(format, "default") else str(format)

    paged = cards[actual_offset : actual_offset + actual_limit]
    if actual_format == "csv":
        data = [item.model_dump() for item in paged]
        return export_csv_response(data, filename="economic_indicators.csv")
    return paged


@router.get("/dashboard", response_model=EconomicDashboardOut)
def get_economic_dashboard(
    month: dt.date | None = Query(None, description="Target calendar month (YYYY-MM-DD)"),
    session: Session = Depends(get_db),
) -> EconomicDashboardOut:
    """Return the interpretable economic dashboard grouped by autonomous dimensions."""
    try:
        db_items = query_economic_dashboard_from_db(session, target_month=month)
    except (ValueError, RuntimeError):
        raise HTTPException(status_code=503, detail="economic_data_not_qualified") from None

    # If DB view is empty (e.g. in test environment without full Gold refresh),
    # construct structured response from catalog with missingness reasons.
    target_month_str = month.isoformat() if month else dt.date.today().replace(day=1).isoformat()

    dimensions_map: dict[str, list[IndicatorObservationOut]] = {
        "inflation": [],
        "exchange_rate": [],
        "fuel_energy": [],
        "external_trade": [],
        "real_activity": [],
    }

    if db_items:
        for item in db_items:
            dim = item.dimension
            if dim in dimensions_map:
                dimensions_map[dim].append(
                    IndicatorObservationOut(
                        indicator_code=item.indicator_code,
                        dimension=item.dimension,
                        title=item.title,
                        unit=item.unit,
                        frequency=item.frequency,
                        geo_scope=item.geo_scope,
                        period_month=item.period_month,
                        current_value=item.current_value,
                        base_period=item.base_period,
                        chg_1m=item.chg_1m,
                        chg_12m=item.chg_12m,
                        null_reason=item.null_reason,
                        source_id=item.source_id,
                        source_family=item.source_family,
                        is_administered=item.is_administered,
                    )
                )
    else:
        # Populate empty baseline from catalog with explicit missingness
        for card in ECONOMIC_METRIC_CARDS.values():
            dimensions_map[card.dimension].append(
                IndicatorObservationOut(
                    indicator_code=card.metric_id,
                    dimension=card.dimension,
                    title=card.title,
                    unit=card.unit,
                    frequency=card.frequency,
                    geo_scope=card.geo_scope,
                    period_month=target_month_str,
                    current_value=None,
                    base_period=None,
                    chg_1m=None,
                    chg_12m=None,
                    null_reason=REASON_MISSING_SERIES,
                    source_id=None,
                    source_family=card.source_family,
                    is_administered=(card.dimension == "fuel_energy"),
                )
            )

    dimensions_out: dict[str, DimensionSummaryOut] = {}
    any_present = False
    all_complete = True

    for dim_name, ind_list in dimensions_map.items():
        n_total = len(ind_list)
        n_present = sum(1 for ind in ind_list if ind.current_value is not None)
        if n_present == n_total and n_total > 0:
            status = "complete"
            any_present = True
        elif n_present > 0:
            status = "partial"
            any_present = True
            all_complete = False
        else:
            status = "no_data"
            all_complete = False

        dimensions_out[dim_name] = DimensionSummaryOut(
            dimension=dim_name,
            completeness=status,
            indicators=ind_list,
        )

    if all_complete:
        overall = "complete"
    elif any_present:
        overall = "partial"
    else:
        overall = "no_data"

    catalog_out = {
        card.metric_id: EconomicMetricCardItem(
            metric_id=card.metric_id,
            dimension=card.dimension,
            title=card.title,
            definition=card.definition,
            formula=card.formula,
            unit=card.unit,
            frequency=card.frequency,
            geo_scope=card.geo_scope,
            primary_source=card.primary_source,
            source_family=card.source_family,
            publication_lag_days=card.publication_lag_days,
            limitations=card.limitations,
        )
        for card in ECONOMIC_METRIC_CARDS.values()
    }

    return EconomicDashboardOut(
        overall_status=overall,
        period_month=target_month_str,
        dimensions=dimensions_out,
        metric_catalog=catalog_out,
    )


@router.get("/pilot-context", response_model=PilotEconomicContextOut)
def get_pilot_economic_context(
    target_month: dt.date | None = Query(None, description="Month of analysis"),
    session: Session = Depends(get_db),
) -> PilotEconomicContextOut:
    """Return economic transmission context for the rice pilot (R2.8)."""
    try:
        tables_for_views(["economic_dashboard"])
    except ValueError:
        raise HTTPException(status_code=503, detail="economic_data_not_qualified") from None
    month_val = target_month or dt.date(2026, 5, 1)
    month_str = month_val.isoformat()

    # Query macro values
    sql_macro = """
        SELECT indicator_code, value::float
        FROM obs.macro_observation
        WHERE superseded_by IS NULL
          AND period_start <= :month_val
          AND period_end >= :month_val
    """
    macro_map: dict[str, float] = {}
    try:
        rows = session.execute(text(sql_macro), {"month_val": month_val}).fetchall()
        for r in rows:
            if r[1] is not None:
                macro_map[r[0]] = float(r[1])
    except Exception as exc:
        logger.warning("Could not query macro observations for pilot context: %s", exc)

    # Query pilot market price
    sql_price = """
        SELECT price_mga_per_base::float, chg_12m::float
        FROM gold.price_changes
        WHERE product_id IN (SELECT product_id FROM ref.product WHERE product_code = 'RICE_WHITE_LOCAL')
          AND month = :month_val
        LIMIT 1
    """
    market_price = None
    market_price_chg = None
    try:
        p_row = session.execute(text(sql_price), {"month_val": month_val}).fetchone()
        if p_row:
            market_price = float(p_row[0]) if p_row[0] is not None else None
            market_price_chg = float(p_row[1]) if p_row[1] is not None else None
    except Exception as exc:
        logger.warning("Could not query price changes for pilot context: %s", exc)

    fx = macro_map.get("EXCHANGE_RATE_USD_MGA")
    diesel = macro_map.get("FUEL_PUMP_CEILING_PRICE_MGA")
    cpi_food = macro_map.get("CPI_FOOD_CHG_12M")
    rice_import_val = macro_map.get("RICE_IMPORT_VALUE_CAF_MGA")
    rice_import_vol = macro_map.get("RICE_IMPORT_VOLUME_TONS")

    cif_cost, _ = calculate_import_unit_cost(rice_import_val, rice_import_vol)

    distinctness = audit_inflation_vs_market_price_distinctness(
        cpi_food_chg_12m=cpi_food,
        market_price_chg_12m=market_price_chg,
    )

    status = "qualified" if (fx is not None and diesel is not None) else "partial"

    return PilotEconomicContextOut(
        pilot_id="pilot_rice_ppn_2026",
        target_month=month_str,
        fx_usd_mga=fx,
        fuel_diesel_ceiling_mga=diesel,
        rice_import_unit_cost_mga_per_kg=cif_cost,
        cpi_food_chg_12m_pct=round(cpi_food * 100.0, 2) if cpi_food is not None else None,
        local_rice_market_price_mga_per_kg=market_price,
        local_rice_price_chg_12m_pct=round(market_price_chg * 100.0, 2)
        if market_price_chg is not None
        else None,
        distinctness_audit=distinctness,
        status=status,
    )
