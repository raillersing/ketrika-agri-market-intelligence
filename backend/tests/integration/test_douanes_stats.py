"""Integration test for Douanes Stats connector end-to-end backfill, DQ and revision cycle (CC3-CC6, T4.3)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from ketrika.connectors.base import DiscoveredItem, RawArtifact, RunContext
from ketrika.connectors.douanes_stats import DouanesStatsConnector
from ketrika.connectors.runner import (
    execute_connector_pipeline,
    load_record_with_supersession,
    record_bronze_artifact,
)
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import check_db_connection
from ketrika.core.models.db import SourceRecord, TradeFlow
from ketrika.core.policy import PolicyEngine
from ketrika.core.settings import get_settings
from ketrika.pipelines import rebuild as rebuild_module
from ketrika.pipelines.rebuild import rebuild_database, wipe_silver_gold_tables


@pytest.fixture
def db_session():
    """Create a database session connected to PostgreSQL."""
    if not check_db_connection():
        pytest.skip("Database is not reachable (skipping integration tests)")
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session = Session(engine)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.integration
def test_douanes_stats_backfill_dq_rebuild_and_revision_cycle(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Verify CC3-CC6: backfill 36 flows, idempotence, DQ checks, supersession revision test, and offline rebuild."""
    # Ensure fresh Silver/Gold state
    wipe_silver_gold_tables(db_session)
    db_session.commit()

    bronze_store = BronzeStore()
    policy = PolicyEngine()
    connector = DouanesStatsConnector()

    ctx = RunContext(
        source_id="douanes_stats",
        bronze_store=bronze_store,
        policy_engine=policy,
        offline=True,
    )

    # 1. CC3: Backfill initial run (douanes_stats_2024.csv, 36 records)
    stats1 = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()

    assert stats1["n_fetched"] == 1
    assert stats1["n_inserted"] == 36
    assert stats1["n_new_artifacts"] >= 0

    # Verify active observations in Silver (obs.trade_flow)
    stmt = (
        select(TradeFlow)
        .join(SourceRecord, TradeFlow.source_record_id == SourceRecord.source_record_id)
        .where(
            SourceRecord.source_id == "douanes_stats",
            TradeFlow.superseded_by.is_(None),
        )
    )
    active_flows = list(db_session.execute(stmt).scalars().all())
    assert len(active_flows) == 36

    # Verify commodity types and flows
    imports = [f for f in active_flows if f.flow == "import"]
    exports = [f for f in active_flows if f.flow == "export"]
    assert len(imports) == 27  # 9 import commodities * 3 months
    assert len(exports) == 9  # 3 export commodities * 3 months
    assert len(imports) + len(exports) == 36

    # 2. CC4: Data Quality Checks
    # Check 1: Provenance complete (100% have valid source_record_id)
    assert all(f.source_record_id is not None for f in active_flows)

    # Check 2: Physical sanity of weights and values
    for f in active_flows:
        assert f.weight_kg is not None and float(f.weight_kg) > 0
        assert f.value_mga is not None and float(f.value_mga) > 0
        assert f.value_usd is not None and float(f.value_usd) > 0
        assert f.period_start is not None and f.period_end is not None
        assert f.period_start <= f.period_end
        assert f.partner_raw is not None and len(f.partner_raw) > 0
        assert f.partner_iso3 is not None and len(f.partner_iso3) == 3

    # 3. Idempotence test: second run inserts 0, skips 36
    stats2 = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()

    assert stats2["n_fetched"] == 1
    assert stats2["n_inserted"] == 0
    assert stats2["n_skipped"] == 36

    # 4. Critical Revision Test (Acceptance criterion: 2 snapshots with 1 modified flow)
    # Step A: Ingest snapshot v1 (4 flows)
    item_v1 = DiscoveredItem(
        url="https://www.douanes.gov.mg/stats/douanes_snapshot_v1.csv",
        partition_key="douanes_snapshot_v1",
        published_at=datetime(2024, 4, 1, 8, 0, tzinfo=UTC),
    )
    raw_v1 = connector.fetch(item_v1, ctx)
    src_rec_v1, _ = record_bronze_artifact(
        session=db_session,
        source_id="douanes_stats",
        artifact=raw_v1,
        parser_version=connector.parser_version,
    )
    bound_v1 = RawArtifact(
        source_record_id=str(src_rec_v1.source_record_id),
        object_key=raw_v1.object_key,
        content_sha256=raw_v1.content_sha256,
        mime_type=raw_v1.mime_type,
        url=raw_v1.url,
        is_new=raw_v1.is_new,
        published_at=raw_v1.published_at,
    )
    parsed_v1 = connector.parse(bound_v1, ctx)
    for rec in parsed_v1.records:
        action, _ = load_record_with_supersession(
            session=db_session,
            record=rec,
            source_id="douanes_stats",
            source_record_id=src_rec_v1.source_record_id,
        )
        assert action == "inserted"
    db_session.commit()

    # Step B: Ingest snapshot v2 (4 flows: 3 identical, 1 modified)
    item_v2 = DiscoveredItem(
        url="https://www.douanes.gov.mg/stats/douanes_snapshot_v2.csv",
        partition_key="douanes_snapshot_v2",
        published_at=datetime(2024, 4, 15, 8, 0, tzinfo=UTC),
    )
    raw_v2 = connector.fetch(item_v2, ctx)
    src_rec_v2, _ = record_bronze_artifact(
        session=db_session,
        source_id="douanes_stats",
        artifact=raw_v2,
        parser_version=connector.parser_version,
    )
    bound_v2 = RawArtifact(
        source_record_id=str(src_rec_v2.source_record_id),
        object_key=raw_v2.object_key,
        content_sha256=raw_v2.content_sha256,
        mime_type=raw_v2.mime_type,
        url=raw_v2.url,
        is_new=raw_v2.is_new,
        published_at=raw_v2.published_at,
    )
    parsed_v2 = connector.parse(bound_v2, ctx)
    actions = []
    for rec in parsed_v2.records:
        action, _ = load_record_with_supersession(
            session=db_session,
            record=rec,
            source_id="douanes_stats",
            source_record_id=src_rec_v2.source_record_id,
        )
        actions.append(action)
    db_session.commit()

    assert actions.count("idempotent_skipped") == 3
    assert actions.count("superseded") == 1

    # Verify with direct SQL that exactly 1 row has superseded_by IS NOT NULL
    superseded_count_sql = text("""
        SELECT count(*)
        FROM obs.trade_flow
        WHERE superseded_by IS NOT NULL;
    """)
    n_superseded = db_session.execute(superseded_count_sql).scalar()
    assert n_superseded == 1

    # Verify that the active record (superseded_by IS NULL) returns the revised value
    revised_query = text("""
        SELECT weight_kg, value_mga, superseded_by
        FROM obs.trade_flow
        WHERE product_raw = 'Riz semi-blanchi ou blanchi'
          AND partner_raw = 'Inde'
          AND period_start = '2024-04-01'
        ORDER BY published_at DESC;
    """)
    rows = db_session.execute(revised_query).fetchall()
    assert len(rows) == 2  # 1 old superseded, 1 new active
    old_row, active_row = (rows[1], rows[0]) if rows[0][2] is None else (rows[0], rows[1])

    # Old row is superseded
    assert old_row[2] is not None
    assert float(old_row[0]) == 25000000.0
    assert float(old_row[1]) == 75000000000.0

    # Active row has the revised values
    assert active_row[2] is None
    assert float(active_row[0]) == 26500000.0
    assert float(active_row[1]) == 79500000000.0

    # 5. Bounded offline replay of this scenario, NOT a full QA-store rebuild.
    # ADR-015: retain historical Bronze/metadata, including older CRLF variants.
    current_ids = {
        active_flows[0].source_record_id,
        src_rec_v1.source_record_id,
        src_rec_v2.source_record_id,
    }
    assert len(current_ids) == 3
    source_ids_before = set(
        db_session.execute(select(SourceRecord.source_record_id)).scalars().all()
    )

    def select_current_corpus(entity: type[SourceRecord]) -> Select[SourceRecord]:
        assert entity is SourceRecord
        return select(entity).where(entity.source_record_id.in_(current_ids))

    # Temporary SQL projection only in this test; production rebuild is unchanged.
    monkeypatch.setattr(rebuild_module, "select", select_current_corpus)
    rebuild_stats = rebuild_database(session=db_session, offline=True, source_id="douanes_stats")
    db_session.commit()
    assert rebuild_stats["source_records_total"] == 3
    assert rebuild_stats["source_records_replayed"] == 3
    assert rebuild_stats["source_records_skipped"] == 0
    assert (
        set(db_session.execute(select(SourceRecord.source_record_id)).scalars().all())
        == source_ids_before
    )

    # Total replayed: 36 (initial) + 4 (v1) + 4 (v2) = 44 records processed
    # Inserted = 36 + 4 = 40, superseded = 1, skipped = 3
    assert rebuild_stats["records_inserted"] == 40
    assert rebuild_stats["records_superseded"] == 1
    assert rebuild_stats["records_skipped"] == 3

    # Direct SQL check after rebuild: exactly 1 superseded row remains
    assert db_session.execute(superseded_count_sql).scalar() == 1
    rebuilt_active = db_session.execute(revised_query).fetchall()
    rebuilt_active_row = next(r for r in rebuilt_active if r[2] is None)
    assert float(rebuilt_active_row[0]) == 26500000.0
    assert float(rebuilt_active_row[1]) == 79500000000.0
