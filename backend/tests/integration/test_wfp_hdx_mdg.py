"""Integration test for WFP HDX connector end-to-end backfill and DQ (CC3-CC6, T3.1)."""

import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ketrika.connectors.base import RunContext
from ketrika.connectors.runner import execute_connector_pipeline
from ketrika.connectors.wfp_hdx_mdg import WfpHdxMdgConnector
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import check_db_connection
from ketrika.core.http import PoliteHttpClient
from ketrika.core.models.db import PriceObservation, SourceRecord
from ketrika.core.policy import PolicyEngine
from ketrika.core.registry import find_repo_root
from ketrika.core.settings import get_settings
from ketrika.pipelines.rebuild import rebuild_database, wipe_silver_gold_tables

FIXTURE_PATH = (
    find_repo_root()
    / "backend"
    / "tests"
    / "fixtures"
    / "wfp_hdx_mdg"
    / "wfp_food_prices_mdg_sample.csv"
)


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


@pytest.fixture
def csv_content() -> str:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return f.read()


@pytest.mark.integration
def test_wfp_hdx_backfill_dq_and_rebuild_lifecycle(httpserver, db_session, csv_content: str):
    """Verify CC3-CC6: backfill execution, idempotence, supersession, DQ checks and offline rebuild."""
    # Ensure fresh Silver/Gold state
    wipe_silver_gold_tables(db_session)
    db_session.commit()

    run_tag = uuid.uuid4().hex[:8]
    unique_csv = f"# test_run_{run_tag}\n" + csv_content

    endpoint_path = f"/wfp_test_{run_tag}/prices.csv"
    httpserver.expect_request(endpoint_path).respond_with_data(unique_csv, content_type="text/csv")
    csv_url = httpserver.url_for(endpoint_path)

    bronze_store = BronzeStore()
    policy = PolicyEngine()
    http_client = PoliteHttpClient(policy_engine=policy)
    connector = WfpHdxMdgConnector()

    ctx = RunContext(
        source_id="wfp_hdx_mdg",
        bronze_store=bronze_store,
        http_client=http_client,
        policy_engine=policy,
        metadata={"csv_url": csv_url},
    )

    # 1. CC3: Backfill initial run
    stats1 = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()
    assert stats1["n_inserted"] == 36
    assert stats1["n_new_artifacts"] == 1

    # Check active observations in Silver
    stmt = (
        select(PriceObservation)
        .join(SourceRecord, PriceObservation.source_record_id == SourceRecord.source_record_id)
        .where(
            SourceRecord.source_id == "wfp_hdx_mdg",
            PriceObservation.superseded_by.is_(None),
        )
    )
    active_obs = list(db_session.execute(stmt).scalars().all())
    assert len(active_obs) == 36

    # 2. CC4: Data Quality Checks
    # Check 1: provenance_complete (100% of observations have valid source_record_id)
    assert all(o.source_record_id is not None for o in active_obs)

    # Check 2: price_range_sanity (prices in realistic range)
    for o in active_obs:
        assert o.price_value is not None
        assert 500.0 <= float(o.price_value) <= 25000.0, f"Unrealistic price: {o.price_value}"

    # Check 3: required fields completeness
    for o in active_obs:
        assert o.product_raw != ""
        assert o.unit_raw != ""
        assert o.actor_level in ("retail", "wholesale")
        assert o.period_start is not None

    # 3. Idempotence verification: second run adds 0 rows
    stats2 = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()
    assert stats2["n_inserted"] == 0
    assert stats2["n_skipped"] == 36

    # 4. CC6: Rebuild stable verification
    rebuild_stats = rebuild_database(session=db_session, offline=True, source_id="wfp_hdx_mdg")
    assert rebuild_stats["source_records_replayed"] >= 1

    obs_after_rebuild = list(db_session.execute(stmt).scalars().all())
    assert len(obs_after_rebuild) == 36
    # Verify commodities present
    commodities = {o.product_raw for o in obs_after_rebuild}
    assert "Rice (local)" in commodities
    assert "Maize" in commodities
    assert "Cassava (fresh)" in commodities
