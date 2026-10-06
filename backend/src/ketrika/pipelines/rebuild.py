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

logger = logging.getLogger("ketrika.rebuild")


def wipe_silver_gold_tables(session: Session) -> dict[str, int]:
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

    gold_matviews = list(
        session.execute(text("SELECT matviewname FROM pg_matviews WHERE schemaname = 'gold'"))
        .scalars()
        .all()
    )
    for mv in gold_matviews:
        session.execute(text(f"REFRESH MATERIALIZED VIEW gold.{mv};"))

    session.flush()
    logger.info("Successfully wiped Silver and Gold tables.")
    return {
        "gold_tables_truncated": len(gold_tables),
        "gold_matviews_refreshed": len(gold_matviews),
    }


def rebuild_database(
    session: Session | None = None,
    offline: bool = True,
) -> dict[str, Any]:
    """Rebuild Silver/Gold layers offline from Bronze storage and meta.source_record.

    Guarantees:
    - Zero network calls (HTTP_OFFLINE=1).
    - Fully deterministic replay in chronological order.
    - Exact preservation of supersession history.
    """
    bronze_store = BronzeStore()
    policy_engine = PolicyEngine()

    def _execute(s: Session) -> dict[str, Any]:
        # 1. Wipe Silver & Gold tables
        wipe_stats = wipe_silver_gold_tables(s)

        # 2. Query all source records chronologically (fetched_at ASC)
        stmt = select(SourceRecord).order_by(
            SourceRecord.fetched_at.asc(), SourceRecord.source_record_id.asc()
        )
        source_records = list(s.execute(stmt).scalars().all())
        logger.info("Found %d source records to replay from Bronze", len(source_records))

        stats: dict[str, Any] = {
            "source_records_total": len(source_records),
            "source_records_replayed": 0,
            "source_records_skipped": 0,
            "records_inserted": 0,
            "records_superseded": 0,
            "records_skipped": 0,
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
                    else:
                        stats["records_skipped"] += 1

                stats["source_records_replayed"] += 1

            except Exception as exc:
                logger.error(
                    "Failed to replay source_record %s (%s): %s",
                    s_rec.source_record_id,
                    s_rec.source_id,
                    exc,
                )
                raise

        s.commit()
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
        sys.exit(0)
    except Exception as exc:
        print(f"Rebuild failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
