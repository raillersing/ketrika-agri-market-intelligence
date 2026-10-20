"""Market coverage and pilot configuration router (SPECS §19, R2.4)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ketrika.api.csv_utils import export_csv_response
from ketrika.api.schemas import (
    ImpossibleCapabilityItem,
    MarketCoverageItem,
    PilotConfigResponse,
    PilotLocationItem,
    PilotProductItem,
    SeriesCoverageSummaryItem,
)
from ketrika.core.db import get_db
from ketrika.core.pilot import check_pilot_authenticity, load_pilot_config
from ketrika.gold.coverage import (
    compute_series_gaps_independent_sql,
    query_market_coverage_matrix,
)

router = APIRouter(prefix="/v1/market", tags=["market"])


@router.get("/coverage", response_model=list[MarketCoverageItem])
def get_market_coverage(
    product: str | None = Query(None, description="Product code (e.g. RICE_WHITE_LOCAL)"),
    location: str | None = Query(None, description="Location P-code (e.g. MDG11)"),
    actor_level: str | None = Query(None, description="Actor level (e.g. retail, wholesale)"),
    from_date: str | None = Query(None, alias="from", description="Start month (YYYY-MM-01)"),
    to_date: str | None = Query(None, alias="to", description="End month (YYYY-MM-01)"),
    limit: int = Query(100, ge=1, le=1000, description="Page limit (default 100, max 1000)"),
    offset: int = Query(0, ge=0, description="Page offset (default 0)"),
    format: str = Query("json", description="Output format (json or csv)"),
    session: Session = Depends(get_db),
) -> Any:
    """Retrieve market coverage matrix cells with pagination and CSV export (SPECS §19, R2.4, ADR-071)."""
    rows = query_market_coverage_matrix(
        session=session,
        product_code=product,
        location_pcode=location,
        actor_level=actor_level,
        from_month=from_date,
        to_month=to_date,
    )
    items = [
        MarketCoverageItem(
            product_code=r.product_code,
            product_name=r.product_name,
            location_pcode=r.location_pcode,
            location_name=r.location_name,
            admin_level=r.admin_level,
            actor_level=r.actor_level,
            month=r.month,
            n_sources=r.n_sources,
            n_families=r.n_families,
            sources=r.sources,
            source_families=r.source_families,
            n_obs=r.n_obs,
            imputed_share=r.imputed_share,
            has_observed=r.has_observed,
            observed_or_imputed=r.observed_or_imputed,
            min_price=r.min_price,
            max_price=r.max_price,
            median_price=r.median_price,
            age_days=r.age_days,
        )
        for r in rows
    ]

    actual_limit = int(limit.default) if hasattr(limit, "default") else int(limit)
    actual_offset = int(offset.default) if hasattr(offset, "default") else int(offset)
    actual_format = str(format.default) if hasattr(format, "default") else str(format)

    paged_items = items[actual_offset : actual_offset + actual_limit]

    if actual_format == "csv":
        data = [item.model_dump() for item in paged_items]
        return export_csv_response(data, filename="market_coverage.csv")

    return paged_items


@router.get("/coverage/gaps", response_model=SeriesCoverageSummaryItem)
def get_series_gaps(
    product: str = Query(..., description="Product code (e.g. RICE_WHITE_LOCAL)"),
    location: str = Query(..., description="Location P-code (e.g. MDG11)"),
    actor_level: str = Query("retail", description="Actor level (default: retail)"),
    session: Session = Depends(get_db),
) -> SeriesCoverageSummaryItem:
    """Compute independent calendar gaps and coverage ratio for a single series in SQL."""
    summary = compute_series_gaps_independent_sql(
        session=session,
        product_code=product,
        location_pcode=location,
        actor_level=actor_level,
    )
    return SeriesCoverageSummaryItem(
        product_code=summary.product_code,
        location_pcode=summary.location_pcode,
        location_name=summary.location_name,
        actor_level=summary.actor_level,
        admin_level=summary.admin_level,
        start_month=summary.start_month,
        end_month=summary.end_month,
        expected_months=summary.expected_months,
        observed_months=summary.observed_months,
        missing_months=summary.missing_months,
        coverage_ratio=summary.coverage_ratio,
        missing_months_list=summary.missing_months_list,
        source_families=summary.source_families,
        is_pilot_candidate=summary.is_pilot_candidate,
    )


@router.get("/pilot", response_model=PilotConfigResponse)
def get_pilot_configuration(
    session: Session = Depends(get_db),
) -> PilotConfigResponse:
    """Retrieve pilot configuration, economic justifications, impossible capabilities, and authenticity status."""
    config = load_pilot_config()
    auth_check = check_pilot_authenticity(
        session=session, pilot_config=config, raise_on_error=False
    )

    return PilotConfigResponse(
        pilot_id=config.pilot_id,
        version=config.version,
        title=config.title,
        description=config.description,
        products=[
            PilotProductItem(
                product_code=p.product_code,
                canonical_name_fr=p.canonical_name_fr,
                role=p.role,
                category=p.category,
                base_unit=p.base_unit,
                justification=p.justification,
            )
            for p in config.products
        ],
        locations=[
            PilotLocationItem(
                pcode=loc.pcode,
                name=loc.name,
                admin_level=loc.admin_level,
                economic_role=loc.economic_role,
                justification=loc.justification,
            )
            for loc in config.locations
        ],
        complementarity_rationale=config.complementarity_rationale,
        impossible_capabilities=[
            ImpossibleCapabilityItem(
                capability=c.capability,
                status=c.status,
                scope=c.scope,
                reason=c.reason,
            )
            for c in config.impossible_capabilities
        ],
        authenticity_status=auth_check.status,
        authentic_sources_found=auth_check.authentic_sources_found,
        authentic_observations_count=auth_check.authentic_observations_count,
        synthetic_observations_count=auth_check.synthetic_observations_count,
    )
