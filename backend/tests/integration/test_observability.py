"""Integration tests for Observability, failure sensors, Mailpit notifications, and /v1/sources (T11.1)."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ketrika.alerts.notifier import send_pipeline_failure_email
from ketrika.api.main import app
from ketrika.connectors.base import Connector, DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.registry import _CONNECTOR_REGISTRY
from ketrika.connectors.runner import execute_connector_pipeline
from ketrika.core.db import check_db_connection
from ketrika.core.models.db import IngestionRun, Source
from ketrika.core.settings import get_settings
from ketrika.gold.refresh import refresh_gold_views
from ketrika.pipelines.definitions import handle_pipeline_failure
from tests.api_fixtures import login_test_admin


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


def clear_mailpit_messages() -> None:
    """Clear messages in local Mailpit instance."""
    try:
        httpx.delete("http://mailpit:8025/api/v1/messages", timeout=5)
    except Exception:
        pass


def get_mailpit_messages() -> list[dict[str, Any]]:
    """Retrieve all messages from Mailpit."""
    try:
        resp = httpx.get("http://mailpit:8025/api/v1/messages", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                msgs = data.get("messages", [])
                if isinstance(msgs, list):
                    return msgs
    except Exception:
        pass
    return []


class FailingConnector(Connector):
    """Dummy connector designed to raise a simulated error during discovery."""

    source_id = "failing_test_source"
    parser_version = "1.0.0"

    def discover(self, ctx: RunContext):
        raise RuntimeError("Forced simulation: upstream API 500 error")

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        raise NotImplementedError

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        raise NotImplementedError


@pytest.mark.integration
def test_send_pipeline_failure_email_direct():
    """Verify direct pipeline failure email reaches Mailpit."""
    clear_mailpit_messages()

    run_id = f"test-run-{uuid.uuid4().hex[:8]}"
    success = send_pipeline_failure_email(
        job_name="harvest_wfp_hdx",
        run_id=run_id,
        error_message="Simulated connection timeout while fetching HDX resource",
    )
    assert success is True

    messages = get_mailpit_messages()
    assert len(messages) >= 1
    matched = [m for m in messages if run_id[:8] in m.get("Subject", "")]
    assert len(matched) == 1
    assert "harvest_wfp_hdx" in matched[0]["Subject"]


@pytest.mark.integration
def test_forced_connector_failure_records_failed_and_dispatches_email(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Verify that a forced connector failure produces an email in Mailpit and status failed in /v1/sources."""
    clear_mailpit_messages()

    unique_source_id = f"dummy_failing_{uuid.uuid4().hex}"

    # Ensure source exists in meta.source
    src = Source(
        source_id=unique_source_id,
        spec={"name": "Failing Test Source", "priority": "P2", "freshness_sla_days": 15},
        status="active",
    )
    db_session.add(src)
    db_session.commit()

    class CustomFailingConnector(FailingConnector):
        source_id = unique_source_id

    monkeypatch.setitem(_CONNECTOR_REGISTRY, unique_source_id, CustomFailingConnector)
    connector = CustomFailingConnector()
    ctx = RunContext(source_id=unique_source_id)

    # 1. Execute pipeline which will fail
    with pytest.raises(RuntimeError, match="upstream API 500 error"):
        execute_connector_pipeline(connector, ctx, db_session)
    db_session.commit()

    # 2. Assert failure was saved in meta.ingestion_run
    failed_run = (
        db_session.query(IngestionRun)
        .filter(IngestionRun.source_id == unique_source_id)
        .order_by(IngestionRun.started_at.desc())
        .first()
    )
    assert failed_run is not None
    assert failed_run.status == "failed"
    assert failed_run.error == "RuntimeError"
    assert ctx.run_id == failed_run.run_id

    # 3. Assert an alert email was sent to Mailpit
    messages = get_mailpit_messages()
    assert len(messages) >= 1
    matched = [m for m in messages if str(failed_run.run_id)[:8] in m.get("Subject", "")]
    assert len(matched) >= 1
    assert unique_source_id in matched[0]["Subject"]

    # 4. Assert /v1/sources API returns latest_run_status == "failed"
    # Arrange the existing metadata-cache precondition explicitly. This does
    # not fix or qualify the no-cache API path tracked separately in BL-015.
    metadata = refresh_gold_views(db_session, views=["source_health"])
    assert metadata["views_refreshed"] == ["source_health"]
    assert metadata["source_observations_total"] == metadata["source_observations_valid"] == 0
    assert metadata["source_cell_rate"] is None
    db_session.commit()
    client = TestClient(app)
    login_test_admin(client)
    resp = client.get("/v1/sources")
    assert resp.status_code == 200
    sources_data = resp.json()
    source_entry = next((s for s in sources_data if s["source_id"] == unique_source_id), None)
    assert source_entry is not None
    assert source_entry["latest_run_status"] == "failed"


@pytest.mark.integration
def test_dagster_failure_sensor_execution():
    """Verify that Dagster failure sensor dispatches failure email upon failed run event."""
    clear_mailpit_messages()

    mock_context = MagicMock()
    mock_run_id = f"dagster-run-{uuid.uuid4().hex[:8]}"
    mock_context.dagster_run.run_id = mock_run_id
    mock_context.dagster_run.job_name = "gold_refresh_job"
    mock_context.failure_event.message = "PostgreSQL deadlock detected during gold refresh"

    # Call pipeline failure handler with mock Dagster context
    handle_pipeline_failure(mock_context)

    messages = get_mailpit_messages()
    assert len(messages) >= 1
    matched = [m for m in messages if mock_run_id[:8] in m.get("Subject", "")]
    assert len(matched) == 1
    assert "gold_refresh_job" in matched[0]["Subject"]
