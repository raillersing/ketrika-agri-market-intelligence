"""Integration test for MiASA ODR connector end-to-end backfill and DQ (CC3-CC6, T4.1)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from ketrika.connectors.base import RunContext
from ketrika.connectors.miasa_odr import MiasaOdrConnector
from ketrika.connectors.runner import execute_connector_pipeline
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import check_db_connection
from ketrika.core.models.db import PriceObservation, ReviewItem, SourceRecord
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
def test_miasa_odr_backfill_dq_and_rebuild_lifecycle(db_session: Session):
    """Verify CC3-CC6: backfill 3 editions, idempotence, DQ checks, SQL 0 ND/NA->0, and offline rebuild."""
    # Ensure fresh Silver/Gold state
    wipe_silver_gold_tables(db_session)
    db_session.commit()

    bronze_store = BronzeStore()
    policy = PolicyEngine()
    connector = MiasaOdrConnector()
    replay_llm = ReplayClient()

    ctx = RunContext(
        source_id="miasa_odr",
        bronze_store=bronze_store,
        policy_engine=policy,
        llm_client=replay_llm,
        offline=True,
    )

    # 1. CC3: Backfill initial run (3 editions: 850, 710, 520)
    stats1 = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()

    assert stats1["n_fetched"] == 3
    assert stats1["n_inserted"] == 180  # 3 editions * 60 records
    assert stats1["n_new_artifacts"] >= 0

    # Check active observations in Silver
    stmt = (
        select(PriceObservation)
        .join(SourceRecord, PriceObservation.source_record_id == SourceRecord.source_record_id)
        .where(
            SourceRecord.source_id == "miasa_odr",
            PriceObservation.superseded_by.is_(None),
        )
    )
    active_obs = list(db_session.execute(stmt).scalars().all())
    assert len(active_obs) == 180

    # 2. CC4: Data Quality Checks
    # Check 1: provenance_complete (100% of observations have valid source_record_id)
    assert all(o.source_record_id is not None for o in active_obs)

    # Check 2: price_range_sanity on observed prices
    numeric_obs = [o for o in active_obs if o.price_value is not None]
    assert len(numeric_obs) >= 170  # ~171 numeric, 9 missing
    for o in numeric_obs:
        pv = o.price_value
        assert pv is not None
        val = float(pv)
        assert 700.0 <= val <= 5000.0, f"Price {val} out of expected bounds [700, 5000]"

    # Check 3: required fields completeness
    for o in active_obs:
        assert o.product_raw != ""
        assert o.actor_level in ("producer", "wholesale", "retail")
        assert o.unit_raw == "kg"
        assert o.currency_raw == "MGA"
        assert o.period_start is not None
        assert o.period_end is not None

    # Check 4: Actor level distribution
    producer_obs = [o for o in active_obs if o.actor_level == "producer"]
    wholesale_obs = [o for o in active_obs if o.actor_level == "wholesale"]
    retail_obs = [o for o in active_obs if o.actor_level == "retail"]
    assert len(producer_obs) == 36  # 3 * 12
    assert len(wholesale_obs) == 72  # 3 * 24
    assert len(retail_obs) == 72  # 3 * 24

    # Check 5: Variety distribution
    varieties = {o.variety for o in active_obs if o.variety is not None}
    assert "Vary gasy" in varieties
    assert "Makalioka" in varieties
    assert "Tsipala" in varieties
    assert "25% brisures" in varieties

    # Check 6 (T4.1 Acceptance criteria): Review items opened <= 5% of records
    review_items_stmt = (
        select(func.count(ReviewItem.review_id))
        .join(SourceRecord, ReviewItem.source_record_id == SourceRecord.source_record_id)
        .where(SourceRecord.source_id == "miasa_odr")
    )
    n_review_items = db_session.execute(review_items_stmt).scalar() or 0
    assert (n_review_items / len(active_obs)) <= 0.05, (
        f"Review items share {n_review_items / len(active_obs):.2%} exceeds 5% threshold"
    )

    # Check 7 (T4.1 Strict Acceptance Criterion): 0 valeur ND ou NA convertie en 0 (test SQL direct)
    zero_sql = text("""
        SELECT count(*)
        FROM obs.price_observation
        WHERE (missing_code IN ('ND', 'NA') OR price_raw IN ('ND', 'NA'))
          AND price_value = 0
    """)
    zero_count = db_session.execute(zero_sql).scalar()
    assert zero_count == 0, f"Found {zero_count} ND/NA records converted to numeric 0!"

    # Verify that missing_code records have price_value is NULL
    missing_obs = [o for o in active_obs if o.missing_code in ("ND", "NA")]
    assert len(missing_obs) >= 7  # 3 per bulletin = 9
    for o in missing_obs:
        assert o.price_value is None, (
            f"Expected NULL price_value for missing_code, got {o.price_value}"
        )

    # 3. Idempotence: second run adds 0 rows, skips all 180
    stats2 = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()
    assert stats2["n_inserted"] == 0
    assert stats2["n_skipped"] == 180

    # 4. CC6: Offline rebuild stability
    rebuild_stats = rebuild_database(session=db_session, offline=True, source_id="miasa_odr")
    assert rebuild_stats["source_records_replayed"] >= 1

    obs_after_rebuild = list(db_session.execute(stmt).scalars().all())
    assert len(obs_after_rebuild) == 180

    # Confirm same exact counts after rebuild
    rebuild_producer = sum(1 for o in obs_after_rebuild if o.actor_level == "producer")
    rebuild_wholesale = sum(1 for o in obs_after_rebuild if o.actor_level == "wholesale")
    rebuild_retail = sum(1 for o in obs_after_rebuild if o.actor_level == "retail")
    assert rebuild_producer == 36
    assert rebuild_wholesale == 72
    assert rebuild_retail == 72
