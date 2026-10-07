"""Series extraction and eligibility filtering for price forecasting (SPECS §17)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PricePoint:
    month: date
    price: float


@dataclass
class EligibleSeries:
    series_key: str
    product_id: uuid.UUID
    product_code: str
    product_name: str
    location_id: uuid.UUID
    location_pcode: str
    location_name: str
    actor_level: str
    points: list[PricePoint]


def extract_eligible_series(
    session: Session,
    data_cutoff: date,
    min_points: int = 6,
) -> list[EligibleSeries]:
    """Extract price series from gold.price_monthly_best up to data_cutoff.

    Enforces temporal integrity: strictly filters month <= data_cutoff to prevent data leakage.
    """
    query = text(
        """
        SELECT
            product_id,
            product_code,
            product_name,
            location_id,
            location_pcode,
            location_name,
            actor_level,
            month,
            median_price
        FROM gold.price_monthly_best
        WHERE month <= :cutoff
          AND median_price IS NOT NULL
          AND median_price > 0
        ORDER BY product_code, location_pcode, actor_level, month ASC;
        """
    )
    rows = session.execute(query, {"cutoff": data_cutoff}).fetchall()

    grouped: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = f"{r.product_code}|{r.location_pcode}|{r.actor_level}"
        if key not in grouped:
            grouped[key] = {
                "series_key": key,
                "product_id": r.product_id,
                "product_code": r.product_code,
                "product_name": r.product_name,
                "location_id": r.location_id,
                "location_pcode": r.location_pcode,
                "location_name": r.location_name,
                "actor_level": r.actor_level,
                "points": [],
            }
        grouped[key]["points"].append(PricePoint(month=r.month, price=float(r.median_price)))

    eligible: list[EligibleSeries] = []
    for g in grouped.values():
        if len(g["points"]) >= min_points:
            eligible.append(
                EligibleSeries(
                    series_key=g["series_key"],
                    product_id=g["product_id"],
                    product_code=g["product_code"],
                    product_name=g["product_name"],
                    location_id=g["location_id"],
                    location_pcode=g["location_pcode"],
                    location_name=g["location_name"],
                    actor_level=g["actor_level"],
                    points=g["points"],
                )
            )

    logger.info(
        "eligible_series_extracted",
        total_series_found=len(grouped),
        eligible_series_count=len(eligible),
        cutoff=data_cutoff.isoformat(),
    )
    return eligible
