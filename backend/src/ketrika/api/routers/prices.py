"""Prices and observations router (SPECS §19)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.api.csv_utils import export_csv_response
from ketrika.api.errors import NotFoundException
from ketrika.api.gold_availability import require_gold_view
from ketrika.api.schemas import (
    ObservationDetailResponse,
    PriceLatestItem,
    PriceSeriesItem,
    ValueKind,
)
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_db
from ketrika.core.models.db import PriceObservation, SourceRecord
from ketrika.core.taxonomy import resolve_product

router = APIRouter(prefix="/v1", tags=["prices"])


@router.get("/prices")
def get_prices(
    product: str | None = Query(None, description="Product code (e.g. rice_milled) or UUID"),
    location: str | None = Query(None, description="Location P-code (e.g. MG11) or UUID"),
    actor_level: str | None = Query(
        None, description="Actor level (e.g. retail, wholesale, producer)"
    ),
    from_date: str | None = Query(None, alias="from", description="Start month (YYYY-MM-01)"),
    to_date: str | None = Query(None, alias="to", description="End month (YYYY-MM-01)"),
    granularity: str = Query("month", description="Aggregation granularity (default month)"),
    source: str | None = Query(None, description="Filter by source ID (uses gold.price_monthly)"),
    format: str = Query("json", description="Output format (json or csv)"),
    session: Session = Depends(get_db),
) -> Any:
    """Retrieve historical aggregated price series (SPECS §19)."""
    target_matview = "price_monthly" if source else "price_monthly_best"
    require_gold_view(session, target_matview)

    table_name = "gold.price_monthly" if source else "gold.price_monthly_best"
    source_col = "source_id" if source else "chosen_source_id"
    obs_imp_col = (
        "CASE WHEN has_observed THEN 'observed' ELSE 'imputed' END AS observed_or_imputed"
        if source
        else "observed_or_imputed"
    )

    query_sql = f"""
        SELECT
            product_code,
            location_pcode,
            location_name,
            actor_level,
            month::text AS month,
            median_price::float AS median_price,
            min_price::float AS min_price,
            max_price::float AS max_price,
            n_obs,
            imputed_share::float AS imputed_share,
            {obs_imp_col},
            {source_col} AS source_id
        FROM {table_name}
        WHERE 1=1
    """
    params: dict[str, Any] = {}

    if product:
        resolved = resolve_product(product)
        canonical = resolved[0] if resolved else None
        if canonical and canonical != product:
            query_sql += " AND (product_code = :product OR product_code = :canonical OR product_id::text = :product)"
            params["canonical"] = canonical
        else:
            query_sql += " AND (product_code = :product OR product_id::text = :product)"
        params["product"] = product
    if location:
        query_sql += " AND (location_pcode = :loc OR location_id::text = :loc)"
        params["loc"] = location
    if actor_level:
        query_sql += " AND actor_level = :actor"
        params["actor"] = actor_level
    if from_date:
        query_sql += " AND month >= CAST(:from_date AS date)"
        params["from_date"] = from_date
    if to_date:
        query_sql += " AND month <= CAST(:to_date AS date)"
        params["to_date"] = to_date
    if source:
        query_sql += " AND source_id = :source"
        params["source"] = source

    query_sql += " ORDER BY month ASC, product_code, location_pcode;"

    rows = session.execute(text(query_sql), params).fetchall()

    items: list[dict[str, Any]] = []
    for r in rows:
        val_kind = "imputed" if r[10] == "imputed" else "observed"
        item = {
            "product_code": r[0],
            "location_pcode": r[1],
            "location_name": r[2],
            "actor_level": r[3],
            "month": str(r[4]),
            "median_price": float(r[5]),
            "min_price": float(r[6]) if r[6] is not None else None,
            "max_price": float(r[7]) if r[7] is not None else None,
            "currency": "MGA",
            "unit": "kg",
            "value_kind": val_kind,
            "sources": [r[11]] if r[11] else [],
            "n_obs": int(r[8]),
            "imputed_share": float(r[9]) if r[9] is not None else 0.0,
        }
        items.append(item)

    if format.lower() == "csv":
        return export_csv_response(items, filename="prices.csv")

    return [PriceSeriesItem(**it) for it in items]


@router.get("/prices/latest", response_model=list[PriceLatestItem])
def get_prices_latest(
    product: str | None = Query(None, description="Product code or UUID"),
    level: int = Query(1, description="Admin level (1=Region, 2=District)"),
    session: Session = Depends(get_db),
) -> list[PriceLatestItem]:
    """Retrieve the latest monthly price for each geographic entity at given admin level (SPECS §19)."""
    require_gold_view(session, "price_monthly_best")

    params: dict[str, Any] = {"lvl": level}
    if product:
        resolved = resolve_product(product)
        canonical = resolved[0] if resolved else None
        if canonical and canonical != product:
            prod_filter = "AND (product_code = :prod OR product_code = :canonical OR product_id::text = :prod)"
            params["canonical"] = canonical
        else:
            prod_filter = "AND (product_code = :prod OR product_id::text = :prod)"
        params["prod"] = product
    else:
        prod_filter = ""
    query_sql = f"""
        WITH latest_month_per_loc AS (
            SELECT
                product_code,
                location_pcode,
                location_name,
                month::text AS month,
                median_price::float AS median_price,
                observed_or_imputed,
                chosen_source_id,
                ROW_NUMBER() OVER (
                    PARTITION BY product_code, location_pcode
                    ORDER BY month DESC
                ) AS rn
            FROM gold.price_monthly_best
            WHERE admin_level = :lvl
              {prod_filter}
        )
        SELECT
            product_code,
            location_pcode,
            location_name,
            month,
            median_price,
            observed_or_imputed,
            chosen_source_id
        FROM latest_month_per_loc
        WHERE rn = 1
        ORDER BY location_pcode;
    """
    rows = session.execute(text(query_sql), params).fetchall()

    results: list[PriceLatestItem] = []
    for r in rows:
        val_kind: ValueKind = "imputed" if r[5] == "imputed" else "observed"
        results.append(
            PriceLatestItem(
                product_code=r[0],
                location_pcode=r[1],
                location_name=r[2],
                month=r[3],
                median_price=float(r[4]),
                currency="MGA",
                unit="kg",
                value_kind=val_kind,
                sources=[r[6]] if r[6] else [],
            )
        )
    return results


@router.get("/observations/{observation_id}", response_model=ObservationDetailResponse)
def get_observation_detail(
    observation_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> ObservationDetailResponse:
    """Retrieve complete observation provenance: raw values, evidence, extraction method,

    and a temporary presigned 15-minute Bronze object download URL (SPECS §19).
    """
    obs = session.get(PriceObservation, observation_id)
    if not obs:
        raise NotFoundException(f"Observation {observation_id} not found")

    srec = session.get(SourceRecord, obs.source_record_id)
    if not srec:
        raise NotFoundException(f"SourceRecord for observation {observation_id} not found")

    # Generate presigned URL valid for 15 minutes (900 seconds)
    bronze_store = BronzeStore()
    presigned_url = bronze_store.get_presigned_url(srec.object_key, expires_in=900)

    val_kind_obs: ValueKind = "imputed" if obs.observed_or_imputed == "imputed" else "observed"

    return ObservationDetailResponse(
        observation_id=obs.observation_id,
        source_id=srec.source_id,
        source_url=srec.source_url,
        parser_version=srec.parser_version or "1.0.0",
        price_raw=obs.price_raw,
        price_value=float(obs.price_value) if obs.price_value is not None else None,
        price_mga_per_base=float(obs.price_mga_per_base)
        if obs.price_mga_per_base is not None
        else None,
        currency_raw=obs.currency_raw,
        unit_raw=obs.unit_raw,
        base_unit=obs.base_unit or "kg",
        actor_level=obs.actor_level,
        period_start=str(obs.period_start),
        period_end=str(obs.period_end),
        observed_or_imputed=obs.observed_or_imputed,
        value_kind=val_kind_obs,
        extraction_method=obs.extraction_method,
        confidence=float(obs.confidence),
        evidence=obs.evidence or {},
        bronze_presigned_url=presigned_url,
    )
