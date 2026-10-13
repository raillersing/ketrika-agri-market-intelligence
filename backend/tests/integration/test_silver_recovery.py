"""Isolated real SQL/S3, including a killed worker; no institutional HTTP."""

import hashlib
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from ketrika.connectors.base import DiscoveredItem, RawArtifact, RunContext
from ketrika.connectors.batch_ledger import read_bronze_batch
from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.durable_phases import (
    DurablePhaseFailure,
    execute_durable_bronze,
    execute_durable_silver,
    resume_durable_silver,
)
from ketrika.connectors.registry import _CONNECTOR_REGISTRY
from ketrika.connectors.silver_attempts import SilverRunBusy, exclusive_silver_run
from ketrika.core.artifact_identity import ArtifactProcessingIdentity
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import IngestionRun, PriceObservation, Source, SourceRecord
from ketrika.core.qualification import require_synthetic_test_database
from tests.integration.test_connector_pipeline import CSV_V1


@pytest.fixture
def recovery_case(monkeypatch):
    identifier = "dummy_recovery_" + uuid4().hex
    with get_session() as session:
        target = session.get_bind().engine.url
        require_synthetic_test_database(target.host, target.database)
        session.add(
            Source(
                source_id=identifier,
                status="disabled",
                spec={
                    "dataset": "synthetic",
                    "verified": False,
                },
            )
        )
    store = BronzeStore()
    assert store.bucket == "ketrika-qa-bronze"
    archived = store.put(
        source_id=identifier,
        content=CSV_V1.encode(),
        mime_type="text/csv",
        url="https://example.invalid/synthetic-recovery",
        retrieved_via="manual_upload",
        fetched_at=datetime.now(UTC),
        http_status=0,
        http_headers={"x-ketrika-dataset": "synthetic;verified=false"},
    )
    raw = RawArtifact(
        str(uuid4()),
        archived.object_key,
        archived.content_sha256,
        "text/csv",
        archived.url,
        archived.is_new,
    )
    calls = {"fetch": 0, "parse": 0}

    class Fixture(DummyCsvConnector):
        source_id = identifier

        def discover(self, ctx):
            yield DiscoveredItem(url=raw.url)

        def fetch(self, item, ctx):
            calls["fetch"] += 1
            return raw

        def parse(self, artifact, ctx):
            calls["parse"] += 1
            assert ctx.offline
            return super().parse(artifact, ctx)

    monkeypatch.setitem(_CONNECTOR_REGISTRY, identifier, Fixture)
    connector = Fixture()
    context = RunContext(source_id=identifier, bronze_store=store)
    batch = execute_durable_bronze(connector, context)
    assert calls == {"fetch": 1, "parse": 0}
    return connector, context, batch, calls


def observed_count(source_id):
    with get_session() as session:
        return session.scalar(
            select(func.count())
            .select_from(PriceObservation)
            .join(SourceRecord)
            .where(SourceRecord.source_id == source_id)
        )


def history(run_id):
    with get_session() as session:
        return (
            session.execute(
                text(
                    "SELECT a.attempt_id, a.batch_sha256, a.resumed_from, r.status, r.stats, r.error_class "
                    "FROM meta.silver_attempt a LEFT JOIN meta.silver_attempt_result r USING(attempt_id) "
                    "WHERE a.run_id=:run"
                ),
                {"run": run_id},
            )
            .mappings()
            .one_or_none()
        )


@pytest.mark.integration
def test_success_receipt_atomic_and_repeat_does_not_parse(recovery_case):
    connector, ctx, batch, calls = recovery_case
    first = execute_durable_silver(connector, ctx, batch)
    assert first["n_inserted"] == 3
    assert execute_durable_silver(connector, ctx, batch) == first
    assert calls == {"fetch": 1, "parse": 1}
    assert observed_count(batch.source_id) == 3
    receipt = history(batch.ingestion_run_id)
    assert receipt is not None and receipt["status"] == "success"
    assert receipt["stats"] == first and receipt["error_class"] is None
    with get_session() as session:
        member = (
            session.execute(
                text("SELECT * FROM meta.silver_attempt_member WHERE attempt_id=:id"),
                {"id": receipt["attempt_id"]},
            )
            .mappings()
            .one()
        )
        assert (
            member["ordinal"] == 0
            and str(member["source_record_id"]) == batch.artifacts[0].source_record_id
        )
        identity = ArtifactProcessingIdentity(
            batch.source_id,
            member["source_record_id"],
            batch.artifacts[0].content_sha256,
            batch.parser_version,
            member["normalizer_version"],
            member["reference_manifest_sha256"],
        )
        assert identity.processing_key == member["processing_key"]
        prices = session.scalars(
            select(PriceObservation)
            .join(SourceRecord)
            .where(SourceRecord.source_id == batch.source_id)
        ).all()
        assert len(prices) == 3
        for price in prices:
            assert price.evidence is not None
            assert (
                price.evidence["normalization"]["reference_snapshot"]["sha256"]
                == identity.reference_manifest_sha256
            )
    with pytest.raises(ValueError, match="silver_resume_terminal_success"):
        resume_durable_silver(connector, ctx, batch.ingestion_run_id)


@pytest.mark.integration
def test_failure_after_real_insert_rolls_back_and_resume_preserves_history(
    recovery_case, monkeypatch
):
    from ketrika.normalize.price_loader import load_normalized_price

    connector, ctx, batch, calls = recovery_case

    def fail_after_insert(session, *args, **kwargs):
        result = load_normalized_price(session, *args, **kwargs)
        assert result.action == "inserted"
        assert (
            session.scalar(
                select(func.count())
                .select_from(PriceObservation)
                .join(SourceRecord)
                .where(SourceRecord.source_id == batch.source_id)
            )
            == 1
        )
        raise RuntimeError("UNTRUSTED_RUN_TOOL_NOW")

    monkeypatch.setattr("ketrika.normalize.price_loader.load_normalized_price", fail_after_insert)
    with pytest.raises(DurablePhaseFailure, match="^silver:RuntimeError$"):
        execute_durable_silver(connector, ctx, batch)
    assert observed_count(batch.source_id) == 0
    before = dict(history(batch.ingestion_run_id))
    assert before["status"] == "failed" and before["error_class"] == "RuntimeError"
    assert before["stats"] is None
    monkeypatch.setattr(
        "ketrika.normalize.price_loader.load_normalized_price", load_normalized_price
    )
    resumed = resume_durable_silver(connector, ctx, batch.ingestion_run_id)
    assert resumed["n_inserted"] == 3 and observed_count(batch.source_id) == 3
    assert dict(history(batch.ingestion_run_id)) == before
    assert calls == {"fetch": 1, "parse": 2}
    with get_session() as session:
        original = session.get(IngestionRun, batch.ingestion_run_id)
        assert original is not None and original.status == "failed"
        new_run = session.scalar(
            text("SELECT run_id FROM meta.silver_attempt WHERE resumed_from=:run"),
            {"run": batch.ingestion_run_id},
        )
        assert new_run is not None and new_run != batch.ingestion_run_id
        assert read_bronze_batch(session, new_run).artifacts == batch.artifacts
    assert (
        hashlib.sha256(ctx.bronze_store.get(batch.artifacts[0].object_key)).hexdigest()
        == batch.artifacts[0].content_sha256
    )


@pytest.mark.integration
def test_active_owner_is_refused_without_failed_receipt(recovery_case):
    connector, ctx, batch, calls = recovery_case
    with exclusive_silver_run(batch.ingestion_run_id):
        with pytest.raises(SilverRunBusy, match="silver_run_busy"):
            execute_durable_silver(connector, ctx, batch)
        with pytest.raises(SilverRunBusy, match="silver_run_busy"):
            resume_durable_silver(connector, ctx, batch.ingestion_run_id)
    assert history(batch.ingestion_run_id) is None
    assert calls == {"fetch": 1, "parse": 0}
    with get_session() as session:
        original = session.get(IngestionRun, batch.ingestion_run_id)
        assert original is not None and original.status == "running"
    assert execute_durable_silver(connector, ctx, batch)["n_inserted"] == 3


@pytest.mark.integration
@pytest.mark.parametrize("change", ["parser", "is_new"])
def test_recorded_batch_mismatch_refused_before_intention_or_parse(recovery_case, change):
    connector, ctx, batch, calls = recovery_case
    altered = (
        replace(batch, parser_version="wrong-v1")
        if change == "parser"
        else replace(batch, artifacts=(replace(batch.artifacts[0], is_new=False),))
    )
    if change == "parser":
        connector.parser_version = altered.parser_version
    with pytest.raises(ValueError, match="silver_recorded_batch_mismatch"):
        execute_durable_silver(connector, ctx, altered)
    assert history(batch.ingestion_run_id) is None
    assert observed_count(batch.source_id) == 0 and calls["parse"] == 0


@pytest.mark.integration
def test_different_native_runs_for_one_source_cannot_insert_concurrently(recovery_case):
    connector, ctx, first, calls = recovery_case
    second = execute_durable_bronze(connector, ctx)
    assert second.ingestion_run_id != first.ingestion_run_id
    with exclusive_silver_run(first.ingestion_run_id, first.source_id):
        with pytest.raises(SilverRunBusy, match="silver_run_busy"):
            execute_durable_silver(connector, ctx, second)
    assert history(second.ingestion_run_id) is None
    assert calls == {"fetch": 2, "parse": 0}
    assert execute_durable_silver(connector, ctx, first)["n_inserted"] == 3
    retried = execute_durable_silver(connector, ctx, second)
    assert retried["n_inserted"] == 0 and retried["n_skipped"] == 3
    assert observed_count(first.source_id) == 3


@pytest.mark.integration
@pytest.mark.parametrize(
    "table", ["silver_attempt", "silver_attempt_result", "silver_attempt_member"]
)
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_attempt_history_immutable(recovery_case, table, operation):
    connector, ctx, batch, _ = recovery_case
    execute_durable_silver(connector, ctx, batch)
    receipt = history(batch.ingestion_run_id)
    assert receipt is not None
    statement = (
        f"UPDATE meta.{table} SET attempt_id=attempt_id WHERE attempt_id=:id"
        if operation == "UPDATE"
        else f"DELETE FROM meta.{table} WHERE attempt_id=:id"
    )
    with pytest.raises(DBAPIError) as captured:
        with get_session() as session:
            session.execute(text(statement), {"id": receipt["attempt_id"]})
    assert captured.value.orig.sqlstate == "55000"
    assert history(batch.ingestion_run_id) == receipt


@pytest.mark.integration
def test_actual_process_exit_after_insert_leaves_unknown_then_resume(recovery_case):
    connector, ctx, batch, calls = recovery_case
    # Child has its own engine and connections; os._exit skips Python rollback/finally.
    code = """
import os, sys
from uuid import UUID
from ketrika.core.db import get_session
from ketrika.core.bronze import BronzeStore
from ketrika.connectors.base import RunContext
from ketrika.connectors.batch_ledger import read_bronze_batch
from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.durable_phases import execute_durable_silver
from ketrika.core.qualification import require_synthetic_test_database
from sqlalchemy import select, func
from ketrika.core.models.db import PriceObservation, SourceRecord
import ketrika.normalize.price_loader as loader
with get_session() as session:
    target = session.get_bind().engine.url
    require_synthetic_test_database(target.host, target.database)
    batch = read_bronze_batch(session, UUID(sys.argv[1]))
original = loader.load_normalized_price
def insert_then_exit(session, *args, **kwargs):
    loaded = original(session, *args, **kwargs)
    assert loaded.action == 'inserted'
    count = session.scalar(select(func.count()).select_from(PriceObservation).join(SourceRecord)
                           .where(SourceRecord.source_id == batch.source_id))
    assert count == 1
    os._exit(91)
loader.load_normalized_price = insert_then_exit
connector = DummyCsvConnector()
connector.source_id = batch.source_id
execute_durable_silver(connector, RunContext(source_id=batch.source_id, bronze_store=BronzeStore()), batch)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(batch.ingestion_run_id)], capture_output=True, timeout=90
    )
    assert result.returncode == 91, result.stderr.decode(errors="replace")
    assert observed_count(batch.source_id) == 0
    before = dict(history(batch.ingestion_run_id))
    assert before["status"] is None and before["stats"] is None
    with pytest.raises(ValueError, match="silver_attempt_exists_resume_required"):
        execute_durable_silver(connector, ctx, batch)
    resumed = resume_durable_silver(connector, ctx, batch.ingestion_run_id)
    assert resumed["n_inserted"] == 3 and observed_count(batch.source_id) == 3
    assert dict(history(batch.ingestion_run_id)) == before
    assert calls == {"fetch": 1, "parse": 1}
    with get_session() as session:
        original = session.get(IngestionRun, batch.ingestion_run_id)
        assert original is not None and original.status == "running"
        assert original.finished_at is None
