"""Market coverage measurement and series gap analysis (SPECS §15, §19, MARKET_INTELLIGENCE_EXECUTION_PLAN R2.4)."""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.core.pilot import PilotConfig, load_pilot_config
from ketrika.gold.compatibility import is_gold_view_populated


class MarketCoverageRow(BaseModel):
    """Row from gold.market_coverage representing product x location x actor x month cell."""

    product_id: UUID | None = None
    product_code: str
    product_name: str
    location_id: UUID | None = None
    location_pcode: str | None = None
    location_name: str | None = None
    admin_level: int | None = None
    actor_level: str
    month: str
    n_sources: int
    n_families: int
    sources: str
    source_families: str
    n_obs: int
    imputed_share: float
    has_observed: bool
    observed_or_imputed: str
    min_price: float | None = None
    max_price: float | None = None
    median_price: float | None = None
    age_days: int


class SeriesCoverageSummary(BaseModel):
    """Independent coverage and gap analysis for a single series (product x location x actor)."""

    product_code: str
    location_pcode: str
    location_name: str | None = None
    actor_level: str
    admin_level: int | None = None
    start_month: str | None = None
    end_month: str | None = None
    expected_months: int = 0
    observed_months: int = 0
    missing_months: int = 0
    coverage_ratio: float = 0.0
    missing_months_list: list[str] = Field(default_factory=list)
    source_families: list[str] = Field(default_factory=list)
    is_pilot_candidate: bool = False


def add_calendar_month(d: datetime.date) -> datetime.date:
    """Increment date by exactly one calendar month, anchored to the 1st."""
    if d.month == 12:
        return datetime.date(d.year + 1, 1, 1)
    return datetime.date(d.year, d.month + 1, 1)


def calculate_missing_months(
    observed_months: Sequence[datetime.date | str],
    start_month: datetime.date | str | None = None,
    end_month: datetime.date | str | None = None,
) -> tuple[int, list[datetime.date], float]:
    """Calculate missing months independently over a continuous calendar grid.

    Args:
        observed_months: Sequence of dates representing observed months.
        start_month: Optional range start. If None, min(observed_months) is used.
        end_month: Optional range end. If None, max(observed_months) is used.

    Returns:
        tuple of (missing_count, missing_dates_list, coverage_ratio).
    """
    parsed_observed: set[datetime.date] = set()
    for m in observed_months:
        if isinstance(m, str):
            parsed_observed.add(datetime.date.fromisoformat(m[:10]))
        elif isinstance(m, datetime.date):
            parsed_observed.add(datetime.date(m.year, m.month, 1))

    if not parsed_observed and (start_month is None or end_month is None):
        return 0, [], 0.0

    start_d: datetime.date
    if start_month is not None:
        start_d = (
            datetime.date.fromisoformat(start_month[:10])
            if isinstance(start_month, str)
            else datetime.date(start_month.year, start_month.month, 1)
        )
    else:
        start_d = min(parsed_observed)

    end_d: datetime.date
    if end_month is not None:
        end_d = (
            datetime.date.fromisoformat(end_month[:10])
            if isinstance(end_month, str)
            else datetime.date(end_month.year, end_month.month, 1)
        )
    else:
        end_d = max(parsed_observed)

    if start_d > end_d:
        return 0, [], 0.0

    # Build continuous calendar grid of 1st-of-month dates
    curr = start_d
    calendar_grid: list[datetime.date] = []
    while curr <= end_d:
        calendar_grid.append(curr)
        curr = add_calendar_month(curr)

    missing: list[datetime.date] = [d for d in calendar_grid if d not in parsed_observed]
    expected_count = len(calendar_grid)
    observed_in_range_count = expected_count - len(missing)

    ratio = observed_in_range_count / expected_count if expected_count > 0 else 0.0
    return len(missing), missing, round(ratio, 4)


def query_market_coverage_matrix(
    session: Session,
    product_code: str | None = None,
    location_pcode: str | None = None,
    actor_level: str | None = None,
    from_month: str | None = None,
    to_month: str | None = None,
) -> list[MarketCoverageRow]:
    """Retrieve market coverage cells from gold.market_coverage with optional filters."""
    if not is_gold_view_populated(session, "market_coverage"):
        raise ValueError("gold_not_published")

    sql = """
        SELECT
            product_id,
            product_code,
            product_name,
            location_id,
            location_pcode,
            location_name,
            admin_level,
            actor_level,
            month::text AS month,
            n_sources,
            n_families,
            sources,
            source_families,
            n_obs,
            imputed_share::float,
            has_observed,
            observed_or_imputed,
            min_price::float,
            max_price::float,
            median_price::float,
            age_days
        FROM gold.market_coverage
        WHERE 1=1
    """
    params: dict[str, Any] = {}
    if product_code:
        sql += " AND product_code = :product_code"
        params["product_code"] = product_code
    if location_pcode:
        sql += " AND location_pcode = :location_pcode"
        params["location_pcode"] = location_pcode
    if actor_level:
        sql += " AND actor_level = :actor_level"
        params["actor_level"] = actor_level
    if from_month:
        sql += " AND month >= :from_month::date"
        params["from_month"] = from_month
    if to_month:
        sql += " AND month <= :to_month::date"
        params["to_month"] = to_month

    sql += " ORDER BY month DESC, product_code, location_pcode, actor_level;"

    rows = session.execute(text(sql), params).fetchall()
    results: list[MarketCoverageRow] = []
    for r in rows:
        results.append(
            MarketCoverageRow(
                product_id=r[0],
                product_code=r[1],
                product_name=r[2],
                location_id=r[3],
                location_pcode=r[4],
                location_name=r[5],
                admin_level=r[6],
                actor_level=r[7],
                month=r[8],
                n_sources=r[9],
                n_families=r[10],
                sources=r[11],
                source_families=r[12],
                n_obs=r[13],
                imputed_share=r[14],
                has_observed=r[15],
                observed_or_imputed=r[16],
                min_price=r[17],
                max_price=r[18],
                median_price=r[19],
                age_days=r[20],
            )
        )
    return results


def compute_series_gaps_independent_sql(
    session: Session,
    product_code: str,
    location_pcode: str,
    actor_level: str = "retail",
) -> SeriesCoverageSummary:
    """Compute independent calendar gaps and coverage ratio in SQL using generate_series.

    Guarantee: independent gap computation without flattery or cherry-picking.
    """
    if not is_gold_view_populated(session, "market_coverage"):
        raise ValueError("gold_not_published")

    query = text(
        """
        WITH series_bounds AS (
            SELECT
                min(month) AS min_m,
                max(month) AS max_m,
                product_name,
                location_name,
                admin_level
            FROM gold.market_coverage
            WHERE product_code = :product_code
              AND location_pcode = :location_pcode
              AND actor_level = :actor_level
            GROUP BY product_name, location_name, admin_level
        ),
        grid AS (
            SELECT
                generate_series(sb.min_m, sb.max_m, INTERVAL '1 month')::date AS expected_month,
                sb.product_name,
                sb.location_name,
                sb.admin_level
            FROM series_bounds sb
        ),
        gaps AS (
            SELECT
                g.expected_month,
                g.product_name,
                g.location_name,
                g.admin_level,
                mc.month AS observed_month,
                mc.source_families
            FROM grid g
            LEFT JOIN gold.market_coverage mc ON (
                mc.product_code = :product_code
                AND mc.location_pcode = :location_pcode
                AND mc.actor_level = :actor_level
                AND mc.month = g.expected_month
            )
        )
        SELECT
            min(expected_month)::text AS start_month,
            max(expected_month)::text AS end_month,
            count(*)::integer AS total_expected,
            count(observed_month)::integer AS total_observed,
            (count(*) - count(observed_month))::integer AS missing_count,
            round((count(observed_month)::numeric / NULLIF(count(*), 0)), 4)::float AS coverage_ratio,
            array_agg(expected_month::text ORDER BY expected_month) FILTER (WHERE observed_month IS NULL) AS missing_list,
            string_agg(DISTINCT source_families, ', ') AS families,
            max(product_name) AS product_name,
            max(location_name) AS location_name,
            max(admin_level) AS admin_level
        FROM gaps;
        """
    )

    res = session.execute(
        query,
        {
            "product_code": product_code,
            "location_pcode": location_pcode,
            "actor_level": actor_level,
        },
    ).fetchone()

    if not res or res[0] is None:
        return SeriesCoverageSummary(
            product_code=product_code,
            location_pcode=location_pcode,
            actor_level=actor_level,
            expected_months=0,
            observed_months=0,
            missing_months=0,
            coverage_ratio=0.0,
            missing_months_list=[],
            source_families=[],
            is_pilot_candidate=False,
        )

    missing_list = [str(x) for x in res[6]] if res[6] else []
    families_str = str(res[7]) if res[7] else ""
    families = [f.strip() for f in families_str.split(",") if f.strip()]

    cov_ratio = float(res[5]) if res[5] is not None else 0.0

    return SeriesCoverageSummary(
        product_code=product_code,
        location_pcode=location_pcode,
        location_name=res[9],
        actor_level=actor_level,
        admin_level=res[10],
        start_month=res[0],
        end_month=res[1],
        expected_months=int(res[2]),
        observed_months=int(res[3]),
        missing_months=int(res[4]),
        coverage_ratio=cov_ratio,
        missing_months_list=missing_list,
        source_families=sorted(set(families)),
        is_pilot_candidate=(cov_ratio >= 0.50),
    )


def audit_pilot_market_coverage(
    session: Session,
    pilot_config: PilotConfig | None = None,
) -> dict[str, Any]:
    """Execute complete coverage audit of the pilot configuration."""
    config = pilot_config or load_pilot_config()

    series_summaries: list[SeriesCoverageSummary] = []
    pilot_products = [p.product_code for p in config.products]
    pilot_locations = [loc.pcode for loc in config.locations]

    for p_code in pilot_products:
        for loc_code in pilot_locations:
            summary = compute_series_gaps_independent_sql(
                session=session,
                product_code=p_code,
                location_pcode=loc_code,
                actor_level="retail",
            )
            series_summaries.append(summary)

    total_expected = sum(s.expected_months for s in series_summaries)
    total_observed = sum(s.observed_months for s in series_summaries)
    total_missing = sum(s.missing_months for s in series_summaries)
    overall_ratio = round(total_observed / total_expected, 4) if total_expected > 0 else 0.0

    return {
        "pilot_id": config.pilot_id,
        "title": config.title,
        "total_series_evaluated": len(series_summaries),
        "total_expected_cell_months": total_expected,
        "total_observed_cell_months": total_observed,
        "total_missing_cell_months": total_missing,
        "overall_coverage_ratio": overall_ratio,
        "series": [s.model_dump() for s in series_summaries],
        "impossible_capabilities": [c.model_dump() for c in config.impossible_capabilities],
    }
