"""Sources DataOps router (SPECS §19)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ketrika.api.auth import get_current_user, require_admin
from ketrika.api.errors import NotFoundException, ProblemDetailException
from ketrika.api.schemas import (
    CollectionInput,
    SourceHealthItem,
    SourceItem,
    SourceRefreshResponse,
    SourceRunItem,
)
from ketrika.connectors import manual_collection
from ketrika.connectors.manual_collection import RECOMPUTE_VIEWS
from ketrika.core.db import get_db
from ketrika.core.diagnostics import classify_run_diagnostic
from ketrika.gold.refresh import refresh_gold_views

router = APIRouter(prefix="/v1/sources", tags=["sources"])


def _health_cache_populated(session: Session) -> bool:
    """Inspect state, not a count or fabricated readiness metric."""
    return (
        session.scalar(
            text(
                "SELECT ispopulated FROM pg_matviews "
                "WHERE schemaname='gold' AND matviewname='source_health'"
            )
        )
        is True
    )


@router.get("", response_model=list[SourceItem])
def list_sources(session: Session = Depends(get_db)) -> list[SourceItem]:
    """List all registered data sources and their priority / freshness SLAs and health."""
    health_join = (
        "LEFT JOIN gold.source_health sh ON s.source_id = sh.source_id"
        if _health_cache_populated(session)
        else (
            "LEFT JOIN (SELECT NULL::integer AS freshness_days, "
            "NULL::boolean AS is_stale, NULL::integer AS open_review_items, "
            "NULL::integer AS n_records_30d) sh ON FALSE"
        )
    )
    # Only fixed code-owned SQL fragments; no source or request content.
    sql = text(
        f"""
        SELECT
            s.source_id,
            COALESCE(s.spec->>'name', s.source_id) AS name,
            COALESCE(s.spec->>'priority', 'P1') AS priority,
            s.status,
            (s.spec->>'freshness_sla_days')::integer AS freshness_sla_days,
            sh.freshness_days,
            sh.is_stale,
            lr.latest_run_status AS latest_run_status,
            lr.started_at AS last_run_started_at,
            lr.n_records AS latest_run_records,
            lr.n_fetched AS latest_run_fetched,
            lr.error AS latest_run_error,
            COALESCE(sh.open_review_items, 0)::integer AS open_review_items,
            COALESCE(sh.n_records_30d, 0)::integer AS n_records_30d
        FROM meta.source s
        {health_join}
        LEFT JOIN LATERAL (
            SELECT status AS latest_run_status, started_at, n_records, n_fetched, error
            FROM meta.ingestion_run ir
            WHERE ir.source_id = s.source_id
            ORDER BY ir.started_at DESC, ir.run_id DESC
            LIMIT 1
        ) lr ON true
        ORDER BY s.source_id;
        """
    )
    rows = session.execute(sql).fetchall()

    items: list[SourceItem] = []
    for r in rows:
        diag = classify_run_diagnostic(
            status=r[7],
            n_records=r[9],
            n_fetched=r[10],
            error=r[11],
            has_published_gold=(r[13] > 0 and r[6] is False),
            open_review_items=r[12],
        )
        items.append(
            SourceItem(
                source_id=r[0],
                name=r[1],
                priority=r[2],
                status=r[3],
                freshness_sla_days=r[4],
                freshness_days=r[5],
                is_stale=r[6] if r[5] is not None else None,
                latest_run_status=r[7],
                last_run_started_at=r[8],
                diagnostic_status=diag.diagnostic_status,
                diagnostic_code=diag.diagnostic_code,
                diagnostic_message=diag.diagnostic_message,
            )
        )
    return items


@router.get("/{source_id}/health", response_model=SourceHealthItem)
def get_source_health(
    source_id: str,
    session: Session = Depends(get_db),
) -> SourceHealthItem:
    """Retrieve DataOps health metrics for a specific source from gold.source_health (SPECS §19)."""
    if not _health_cache_populated(session):
        raise ProblemDetailException(
            status_code=503,
            title="DataOps health not published",
            detail="The source health cache has not been published; no health metrics are available.",
        )
    sql = text(
        """
        SELECT
            sh.source_id,
            sh.source_name,
            sh.priority,
            sh.freshness_sla_days,
            sh.freshness_days,
            sh.is_stale,
            lr.latest_run_status,
            lr.started_at AS last_run_started_at,
            sh.n_records_30d,
            sh.parse_success_rate::float,
            sh.open_review_items,
            lr.n_records AS latest_run_records,
            lr.n_fetched AS latest_run_fetched,
            lr.error AS latest_run_error
        FROM gold.source_health sh
        LEFT JOIN LATERAL (
            SELECT status AS latest_run_status, started_at, n_records, n_fetched, error
            FROM meta.ingestion_run ir
            WHERE ir.source_id = sh.source_id
            ORDER BY ir.started_at DESC, ir.run_id DESC
            LIMIT 1
        ) lr ON true
        WHERE sh.source_id = :sid;
        """
    )
    row = session.execute(sql, {"sid": source_id}).fetchone()
    if not row:
        raise NotFoundException(f"Source {source_id} health not found")

    diag = classify_run_diagnostic(
        status=row[6],
        n_records=row[11],
        n_fetched=row[12],
        error=row[13],
        has_published_gold=(int(row[8]) > 0 and not bool(row[5])),
        open_review_items=int(row[10]),
    )

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
        diagnostic_status=diag.diagnostic_status,
        diagnostic_code=diag.diagnostic_code,
        diagnostic_message=diag.diagnostic_message,
    )


@router.get("/runs", response_model=list[SourceRunItem], dependencies=[Depends(get_current_user)])
def list_recent_runs(
    limit: int = 20,
    session: Session = Depends(get_db),
) -> list[SourceRunItem]:
    """Retrieve recent data sync and ingestion runs for user-friendly monitoring."""
    bounded_limit = max(1, min(limit, 50))
    sql = text(
        """
        SELECT
            ir.run_id::text,
            ir.source_id,
            COALESCE(s.spec->>'name', ir.source_id) AS source_name,
            ir.status,
            ir.started_at,
            ir.finished_at,
            ROUND(EXTRACT(EPOCH FROM (ir.finished_at - ir.started_at))::numeric, 2) AS duration_seconds,
            ir.n_records,
            ir.n_fetched,
            ir.error
        FROM meta.ingestion_run ir
        LEFT JOIN meta.source s ON ir.source_id = s.source_id
        ORDER BY ir.started_at DESC, ir.run_id DESC
        LIMIT :lim;
        """
    )
    rows = session.execute(sql, {"lim": bounded_limit}).fetchall()
    items: list[SourceRunItem] = []
    for r in rows:
        diag = classify_run_diagnostic(
            status=r[3],
            n_records=int(r[7]) if r[7] is not None else None,
            n_fetched=int(r[8]) if r[8] is not None else None,
            error=r[9],
        )
        items.append(
            SourceRunItem(
                run_id=r[0],
                source_id=r[1],
                source_name=r[2],
                status=r[3],
                started_at=r[4],
                finished_at=r[5],
                duration_seconds=float(r[6]) if r[6] is not None else None,
                n_records=int(r[7]) if r[7] is not None else None,
                n_fetched=int(r[8]) if r[8] is not None else None,
                error=diag.diagnostic_code if r[9] else None,
                diagnostic_status=diag.diagnostic_status,
                diagnostic_code=diag.diagnostic_code,
                diagnostic_message=diag.diagnostic_message,
            )
        )
    return items


@router.get("/collection-options", dependencies=[Depends(get_current_user)])
def collection_options() -> list[str]:
    return manual_collection.eligible_sources()


@router.get("/collections", dependencies=[Depends(get_current_user)])
def collection_history() -> list[dict[str, Any]]:
    return manual_collection.recent_collections()


@router.get("/collections/{request_id}", dependencies=[Depends(get_current_user)])
def collection_receipt(request_id: UUID) -> dict[str, Any]:
    try:
        return manual_collection.read_collection(request_id)
    except manual_collection.CollectionError as error:
        raise ProblemDetailException(error.status, "Collecte indisponible", str(error)) from None


@router.post("/collect", dependencies=[Depends(require_admin)])
def collect_sources(body: CollectionInput) -> dict[str, Any]:
    try:
        return manual_collection.collect(body.request_id, body.source_id)
    except manual_collection.CollectionError as error:
        raise ProblemDetailException(error.status, "Collecte indisponible", str(error)) from None
    except SQLAlchemyError:
        raise ProblemDetailException(
            503, "Collecte indisponible", "collection_storage_unavailable"
        ) from None


def _recompute(session: Session) -> SourceRefreshResponse:
    """One transaction, guarded publication, no synthetic ingestion history."""
    try:
        acquired = session.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended('sources-gold-recompute', 0))")
        )
        if acquired is not True:
            raise ProblemDetailException(409, "Recalcul en cours", "Un recalcul est déjà en cours.")
        result = refresh_gold_views(session, views=RECOMPUTE_VIEWS)
        views = result["views_refreshed"]
        session.commit()
    except ProblemDetailException:
        session.rollback()
        raise
    except (ValueError, SQLAlchemyError):
        session.rollback()
        raise ProblemDetailException(
            503,
            "Recalcul non publié",
            "Le recalcul a été refusé ou interrompu. Aucune collecte ni fraîcheur nouvelle n'est confirmée.",
        ) from None
    return SourceRefreshResponse(
        success=True,
        message="Indicateurs partagés recalculés à partir des données existantes. Aucune nouvelle collecte.",
        views_refreshed=views,
        refreshed_at=datetime.now(UTC),
    )


@router.post(
    "/refresh", response_model=SourceRefreshResponse, dependencies=[Depends(require_admin)]
)
def refresh_all_market_data(session: Session = Depends(get_db)) -> SourceRefreshResponse:
    return _recompute(session)


@router.post(
    "/{source_id}/refresh",
    response_model=SourceRefreshResponse,
    dependencies=[Depends(require_admin)],
)
def refresh_single_source(
    source_id: str, session: Session = Depends(get_db)
) -> SourceRefreshResponse:
    row = session.execute(
        text("SELECT status FROM meta.source WHERE source_id = :sid"), {"sid": source_id}
    ).fetchone()
    if row is None:
        raise NotFoundException("Source introuvable dans le catalogue.")
    if row[0] != "active":
        raise ProblemDetailException(409, "Source indisponible", "Cette source n'est pas active.")
    return _recompute(session)
