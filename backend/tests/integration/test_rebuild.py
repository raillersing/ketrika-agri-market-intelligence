"""Integration test for offline rebuild pipeline (MVP_EXECUTION_PLAN T2.6).

Verifies that:
1. Rebuild wipes obs/ml/gold layers and replays parse -> normalize -> load from Bronze.
2. Counts before and after rebuild are identical with dummy_csv.
3. HTTP_OFFLINE=1 is strictly enforced during rebuild.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ketrika.connectors.base import RunContext
from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.registry import register_connector
from ketrika.connectors.runner import execute_connector_pipeline
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import check_db_connection
from ketrika.core.http import PoliteHttpClient
from ketrika.core.models.db import PriceObservation, SourceRecord
from ketrika.core.policy import OfflineError, PolicyEngine
from ketrika.core.provenance_audit import ObservationTarget, audit_observation_provenance
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.settings import get_settings
from ketrika.pipelines.rebuild import rebuild_database

CSV_SAMPLE = """product,market,actor_level,period_start,period_end,price,unit,currency
Riz blanc local,Antananarivo,retail,2025-01-01,2025-01-31,2800,kg,MGA
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
def test_rebuild_preserves_exact_counts_offline(httpserver, db_session):
    """Verify T2.6 acceptance: with dummy_csv, counts before and after rebuild are identical."""
    source_id = f"dummy_{uuid.uuid4().hex[:6]}"
    endpoint_path = f"/{source_id}/data.csv"

    httpserver.expect_request(endpoint_path).respond_with_data(CSV_SAMPLE, content_type="text/csv")
    csv_url = httpserver.url_for(endpoint_path)

    bronze_store = BronzeStore()
    httpserver.expect_request("/robots.txt").respond_with_data("", status=404)
    policy = PolicyEngine()
    http_client = PoliteHttpClient(policy_engine=policy, allow_loopback=True)

    connector = DummyCsvConnector()
    connector.source_id = source_id
    register_connector(source_id, DummyCsvConnector)

    ctx = RunContext(
        source_id=source_id,
        bronze_store=bronze_store,
        http_client=http_client,
        policy_engine=policy,
        metadata={"csv_url": csv_url},
    )

    # 1. Ingest initial data
    stats = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()
    assert stats["n_inserted"] == 3

    # Check count before rebuild
    stmt = (
        select(PriceObservation)
        .join(SourceRecord, PriceObservation.source_record_id == SourceRecord.source_record_id)
        .where(SourceRecord.source_id == source_id)
    )
    obs_before = list(db_session.execute(stmt).scalars().all())
    count_before = len(obs_before)
    assert count_before == 3

    # 2. Verify that offline mode raises OfflineError if HTTP is attempted
    old_offline = os.environ.get("HTTP_OFFLINE")
    os.environ["HTTP_OFFLINE"] = "1"
    try:
        with pytest.raises(OfflineError):
            http_client.get("http://localhost:9999/any-url")
    finally:
        if old_offline is not None:
            os.environ["HTTP_OFFLINE"] = old_offline
        else:
            os.environ.pop("HTTP_OFFLINE", None)

    # 3. Execute rebuild_database
    # Qualified CSV cells only; not a full historical-store R0.8 certification.
    rebuild_stats = rebuild_database(session=db_session, offline=True, source_id=source_id)
    assert rebuild_stats["source_records_replayed"] >= 1
    assert rebuild_stats["gold_views_refreshed"] == 13

    # 4. Check count after rebuild
    obs_after = list(db_session.execute(stmt).scalars().all())
    count_after = len(obs_after)

    # Strict equality requirement: counts before and after rebuild are identical
    assert count_after == count_before
    assert count_after == 3
    assert rebuild_stats["gold_publication_state"] == "empty"
    assert rebuild_stats["source_observations_total"] == 0
    assert rebuild_stats["source_cell_rate"] is None
    receipt = audit_observation_provenance(
        db_session,
        BronzeProofReader(bronze_store),
        mode="incremental",
        targets=[ObservationTarget("price_observation", row.observation_id) for row in obs_after],
    )
    assert receipt.report.valid == receipt.report.total == 3
    assert receipt.report.objects_read == 1 and receipt.report.passed

    # Verify attributes preserved
    prices_after = sorted([float(o.price_value) for o in obs_after if o.price_value is not None])
    assert prices_after == [1500.0, 2800.0, 8000.0]
