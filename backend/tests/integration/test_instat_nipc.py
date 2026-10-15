"""Integration test for INSTAT NIPC connector backfill, DQ and offline rebuild (CC3-CC6, T3.5)."""

import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ketrika.connectors.base import RunContext
from ketrika.connectors.instat_nipc import InstatNipcConnector
from ketrika.connectors.runner import execute_connector_pipeline
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import check_db_connection
from ketrika.core.http import PoliteHttpClient
from ketrika.core.models.db import CpiObservation, SourceRecord
from ketrika.core.policy import PolicyEngine
from ketrika.core.registry import find_repo_root
from ketrika.core.settings import get_settings
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.legacy_replay import rejected_legacy_rebuild

FIXTURE_PATH = (
    find_repo_root() / "backend" / "tests" / "fixtures" / "instat_nipc" / "nipc_sample.csv"
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
def test_instat_nipc_backfill_dq_and_rebuild_lifecycle(
    httpserver, db_session, csv_content: str, monkeypatch
):
    """Verify CC3-CC6: backfill execution, idempotence, DQ checks and offline rebuild."""
    wipe_silver_gold_tables(db_session)
    db_session.commit()

    run_tag = uuid.uuid4().hex[:8]
    unique_csv = f"# test_run_{run_tag}\n" + csv_content

    path = f"/instat_nipc_{run_tag}/nipc.csv"
    httpserver.expect_request(path).respond_with_data(unique_csv, content_type="text/csv")
    file_url = httpserver.url_for(path)

    bronze_store = BronzeStore()
    httpserver.expect_request("/robots.txt").respond_with_data("", status=404)
    policy = PolicyEngine()
    http_client = PoliteHttpClient(policy_engine=policy)
    from tests.local_connector import local_connector

    connector = local_connector(InstatNipcConnector, monkeypatch)
    source_id = connector.source_id

    ctx = RunContext(
        source_id=source_id,
        bronze_store=bronze_store,
        http_client=http_client,
        policy_engine=policy,
        metadata={"file_url": file_url},
    )

    # 1. CC3: Backfill initial run
    stats1 = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()
    assert stats1["n_inserted"] == 189
    assert stats1["n_new_artifacts"] == 1

    # Check observations in Silver
    stmt = (
        select(CpiObservation)
        .join(SourceRecord, CpiObservation.source_record_id == SourceRecord.source_record_id)
        .where(
            SourceRecord.source_id == source_id,
            CpiObservation.superseded_by.is_(None),
        )
    )
    cpi_obs = list(db_session.execute(stmt).scalars().all())
    assert len(cpi_obs) == 189

    # 2. CC4: Data Quality Checks
    # Check 1: 100% Provenance from Bronze
    assert all(o.source_record_id is not None for o in cpi_obs)

    # Check 2: Food CPI series spans >= 5 years (T3.5 acceptance criterion)
    food_obs = [o for o in cpi_obs if o.series_code == "cpi_food"]
    assert len(food_obs) == 63
    food_years = {o.period_start.year for o in food_obs}
    assert len(food_years) >= 5
    assert min(food_years) == 2019
    assert max(food_years) == 2024

    # Check 3: Realistic CPI value sanity
    for o in cpi_obs:
        assert o.index_value is not None
        val = float(o.index_value)
        assert 50.0 <= val <= 300.0, f"Unrealistic CPI index value: {val}"
        assert o.geo_scope == "national"
        assert o.base_period == "2016=100"

    # 3. Idempotence: second run adds 0 rows
    stats2 = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()
    assert stats2["n_inserted"] == 0
    assert stats2["n_skipped"] == 189

    # 4. CC6: Offline rebuild stable verification
    rebuild_stats = rejected_legacy_rebuild(db_session, source_id)
    assert rebuild_stats["source_records_replayed"] >= 1

    obs_after = list(db_session.execute(stmt).scalars().all())
    assert len(obs_after) == 189

    food_after = [o for o in obs_after if o.series_code == "cpi_food"]
    assert len(food_after) == 63
    years_after = {o.period_start.year for o in food_after}
    assert len(years_after) >= 5
