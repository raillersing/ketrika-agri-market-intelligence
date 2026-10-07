"""Sources DataOps router (SPECS §19)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ketrika.api.errors import NotFoundException
from ketrika.api.schemas import SourceHealthItem, SourceItem
from ketrika.core.db import get_db
from ketrika.core.models.db import Source

router = APIRouter(prefix="/v1/sources", tags=["sources"])


@router.get("", response_model=list[SourceItem])
def list_sources(session: Session = Depends(get_db)) -> list[SourceItem]:
    """List all registered data sources and their priority / freshness SLAs."""
    stmt = select(Source).order_by(Source.source_id)
    sources = list(session.execute(stmt).scalars().all())

    items: list[SourceItem] = []
    for s in sources:
        spec = s.spec or {}
        items.append(
            SourceItem(
                source_id=s.source_id,
                name=spec.get("name", s.source_id),
                priority=spec.get("priority", "P1"),
                status=s.status,
                freshness_sla_days=spec.get("freshness_sla_days"),
            )
        )
    return items


@router.get("/{source_id}/health", response_model=SourceHealthItem)
def get_source_health(
    source_id: str,
    session: Session = Depends(get_db),
) -> SourceHealthItem:
    """Retrieve DataOps health metrics for a specific source from gold.source_health (SPECS §19)."""
    sql = text(
        """
        SELECT
            source_id,
            source_name,
            priority,
            freshness_sla_days,
            freshness_days,
            is_stale,
            latest_run_status,
            last_run_started_at,
            n_records_30d,
            parse_success_rate::float,
            open_review_items
        FROM gold.source_health
        WHERE source_id = :sid;
        """
    )
    row = session.execute(sql, {"sid": source_id}).fetchone()
    if not row:
        raise NotFoundException(f"Source {source_id} health not found")

    return SourceHealthItem(
        source_id=row[0],
        source_name=row[1],
        priority=row[2],
        freshness_sla_days=row[3],
        freshness_days=row[4],
        is_stale=bool(row[5]),
        latest_run_status=row[6],
        last_run_started_at=row[7],
        n_records_30d=int(row[8]),
        parse_success_rate=float(row[9]),
        open_review_items=int(row[10]),
    )
