"""Integration test for MinCC PPN connector end-to-end backfill and DQ (CC3-CC6, T4.2)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from ketrika.connectors.base import RunContext
from ketrika.connectors.mincc_ppn import MinccPpnConnector
from ketrika.connectors.runner import execute_connector_pipeline
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import check_db_connection
from ketrika.core.models.db import PriceObservation, SourceRecord, StockObservation
from ketrika.core.policy import PolicyEngine
from ketrika.core.settings import get_settings
from ketrika.extraction.llm.replay import ReplayClient
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
def test_mincc_ppn_backfill_dq_and_rebuild_lifecycle(db_session: Session):
    """Verify CC3-CC6: backfill 10 publications, idempotence, DQ checks, >= 1 stock for >= 3 regions, and offline rebuild."""
    # Ensure fresh Silver/Gold state
    wipe_silver_gold_tables(db_session)
    db_session.commit()

    bronze_store = BronzeStore()
    policy = PolicyEngine()
    connector = MinccPpnConnector()
    replay_llm = ReplayClient()

    ctx = RunContext(
        source_id="mincc_ppn",
        bronze_store=bronze_store,
        policy_engine=policy,
        llm_client=replay_llm,
        offline=True,
    )

    # 1. CC3: Backfill initial run (10 publications)
    stats1 = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()

    assert stats1["n_fetched"] == 10
    assert stats1["n_inserted"] == 64  # 32 prices + 32 stocks
    assert stats1["n_new_artifacts"] >= 0

    # Check active observations in Silver (PriceObservation & StockObservation)
    price_stmt = (
        select(PriceObservation)
        .join(SourceRecord, PriceObservation.source_record_id == SourceRecord.source_record_id)
        .where(
            SourceRecord.source_id == "mincc_ppn",
            PriceObservation.superseded_by.is_(None),
        )
    )
    active_prices = list(db_session.execute(price_stmt).scalars().all())
    assert len(active_prices) == 32

    stock_stmt = (
        select(StockObservation)
        .join(SourceRecord, StockObservation.source_record_id == SourceRecord.source_record_id)
        .where(
            SourceRecord.source_id == "mincc_ppn",
            StockObservation.superseded_by.is_(None),
        )
    )
    active_stocks = list(db_session.execute(stock_stmt).scalars().all())
    assert len(active_stocks) == 32

    # 2. CC4: Data Quality Checks
    # Check 1: provenance_complete (100% of observations have valid source_record_id)
    assert all(p.source_record_id is not None for p in active_prices)
    assert all(s.source_record_id is not None for s in active_stocks)

    # Check 2: price_range_sanity on observed prices
    for p in active_prices:
        assert p.price_value is not None
        val = float(p.price_value)
        assert 1000.0 <= val <= 10000.0, f"Price {val} out of expected bounds [1000, 10000]"
        assert p.currency_raw == "MGA"
        assert p.unit_raw in ("kg", "litre")
        assert p.actor_level in ("retail", "wholesale", "official_ppn")

    # Check 3: stock_sanity on stock observations
    for s in active_stocks:
        assert s.quantity_value is not None
        q = float(s.quantity_value)
        assert 100.0 <= q <= 10000.0, f"Stock quantity {q} out of expected bounds"
        assert s.unit_raw == "tonne"
        assert s.stock_status in ("sufficient", "tight", "shortage", "unknown")
        assert s.coverage_days is not None and float(s.coverage_days) > 0

    # Check 4: Acceptance criterion: >= 1 StockRecord for >= 3 regions (direct SQL check)
    regions_sql = text("""
        SELECT DISTINCT location_raw
        FROM obs.stock_observation
        WHERE location_raw IS NOT NULL
          AND superseded_by IS NULL
    """)
    distinct_stock_regions = [r[0] for r in db_session.execute(regions_sql).fetchall()]
    assert len(distinct_stock_regions) >= 3, (
        f"Expected >= 3 regions with stocks, got {len(distinct_stock_regions)}: {distinct_stock_regions}"
    )
    # Covered regions: Analamanga, Atsinanana, Boeny, Vakinankaratra, Atsimo-Andrefana, Diana
    assert len(distinct_stock_regions) == 6

    # 3. Idempotence test (second execution should insert 0 and skip 64)
    stats2 = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()

    assert stats2["n_fetched"] == 10
    assert stats2["n_inserted"] == 0
    assert stats2["n_skipped"] == 64

    # 4. CC6: Offline Rebuild test
    rebuild_stats = rebuild_database(session=db_session, offline=True, source_id="mincc_ppn")
    db_session.commit()

    assert rebuild_stats["records_inserted"] == 64

    # Verify counts in Silver after wipe and rebuild
    rebuilt_prices = list(db_session.execute(price_stmt).scalars().all())
    rebuilt_stocks = list(db_session.execute(stock_stmt).scalars().all())
    assert len(rebuilt_prices) == 32
    assert len(rebuilt_stocks) == 32
