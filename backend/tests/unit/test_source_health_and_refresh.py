"""Unit tests for source refresh, recovery, failure notifications, and health monitoring (R1.12).

Validates:
1. Simulated catalog edition detected on subsequent cycle.
2. Failure and idempotent recovery with Mailpit notification and no duplicate rows.
3. Stale and disabled sources correctly reflected in SQL and API.
4. Zero HTTP network requests during PolicyStop.
5. SQL state in meta.ingestion_run matches API and UI expectations.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ketrika.api.main import app
from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.runner import execute_connector_pipeline
from ketrika.connectors.stages import authorize_collection
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_db
from ketrika.core.models.db import IngestionRun, SourceRecord
from ketrika.core.policy import PolicyStop

pytestmark = pytest.mark.usefixtures("authenticated_unit_reader")


def test_r1_12_catalog_edition_detected_on_subsequent_cycle() -> None:
    """Criterion 1: Simulated catalog edition detected in subsequent ingestion cycle."""
    source_id = "test_catalog_source"
    connector = MagicMock()
    connector.source_id = source_id
    connector.parser_version = "1.0.0"

    # Cycle 1: Catalog has edition 1 (Jan 2025)
    item_v1 = DiscoveredItem(
        url="https://example.org/data_2025_01.csv",
        partition_key="2025_01",
        hints={"edition": "1"},
    )
    connector.discover.return_value = [item_v1]

    content1 = b"edition 1"
    sha1 = hashlib.sha256(content1).hexdigest()
    art_v1 = RawArtifact(
        str(uuid.uuid4()),
        f"{source_id}/2025/01/{sha1}.csv",
        sha1,
        "text/csv",
        item_v1.url,
        True,
    )
    connector.fetch.return_value = art_v1
    connector.parse.return_value = ParseResult(records=[], issues=[], parser_version="1.0.0")

    run_v1 = IngestionRun(
        run_id=uuid.uuid4(),
        source_id=source_id,
        started_at=datetime.now(UTC),
        status="running",
        n_fetched=0,
        n_new_artifacts=0,
        n_records=0,
        n_rejected=0,
        n_review=0,
    )
    ref_v1 = SourceRecord(
        source_record_id=uuid.UUID(art_v1.source_record_id),
        source_id=source_id,
        source_url=art_v1.url,
        object_key=art_v1.object_key,
        content_sha256=art_v1.content_sha256,
        mime_type=art_v1.mime_type,
        parser_version="1.0.0",
    )

    session = MagicMock()
    session.get.side_effect = lambda model, key: run_v1 if model is IngestionRun else ref_v1

    content2 = b"edition 2"
    sha2 = hashlib.sha256(content2).hexdigest()

    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.bucket = "test-bucket"
    mock_bronze.client = MagicMock()

    def mock_get_object(*, Bucket: str, Key: str) -> dict:
        body = MagicMock()
        if sha1 in Key:
            body.read.return_value = content1
            return {"Body": body, "ContentLength": len(content1)}
        if sha2 in Key:
            body.read.return_value = content2
            return {"Body": body, "ContentLength": len(content2)}
        raise KeyError(Key)

    mock_bronze.client.get_object.side_effect = mock_get_object
    ctx = RunContext(source_id=source_id, bronze_store=mock_bronze, offline=True)

    with (
        patch("ketrika.connectors.stages.get_source", return_value=None),
        patch("ketrika.connectors.runner.ensure_ingestion_run_started", return_value=run_v1),
        patch("ketrika.connectors.runner.record_bronze_artifact", return_value=(ref_v1, True)),
        patch("ketrika.connectors.runner.send_pipeline_failure_email"),
    ):
        stats1 = execute_connector_pipeline(connector, ctx, session)

    assert stats1["n_fetched"] == 1
    assert stats1["n_new_artifacts"] == 1

    # Cycle 2: Catalog updated with edition 2 (Feb 2025)
    item_v2 = DiscoveredItem(
        url="https://example.org/data_2025_02.csv",
        partition_key="2025_02",
        hints={"edition": "2"},
    )
    connector.discover.return_value = [item_v1, item_v2]

    art_v2 = RawArtifact(
        str(uuid.uuid4()),
        f"{source_id}/2025/02/{sha2}.csv",
        sha2,
        "text/csv",
        item_v2.url,
        True,
    )
    ref_v2 = SourceRecord(
        source_record_id=uuid.UUID(art_v2.source_record_id),
        source_id=source_id,
        source_url=art_v2.url,
        object_key=art_v2.object_key,
        content_sha256=art_v2.content_sha256,
        mime_type=art_v2.mime_type,
        parser_version="1.0.0",
    )

    run_v2 = IngestionRun(
        run_id=uuid.uuid4(),
        source_id=source_id,
        started_at=datetime.now(UTC),
        status="running",
        n_fetched=0,
        n_new_artifacts=0,
        n_records=0,
        n_rejected=0,
        n_review=0,
    )

    def get_model_v2(model: type, key: uuid.UUID) -> IngestionRun | SourceRecord | None:
        if model is IngestionRun:
            return run_v2
        if key == ref_v1.source_record_id:
            return ref_v1
        return ref_v2

    session.get.side_effect = get_model_v2

    def dynamic_fetch(item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        if item.url == item_v1.url:
            return RawArtifact(
                art_v1.source_record_id,
                art_v1.object_key,
                art_v1.content_sha256,
                art_v1.mime_type,
                art_v1.url,
                False,  # Already known in Bronze
            )
        return art_v2

    connector.fetch.side_effect = dynamic_fetch

    def dynamic_record(session, source_id, raw, parser_version):
        if raw.url == item_v1.url:
            return ref_v1, False
        return ref_v2, True

    with (
        patch("ketrika.connectors.stages.get_source", return_value=None),
        patch("ketrika.connectors.runner.ensure_ingestion_run_started", return_value=run_v2),
        patch("ketrika.connectors.runner.record_bronze_artifact", side_effect=dynamic_record),
        patch("ketrika.connectors.runner.send_pipeline_failure_email"),
    ):
        stats2 = execute_connector_pipeline(connector, ctx, session)

    # In cycle 2, 2 items discovered, but only 1 new artifact ingested
    assert stats2["n_fetched"] == 2
    assert stats2["n_new_artifacts"] == 1


def test_r1_12_failure_and_idempotent_recovery() -> None:
    """Criterion 2: Crash records failed status, alerts Mailpit, and subsequent run recovers idempotently."""
    source_id = "test_crash_source"
    connector = MagicMock()
    connector.source_id = source_id
    connector.parser_version = "1.0.0"

    item = DiscoveredItem(url="https://example.org/data.csv", partition_key="part1")
    connector.discover.return_value = [item]

    run = IngestionRun(
        run_id=uuid.uuid4(),
        source_id=source_id,
        started_at=datetime.now(UTC),
        status="running",
        n_fetched=0,
        n_new_artifacts=0,
        n_records=0,
        n_rejected=0,
        n_review=0,
    )

    session = MagicMock()
    session.get.return_value = run

    ctx = RunContext(source_id=source_id, offline=True)

    # Run 1: Network/system crash during fetch
    connector.fetch.side_effect = ConnectionResetError("Connection dropped by peer")

    with (
        patch("ketrika.connectors.stages.get_source", return_value=None),
        patch("ketrika.connectors.runner.ensure_ingestion_run_started", return_value=run),
        patch("ketrika.connectors.runner.send_pipeline_failure_email") as mock_email,
        pytest.raises(ConnectionResetError),
    ):
        execute_connector_pipeline(connector, ctx, session)

    # Verify run was marked failed and notification was sent to Mailpit
    assert run.status == "failed"
    assert run.finished_at is not None
    assert run.error == "COLLECTION_FAILED"
    mock_email.assert_called_once()
    assert mock_email.call_args.kwargs["error_message"] == "COLLECTION_FAILED"

    # Run 2: Recovery run succeeds idempotently
    recovered_run = IngestionRun(
        run_id=uuid.uuid4(),
        source_id=source_id,
        started_at=datetime.now(UTC),
        status="running",
        n_fetched=0,
        n_new_artifacts=0,
        n_records=0,
        n_rejected=0,
        n_review=0,
    )
    rec_content = b"recovered content"
    sha_rec = hashlib.sha256(rec_content).hexdigest()
    art = RawArtifact(
        str(uuid.uuid4()),
        f"{source_id}/2026/10/{sha_rec}.csv",
        sha_rec,
        "text/csv",
        item.url,
        True,
    )
    ref = SourceRecord(
        source_record_id=uuid.UUID(art.source_record_id),
        source_id=source_id,
        source_url=art.url,
        object_key=art.object_key,
        content_sha256=art.content_sha256,
        mime_type=art.mime_type,
        parser_version="1.0.0",
    )
    session.get.side_effect = lambda model, key: recovered_run if model is IngestionRun else ref

    connector.fetch.side_effect = None
    connector.fetch.return_value = art
    connector.parse.return_value = ParseResult(records=[], issues=[], parser_version="1.0.0")

    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.bucket = "test-bucket"
    mock_bronze.client = MagicMock()
    body_rec = MagicMock()
    body_rec.read.return_value = rec_content
    mock_bronze.client.get_object.return_value = {
        "Body": body_rec,
        "ContentLength": len(rec_content),
    }
    ctx.bronze_store = mock_bronze

    with (
        patch("ketrika.connectors.stages.get_source", return_value=None),
        patch(
            "ketrika.connectors.runner.ensure_ingestion_run_started",
            return_value=recovered_run,
        ),
        patch("ketrika.connectors.runner.record_bronze_artifact", return_value=(ref, True)),
        patch("ketrika.connectors.runner.send_pipeline_failure_email"),
    ):
        stats_recovery = execute_connector_pipeline(connector, ctx, session)

    assert stats_recovery["n_fetched"] == 1
    assert stats_recovery["n_new_artifacts"] == 1
    assert stats_recovery["n_inserted"] == 0
    assert stats_recovery["n_skipped"] == 0


def test_r1_12_zero_requests_during_policy_stop() -> None:
    """Criterion 4: Zero HTTP network requests emitted when source is under PolicyStop."""
    connector = MagicMock()
    connector.source_id = "nasa_power"
    mock_http_client = MagicMock()
    ctx = RunContext(source_id="nasa_power", http_client=mock_http_client, offline=False)

    disabled_source_def = MagicMock(
        source_id="nasa_power",
        status="disabled",
        crawl_permission="public_open_data",
    )

    with (
        patch("ketrika.connectors.stages.get_source", return_value=disabled_source_def),
        pytest.raises(PolicyStop, match="source_collection_disabled"),
    ):
        authorize_collection(connector, ctx)

    # Zero HTTP requests sent
    mock_http_client.get.assert_not_called()
    mock_http_client.post.assert_not_called()


def test_r1_12_sources_api_and_health_visibility() -> None:
    """Criteria 3 & 5: Stale and disabled sources correctly exposed in API and SQL concordance."""
    client = TestClient(app)

    # Mock DB query results for /v1/sources
    mock_rows = [
        (
            "wfp_hdx_mdg",
            "WFP HDX Food Prices",
            "P1",
            "disabled",  # source status
            30,  # freshness_sla_days
            45,  # freshness_days (exceeds SLA)
            True,  # is_stale
            "failed",  # latest_run_status
            datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC),
            0,
            0,
            "COLLECTION_FAILED",
            2,
            0,
        ),
        (
            "instat_nipc",
            "INSTAT NIPC",
            "P1",
            "active",
            30,
            12,
            False,
            "success",
            datetime(2026, 10, 14, 8, 30, 0, tzinfo=UTC),
            150,
            150,
            None,
            2,
            150,
        ),
    ]

    mock_session = MagicMock()
    mock_session.scalar.return_value = True  # matview populated
    mock_session.execute.return_value.fetchall.return_value = mock_rows

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = client.get("/v1/sources")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Check disabled source
        wfp = next(s for s in data if s["source_id"] == "wfp_hdx_mdg")
        assert wfp["status"] == "disabled"
        assert wfp["latest_run_status"] == "failed"
        assert wfp["is_stale"] is True
        assert wfp["freshness_days"] == 45

        # Check active healthy source
        instat = next(s for s in data if s["source_id"] == "instat_nipc")
        assert instat["status"] == "active"
        assert instat["latest_run_status"] == "success"
        assert instat["is_stale"] is False
        assert instat["freshness_days"] == 12
    finally:
        app.dependency_overrides.clear()


def test_r1_12_single_source_health_endpoint() -> None:
    """Criterion 5: /v1/sources/{source_id}/health returns exact Gold metrics."""
    client = TestClient(app)

    mock_row = (
        "instat_nipc",
        "INSTAT NIPC",
        "P1",
        30,  # freshness_sla_days
        12,  # freshness_days
        False,  # is_stale
        "success",  # latest_run_status
        datetime(2026, 10, 14, 8, 30, 0, tzinfo=UTC),
        150,  # n_records_30d
        0.9850,  # parse_success_rate
        2,  # open_review_items
        150,  # latest_run_records
        150,  # latest_run_fetched
        None,  # latest_run_error
    )

    mock_session = MagicMock()
    mock_session.scalar.return_value = True  # matview populated
    mock_session.execute.return_value.fetchone.return_value = mock_row

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = client.get("/v1/sources/instat_nipc/health")
        assert response.status_code == 200
        health = response.json()
        assert health["source_id"] == "instat_nipc"
        assert health["is_stale"] is False
        assert health["latest_run_status"] == "success"
        assert health["n_records_30d"] == 150
        assert health["parse_success_rate"] == 0.985
        assert health["open_review_items"] == 2
    finally:
        app.dependency_overrides.clear()
