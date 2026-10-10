"""Integration test for FAOSTAT connector end-to-end backfill and DQ (CC3-CC6, T3.3)."""

import json
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ketrika.connectors.base import RunContext
from ketrika.connectors.faostat import FaostatConnector
from ketrika.connectors.runner import execute_connector_pipeline
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import check_db_connection
from ketrika.core.http import PoliteHttpClient
from ketrika.core.models.db import ProductionObservation, SourceRecord, TradeFlow
from ketrika.core.policy import PolicyEngine
from ketrika.core.registry import find_repo_root
from ketrika.core.settings import get_settings
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.legacy_replay import rejected_legacy_rebuild

FIXTURE_PATH = (
    find_repo_root() / "backend" / "tests" / "fixtures" / "faostat" / "faostat_sample.json"
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
def json_content() -> str:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return f.read()


@pytest.mark.integration
def test_faostat_backfill_dq_and_rebuild_lifecycle(httpserver, db_session, json_content: str):
    """Verify CC3-CC6: backfill execution, idempotence, supersession, DQ checks and offline rebuild."""
    # Ensure fresh Silver/Gold state
    wipe_silver_gold_tables(db_session)
    db_session.commit()

    run_tag = uuid.uuid4().hex[:8]
    raw_dict = json.loads(json_content)
    raw_dict["test_tag"] = run_tag
    unique_json = json.dumps(raw_dict)

    endpoint_path = f"/faostat_{run_tag}/data.json"
    httpserver.expect_request(endpoint_path).respond_with_data(
        unique_json, content_type="application/json"
    )
    api_url = httpserver.url_for(endpoint_path)

    bronze_store = BronzeStore()
    policy = PolicyEngine()
    http_client = PoliteHttpClient(policy_engine=policy)
    connector = FaostatConnector()

    ctx = RunContext(
        source_id="faostat",
        bronze_store=bronze_store,
        http_client=http_client,
        policy_engine=policy,
        metadata={"api_url": api_url},
    )

    # 1. CC3: Backfill initial run
    stats1 = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()
    assert stats1["n_inserted"] == 36
    assert stats1["n_new_artifacts"] == 1

    # Check active production observations in Silver
    prod_stmt = (
        select(ProductionObservation)
        .join(SourceRecord, ProductionObservation.source_record_id == SourceRecord.source_record_id)
        .where(
            SourceRecord.source_id == "faostat",
            ProductionObservation.superseded_by.is_(None),
        )
    )
    prod_obs = list(db_session.execute(prod_stmt).scalars().all())
    assert len(prod_obs) == 28

    # Check active trade flows in Silver
    trade_stmt = (
        select(TradeFlow)
        .join(SourceRecord, TradeFlow.source_record_id == SourceRecord.source_record_id)
        .where(
            SourceRecord.source_id == "faostat",
            TradeFlow.superseded_by.is_(None),
        )
    )
    trade_obs = list(db_session.execute(trade_stmt).scalars().all())
    assert len(trade_obs) == 8

    # 2. CC4: Data Quality Checks
    # Check 1: Provenance complete (100% of observations reference bronze source_record_id)
    assert all(p.source_record_id is not None for p in prod_obs)
    assert all(t.source_record_id is not None for t in trade_obs)

    # Check 2: Production rice paddy coverage >= 20 years (T3.3 acceptance criterion)
    rice_obs = [p for p in prod_obs if p.product_raw == "Rice"]
    assert len(rice_obs) >= 20
    rice_years = {p.period_start.year for p in rice_obs}
    assert len(rice_years) >= 20
    assert min(rice_years) == 2004
    assert max(rice_years) == 2023

    # Check 3: Values sanity
    for p in prod_obs:
        assert p.value is not None
        assert float(p.value) > 0.0
        assert p.unit_raw == "t"
        assert p.element == "production_t"

    for t in trade_obs:
        assert t.weight_kg is not None
        assert float(t.weight_kg) > 0.0
        assert t.flow == "import"

    # Check 4: Observed vs imputed flags
    imputed_prod = [p for p in prod_obs if p.observed_or_imputed == "imputed"]
    observed_prod = [p for p in prod_obs if p.observed_or_imputed == "observed"]
    assert len(imputed_prod) == 3
    assert len(observed_prod) == 25

    # 3. Idempotence verification: second run adds 0 rows
    stats2 = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()
    assert stats2["n_inserted"] == 0
    assert stats2["n_skipped"] == 36

    # 4. CC6: Rebuild stable verification
    rebuild_stats = rejected_legacy_rebuild(db_session, "faostat")
    assert rebuild_stats["source_records_replayed"] >= 1

    prod_after = list(db_session.execute(prod_stmt).scalars().all())
    trade_after = list(db_session.execute(trade_stmt).scalars().all())
    assert len(prod_after) == 28
    assert len(trade_after) == 8

    # Verify Rice years coverage preserved after rebuild
    rice_after = [p for p in prod_after if p.product_raw == "Rice"]
    assert len(rice_after) >= 20
