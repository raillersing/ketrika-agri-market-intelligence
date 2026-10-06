"""Integration test for Connector Framework, Silver loading and Supersession (MVP_EXECUTION_PLAN T2.3)."""

import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ketrika.connectors.base import RunContext
from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.runner import execute_connector_pipeline
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import check_db_connection
from ketrika.core.http import PoliteHttpClient
from ketrika.core.models.db import PriceObservation, SourceRecord
from ketrika.core.policy import PolicyEngine
from ketrika.core.settings import get_settings

CSV_V1 = """product,market,actor_level,period_start,period_end,price,unit,currency
Riz blanc local,Antananarivo,retail,2025-01-01,2025-01-31,2800,kg,MGA
Mais grain sec,Mahajanga,retail,2025-01-01,2025-01-31,1500,kg,MGA
Huile de palme raffinee,Toamasina,retail,2025-01-01,2025-01-31,8000,l,MGA
"""

CSV_V2_MODIFIED = """product,market,actor_level,period_start,period_end,price,unit,currency
Riz blanc local,Antananarivo,retail,2025-01-01,2025-01-31,2900,kg,MGA
Mais grain sec,Mahajanga,retail,2025-01-01,2025-01-31,1500,kg,MGA
Huile de palme raffinee,Toamasina,retail,2025-01-01,2025-01-31,8000,l,MGA
"""


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
def test_dummy_csv_pipeline_lifecycle_and_supersession(httpserver, db_session):
    """Verify T2.3 acceptance criteria:

    1st run inserts N rows with valid source_record_id.
    2nd run is idempotent (0 new rows).
    3rd run with altered value creates 1 new row and 1 superseded_by pointer.
    """
    source_id = f"dummy_{uuid.uuid4().hex[:6]}"
    endpoint_path = f"/{source_id}/prices.csv"

    # Set up HTTP server serving CSV_V1
    httpserver.expect_request(endpoint_path).respond_with_data(
        CSV_V1,
        content_type="text/csv",
    )
    csv_url = httpserver.url_for(endpoint_path)

    connector = DummyCsvConnector()
    connector.source_id = source_id

    policy_engine = PolicyEngine()
    http_client = PoliteHttpClient(policy_engine=policy_engine)
    bronze_store = BronzeStore()

    ctx = RunContext(
        source_id=source_id,
        http_client=http_client,
        bronze_store=bronze_store,
        policy_engine=policy_engine,
        metadata={"csv_url": csv_url},
    )

    # =========================================================================
    # Run 1: Initial Ingestion -> 3 rows inserted
    # =========================================================================
    stats1 = execute_connector_pipeline(connector, ctx, db_session)
    db_session.commit()

    assert stats1["n_fetched"] == 1
    assert stats1["n_new_artifacts"] == 1
    assert stats1["n_inserted"] == 3
    assert stats1["n_skipped"] == 0
    assert stats1["n_superseded"] == 0

    # Query observations from DB
    stmt = (
        select(PriceObservation)
        .join(SourceRecord, PriceObservation.source_record_id == SourceRecord.source_record_id)
        .where(SourceRecord.source_id == source_id)
    )
    records1 = list(db_session.execute(stmt).scalars().all())
    assert len(records1) == 3
    for obs in records1:
        assert obs.source_record_id is not None
        assert obs.superseded_by is None
        assert obs.natural_key is not None

    # Check specific values
    ant_obs1 = next(r for r in records1 if r.location_raw == "Antananarivo")
    assert ant_obs1.price_raw == "2800"
    assert float(ant_obs1.price_value) == 2800.0

    # =========================================================================
    # Run 2: Second Execution -> Idempotence (0 new rows)
    # =========================================================================
    stats2 = execute_connector_pipeline(connector, ctx, db_session)
    db_session.commit()

    assert stats2["n_fetched"] == 1
    assert stats2["n_new_artifacts"] == 0  # Same sha256
    assert stats2["n_inserted"] == 0
    assert stats2["n_skipped"] == 3
    assert stats2["n_superseded"] == 0

    records2 = list(db_session.execute(stmt).scalars().all())
    assert len(records2) == 3  # Count unchanged

    # =========================================================================
    # Run 3: Altered Price -> 1 new row, 1 superseded_by
    # =========================================================================
    # Clear and re-route httpserver with modified CSV (price 2800 -> 2900)
    httpserver.clear()
    httpserver.expect_request(endpoint_path).respond_with_data(
        CSV_V2_MODIFIED,
        content_type="text/csv",
    )

    stats3 = execute_connector_pipeline(connector, ctx, db_session)
    db_session.commit()

    assert stats3["n_fetched"] == 1
    assert stats3["n_new_artifacts"] == 1  # Content changed
    assert stats3["n_inserted"] == 0
    assert stats3["n_skipped"] == 2  # Mahajanga & Toamasina unchanged
    assert stats3["n_superseded"] == 1  # Antananarivo superseded!

    records3 = list(db_session.execute(stmt).scalars().all())
    # Total observations should now be 4: 3 active + 1 superseded
    assert len(records3) == 4

    active_records = [r for r in records3 if r.superseded_by is None]
    superseded_records = [r for r in records3 if r.superseded_by is not None]

    assert len(active_records) == 3
    assert len(superseded_records) == 1

    old_ant = superseded_records[0]
    assert old_ant.location_raw == "Antananarivo"
    assert old_ant.price_raw == "2800"

    new_ant = next(r for r in active_records if r.location_raw == "Antananarivo")
    assert new_ant.price_raw == "2900"
    assert float(new_ant.price_value) == 2900.0

    # Old row's superseded_by points to new row's observation_id!
    assert old_ant.superseded_by == new_ant.observation_id
