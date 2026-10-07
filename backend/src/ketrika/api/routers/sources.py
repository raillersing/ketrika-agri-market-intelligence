"""Sources DataOps router (SPECS §19)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.api.errors import NotFoundException
from ketrika.api.schemas import SourceHealthItem, SourceItem
from ketrika.core.db import get_db

router = APIRouter(prefix="/v1/sources", tags=["sources"])


@router.get("", response_model=list[SourceItem])
def list_sources(session: Session = Depends(get_db)) -> list[SourceItem]:
    """List all registered data sources and their priority / freshness SLAs and health."""
    sql = text(
        """
        SELECT
            s.source_id,
            COALESCE(s.spec->>'name', s.source_id) AS name,
            COALESCE(s.spec->>'priority', 'P1') AS priority,
            s.status,
            (s.spec->>'freshness_sla_days')::integer AS freshness_sla_days,
            sh.freshness_days,
            sh.is_stale,
            COALESCE(sh.latest_run_status, lr.latest_run_status) AS latest_run_status,
            COALESCE(sh.last_run_started_at, lr.started_at) AS last_run_started_at
        FROM meta.source s
        LEFT JOIN gold.source_health sh ON s.source_id = sh.source_id
        LEFT JOIN LATERAL (
            SELECT status AS latest_run_status, started_at
            FROM meta.ingestion_run ir
            WHERE ir.source_id = s.source_id
            ORDER BY ir.started_at DESC
            LIMIT 1
        ) lr ON true
        ORDER BY s.source_id;
        """
    )
    rows = session.execute(sql).fetchall()

    items: list[SourceItem] = []
    for r in rows:
        items.append(
            SourceItem(
                source_id=r[0],
                name=r[1],
                priority=r[2],
                status=r[3],
                freshness_sla_days=r[4],
                freshness_days=r[5],
                is_stale=r[6],
                latest_run_status=r[7],
                last_run_started_at=r[8],
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
