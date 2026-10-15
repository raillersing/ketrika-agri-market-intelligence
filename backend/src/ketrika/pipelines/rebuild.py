"""Offline database rebuild pipeline from Bronze layer (SPECS §3.3, §12, MVP_EXECUTION_PLAN T2.6).

Replays parse -> normalize -> load for all meta.source_record objects without network access.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.registry import get_connector_class
from ketrika.connectors.runner import load_record_with_supersession
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import SourceRecord
from ketrika.core.policy import PolicyEngine
from ketrika.core.provenance import ArtifactReader
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.gold.provenance_gate import GoldProvenanceRejected
from ketrika.gold.refresh import refresh_gold_views
from ketrika.gold.schema_gate import GoldSchemaRejected

logger = logging.getLogger("ketrika.rebuild")


def wipe_silver_gold_tables(
    session: Session, *, reader: ArtifactReader | None = None
) -> dict[str, int]:
    """Wipe all observation and ML tables, and refresh/truncate Gold views (SPECS §3.3, T2.6).

    Uses TRUNCATE CASCADE to safely bypass row-level immutability triggers on obs tables.
    """
    logger.info("Wiping tables in schema obs and ml...")

    # 1. Truncate obs and ml tables
    session.execute(
        text(
            "TRUNCATE TABLE "
            "obs.price_observation, "
            "obs.stock_observation, "
            "obs.trade_flow, "
            "obs.production_observation, "
            "obs.weather_observation, "
            "obs.cpi_observation, "
            "obs.event, "
            "ops.review_item, "
            "ops.dq_result, "
            "ml.forecast, "
            "ml.model_run "
            "CASCADE;"
        )
    )

    # 2. Check for any tables or views in schema gold
    gold_tables = list(
        session.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'gold'")
        )
        .scalars()
        .all()
    )
    for tbl in gold_tables:
        session.execute(text(f"TRUNCATE TABLE gold.{tbl} CASCADE;"))

    refresh_res = refresh_gold_views(session, reader=reader)
    session.flush()
    logger.info("Successfully wiped Silver and refreshed Gold tables.")
    return {
        "gold_tables_truncated": len(gold_tables),
        "gold_matviews_refreshed": refresh_res["count"],
    }


def rebuild_database(
    session: Session | None = None,
    offline: bool = True,
    source_id: str | None = None,
    *,
    bronze_store: BronzeStore | None = None,
) -> dict[str, Any]:
    """Rebuild Silver/Gold layers offline from Bronze storage and meta.source_record.

    Guarantees:
    - Policy HTTP calls refused when offline=True (HTTP_OFFLINE=1).
      System-level network isolation is the caller's responsibility (ADR-068).
    - Fully deterministic replay in chronological order.
    - Exact preservation of supersession history.
    """
    bronze_store = bronze_store if bronze_store is not None else BronzeStore()
    proof_reader = BronzeProofReader(bronze_store)
    policy_engine = PolicyEngine()

    def _execute(s: Session) -> dict[str, Any]:
        # 1. Wipe Silver & Gold tables
        wipe_stats = wipe_silver_gold_tables(s, reader=proof_reader)

        # 2. Query all source records chronologically (fetched_at ASC)
        stmt = select(SourceRecord)
        if source_id is not None:
            stmt = stmt.where(SourceRecord.source_id == source_id)
        stmt = stmt.order_by(SourceRecord.fetched_at.asc(), SourceRecord.source_record_id.asc())
        source_records = list(s.execute(stmt).scalars().all())
        logger.info("Found %d source records to replay from Bronze", len(source_records))

        stats: dict[str, Any] = {
            "source_records_total": len(source_records),
            "source_records_replayed": 0,
            "source_records_skipped": 0,
            "records_inserted": 0,
            "records_superseded": 0,
            "records_skipped": 0,
            "records_rejected": 0,
            "gold_wiped": wipe_stats,
        }

        for s_rec in source_records:
            connector_cls = get_connector_class(s_rec.source_id)
            if connector_cls is None:
                logger.warning(
                    "No connector registered for source_id '%s' (source_record %s). Skipping.",
                    s_rec.source_id,
                    s_rec.source_record_id,
                )
                stats["source_records_skipped"] += 1
                continue

            connector = connector_cls()
            if hasattr(connector, "source_id") and s_rec.source_id.startswith("dummy_"):
                object.__setattr__(connector, "source_id", s_rec.source_id)

            ctx = RunContext(
                source_id=s_rec.source_id,
                bronze_store=bronze_store,
                policy_engine=policy_engine,
                offline=True,
                logger=logger,
            )

            # Reconstruct RawArtifact pointing to bronze object_key
            raw_artifact = RawArtifact(
                source_record_id=str(s_rec.source_record_id),
                object_key=s_rec.object_key,
                content_sha256=s_rec.content_sha256,
                mime_type=s_rec.mime_type or "application/octet-stream",
                url=s_rec.source_url,
                is_new=False,
                published_at=s_rec.published_at,
            )

            try:
                parse_res = connector.parse(raw_artifact, ctx)
                for rec in parse_res.records:
                    action, _ = load_record_with_supersession(
                        session=s,
                        record=rec,
                        source_id=s_rec.source_id,
                        source_record_id=s_rec.source_record_id,
                    )
                    if action == "inserted":
                        stats["records_inserted"] += 1
                    elif action == "superseded":
                        stats["records_superseded"] += 1
                    elif action == "review_required":
                        stats["records_rejected"] += 1
                    else:
                        stats["records_skipped"] += 1

                stats["source_records_replayed"] += 1

            except Exception as exc:
                logger.warning(
                    "Failed to replay source_record %s (%s, object_key=%s): %s. Skipping.",
                    s_rec.source_record_id,
                    s_rec.source_id,
                    s_rec.object_key,
                    exc,
                )
                stats["source_records_skipped"] += 1

        s.commit()
        # Refresh Gold views to reflect replayed records
        try:
            gold_refresh = refresh_gold_views(s, reader=proof_reader)
        except (GoldProvenanceRejected, GoldSchemaRejected) as exc:
            exc.replay_stats = {
                **stats,
                "gold_views_refreshed": 0,
                "gold_publication_state": "refused",
            }
            raise
        s.commit()
        stats["gold_views_refreshed"] = gold_refresh["count"]
        stats["gold_publication_state"] = gold_refresh["provenance_state"]
        stats["source_observations_total"] = gold_refresh["source_observations_total"]
        stats["source_observations_valid"] = gold_refresh["source_observations_valid"]
        stats["source_cell_rate"] = gold_refresh["source_cell_rate"]
        stats["provenance_scope"] = gold_refresh["provenance_scope"]
        logger.info(
            "Rebuild complete! Replayed %d records: %d inserted, %d superseded, %d skipped",
            stats["source_records_replayed"],
            stats["records_inserted"],
            stats["records_superseded"],
            stats["records_skipped"],
        )
        return stats

    prev_offline = os.environ.get("HTTP_OFFLINE")
    if offline:
        os.environ["HTTP_OFFLINE"] = "1"

    try:
        if session is not None:
            return _execute(session)
        else:
            with get_session() as s:
                return _execute(s)
    finally:
        if offline:
            if prev_offline is not None:
                os.environ["HTTP_OFFLINE"] = prev_offline
            else:
                os.environ.pop("HTTP_OFFLINE", None)


def main() -> None:
    """CLI entrypoint for dev.ps1 rebuild / dev.sh rebuild."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    print("=== Ketrika Agri Market Intelligence: Offline Database Rebuild ===")
    try:
        stats = rebuild_database(offline=True)
        print("Rebuild successfully finished!")
        print(
            f"  Source records processed: {stats['source_records_replayed']}/{stats['source_records_total']}"
        )
        print(f"  Observations inserted:   {stats['records_inserted']}")
        print(f"  Observations superseded: {stats['records_superseded']}")
        print(f"  Observations skipped:    {stats['records_skipped']}")
        print(f"  Gold source-cell state: {stats['gold_publication_state']}")
        print("  Empty/fixtures do not qualify a live source, model or complete R0.8 rebuild.")
        sys.exit(0)
    except Exception as exc:
        print(f"Rebuild failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
