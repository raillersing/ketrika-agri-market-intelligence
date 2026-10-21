"""Explicit collection owner, SQL receipts and crash detection; no automatic retry."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text

from ketrika.connectors.base import RunContext
from ketrika.connectors.durable_phases import execute_durable_bronze, execute_durable_silver
from ketrika.connectors.registry import list_registered_connectors
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.http import PoliteHttpClient
from ketrika.core.policy import PolicyEngine
from ketrika.core.registry import get_source
from ketrika.gold.refresh import refresh_gold_views

LOCK_SQL = "SELECT pg_try_advisory_xact_lock(hashtextextended('sources-gold-recompute',0))"
RECOMPUTE_VIEWS = [
    "price_obs_current",
    "price_monthly",
    "price_monthly_best",
    "price_changes",
    "stock_latest",
    "trade_monthly",
    "import_dependency",
    "weather_monthly",
    "cpi_food",
    "market_health",
    "source_health",
    "forecast_latest",
    "market_coverage",
]


class CollectionError(ValueError):
    def __init__(self, code: str, status: int = 409) -> None:
        self.status = status
        super().__init__(code)


def eligible_sources() -> list[str]:
    """Intersection of code-owned registry and current SQL policy, no arbitrary URL."""
    with get_session() as session:
        enabled = set(
            session.scalars(
                text("SELECT source_id FROM meta.source WHERE status IN ('active','degraded')")
            )
        )
    result = []
    for sid in sorted(list_registered_connectors()):
        if sid.startswith(("dummy_", "fixture_")) or sid not in enabled:
            continue
        spec = get_source(sid)
        if spec.status in ("active", "degraded") and spec.crawl_permission in (
            "public_open_data",
            "robots_tos_compliant",
        ):
            result.append(sid)
    return result


def _read(request_id: UUID) -> dict[str, Any] | None:
    with get_session() as session:
        row = (
            session.execute(
                text("SELECT * FROM meta.collection_request WHERE request_id=:id"),
                {"id": request_id},
            )
            .mappings()
            .one_or_none()
        )
        return dict(row) if row else None


def reconcile_interrupted() -> None:
    # The executing owner's connection holds this lock BEFORE its receipt becomes visible.
    # A free lock therefore proves there is no such owner, not that no wire emission occurred.
    with get_session() as session:
        if session.scalar(text(LOCK_SQL)):
            session.execute(
                text("""
                UPDATE meta.collection_request SET status='interrupted',
                  stage='interrupted', finished_at=now()
                WHERE status='running'
            """)
            )


def read_collection(request_id: UUID) -> dict[str, Any]:
    reconcile_interrupted()
    receipt = _read(request_id)
    if receipt is None:
        raise CollectionError("collection_not_found", 404)
    return receipt


def recent_collections() -> list[dict[str, Any]]:
    reconcile_interrupted()
    with get_session() as session:
        return [
            dict(row)
            for row in session.execute(
                text(
                    "SELECT * FROM meta.collection_request ORDER BY started_at DESC, request_id DESC LIMIT 10"
                )
            ).mappings()
        ]


def _progress(
    request_id: UUID,
    stage: str,
    outcomes: list[dict[str, Any]],
    *,
    status: str = "running",
    publication: str = "not_started",
) -> None:
    with get_session() as session:
        session.execute(
            text("""
            UPDATE meta.collection_request SET stage=:stage, status=:status,
              outcomes=CAST(:outcomes AS jsonb), publication=:publication,
              finished_at=CASE WHEN :status='running' THEN NULL ELSE now() END
            WHERE request_id=:id
        """),
            {
                "id": request_id,
                "stage": stage,
                "status": status,
                "outcomes": json.dumps(outcomes),
                "publication": publication,
            },
        )


def _collect_source(sid: str, request_id: UUID, outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Reuse the same real durable phase owners as Dagster; never synthesize a run."""
    outcome: dict[str, Any] = {"source_id": sid, "status": "failed", "run_id": None}
    ctx = RunContext(
        source_id=sid,
        metadata={"dagster_run_id": str(request_id)},
        logger=logging.getLogger(__name__),
        bronze_store=BronzeStore(),
        policy_engine=PolicyEngine(),
    )
    try:
        if sid not in eligible_sources():
            outcome["status"] = "blocked"
            return outcome
        connector = list_registered_connectors()[sid]()
        if sid == "wb_rtfp_mdg":
            from ketrika.connectors.manual_wb import ManualWbConnector

            connector = ManualWbConnector()
            outcome["scope"] = "bounded_15_modeled_rice_estimates_not_full_market"
        _progress(request_id, f"bronze:{sid}", outcomes)
        with PoliteHttpClient(policy_engine=ctx.policy_engine) as http:
            ctx.http_client = http
            batch = execute_durable_bronze(connector, ctx)
            outcome["run_id"] = str(batch.ingestion_run_id)
            _progress(request_id, f"silver:{sid}", [*outcomes, {**outcome, "status": "running"}])
            execute_durable_silver(connector, ctx, batch)
        with get_session() as session:
            row = (
                session.execute(
                    text("""
                SELECT status,n_fetched,n_new_artifacts,n_records,n_rejected
                FROM meta.ingestion_run WHERE run_id=:id AND source_id=:sid
            """),
                    {"id": batch.ingestion_run_id, "sid": sid},
                )
                .mappings()
                .one()
            )
            outcome.update(dict(row))
        # Durable Silver must actually have closed its run successfully.
        if outcome["status"] != "success":
            outcome["status"] = "failed"
    except Exception:
        # Untrusted source text, URLs, credentials and SQL errors never enter UI receipts.
        outcome["status"] = "failed"
        outcome["error"] = "collection_source_failed"
        if ctx.run_id is not None:
            outcome["run_id"] = str(ctx.run_id)
    return outcome


def collect(request_id: UUID, selection: str | None) -> dict[str, Any]:
    existing = _read(request_id)
    if existing is not None:
        if existing["selection"] != selection:
            raise CollectionError("collection_idempotency_conflict")
        return read_collection(request_id)
    # A separate, open transaction owns the lock throughout all phase commits.
    with get_session() as owner:
        if not owner.scalar(text(LOCK_SQL)):
            raise CollectionError("collection_busy")
        existing = _read(request_id)
        if existing is not None:
            if existing["selection"] != selection:
                raise CollectionError("collection_idempotency_conflict")
            return existing
        with get_session() as session:
            session.execute(
                text("""
                UPDATE meta.collection_request SET status='interrupted', stage='interrupted',
                    finished_at=now() WHERE status='running'
            """)
            )
        sources = eligible_sources()
        if selection is not None:
            if selection not in sources:
                raise CollectionError("collection_source_not_eligible")
            sources = [selection]
        if not sources:
            raise CollectionError("collection_no_eligible_sources")
        with get_session() as session:
            session.execute(
                text("""
                INSERT INTO meta.collection_request(request_id,selection,status,stage,source_ids)
                VALUES (:id,:selection,'running','starting',CAST(:sources AS jsonb))
            """),
                {"id": request_id, "selection": selection, "sources": json.dumps(sources)},
            )
        outcomes: list[dict[str, Any]] = []
        try:
            for sid in sources:
                outcome = _collect_source(sid, request_id, outcomes)
                outcomes.append(outcome)
                _progress(request_id, "source_finished", outcomes)
            successes = sum(item["status"] == "success" for item in outcomes)
            publication = "not_started"
            if successes:
                _progress(request_id, "gold", outcomes, publication="running")
                try:
                    with get_session() as session:
                        refresh_gold_views(session, views=RECOMPUTE_VIEWS)
                    publication = "succeeded"
                except Exception:
                    publication = "failed"
            status = (
                "succeeded"
                if successes == len(sources) and publication == "succeeded"
                else "partial"
                if successes
                else "failed"
            )
            _progress(request_id, "finished", outcomes, status=status, publication=publication)
        except Exception:
            _progress(request_id, "interrupted", outcomes, status="interrupted")
        result = _read(request_id)
        if result is None:
            raise CollectionError("collection_receipt_unavailable", 503)
        return result
