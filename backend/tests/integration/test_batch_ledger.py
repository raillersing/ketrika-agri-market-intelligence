"""Real isolated SQL/S3 membership; no HTTP, active writes or crash claim."""

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ketrika.connectors.base import RawArtifact
from ketrika.connectors.batch_ledger import batch_digest, persist_bronze_batch, read_bronze_batch
from ketrika.connectors.stages import BronzeBatch
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import IngestionRun, Source, SourceRecord
from ketrika.core.models.ingestion_batch import IngestionBatch
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification import require_synthetic_test_database


def prepare(session: Session, *, empty: bool = False) -> BronzeBatch:
    target = session.get_bind().engine.url
    require_synthetic_test_database(target.host, target.database)
    source_id = "dummy_batch_" + uuid4().hex
    run_id, reference_id = uuid4(), uuid4()
    store = BronzeStore()
    assert store.bucket == "ketrika-qa-bronze"
    content = json.dumps(
        {"dataset": "synthetic", "verified": False, "source_id": source_id}
    ).encode()
    archived = store.put(
        source_id=source_id,
        content=content,
        mime_type="application/json",
        url="https://example.invalid/synthetic-batch",
        retrieved_via="manual_upload",
        fetched_at=datetime.now(UTC),
        http_status=0,
        http_headers={"x-ketrika-dataset": "synthetic;verified=false"},
    )
    assert (
        hashlib.sha256(BronzeProofReader(store).get(archived.object_key)).hexdigest()
        == archived.content_sha256
    )
    session.add(
        Source(source_id=source_id, status="disabled", spec={"synthetic": True, "verified": False})
    )
    session.flush()
    session.add(
        IngestionRun(
            run_id=run_id, source_id=source_id, started_at=datetime.now(UTC), status="running"
        )
    )
    session.add(
        SourceRecord(
            source_record_id=reference_id,
            source_id=source_id,
            source_url=archived.url,
            object_key=archived.object_key,
            content_sha256=archived.content_sha256,
            mime_type="application/json",
            fetched_at=datetime.now(UTC),
            parser_version="fixture-v1",
            extraction_status="pending",
            retrieved_via="manual_upload",
        )
    )
    session.flush()
    parent = session.get(SourceRecord, reference_id)
    assert parent is not None
    artifact = RawArtifact(
        str(reference_id),
        parent.object_key,
        parent.content_sha256,
        "application/json",
        parent.source_url,
        True,
    )
    return BronzeBatch(source_id, run_id, "fixture-v1", () if empty else (artifact,))


@pytest.mark.integration
@pytest.mark.parametrize("empty", [False, True])
def test_batch_survives_session_and_exact_retry_is_noop(empty: bool) -> None:
    with get_session() as session:
        batch = prepare(session, empty=empty)
        digest = persist_bronze_batch(session, batch)
        assert digest == batch_digest(batch)
    with get_session() as session:
        assert read_bronze_batch(session, batch.ingestion_run_id) == batch
        before = session.scalar(text("SELECT count(*) FROM meta.ingestion_batch_member"))
        assert persist_bronze_batch(session, batch) == digest
        assert session.scalar(text("SELECT count(*) FROM meta.ingestion_batch_member")) == before
        assert not session.dirty and not session.new and not session.deleted


@pytest.mark.integration
def test_members_roll_back_without_deleting_preexisting_parents() -> None:
    with get_session() as session:
        batch = prepare(session)
    with pytest.raises(RuntimeError, match="simulated_data_rollback"):
        with get_session() as session:
            persist_bronze_batch(session, batch)
            assert read_bronze_batch(session, batch.ingestion_run_id) == batch
            raise RuntimeError("simulated_data_rollback")
    with get_session() as session:
        assert session.get(IngestionBatch, batch.ingestion_run_id) is None
        assert session.get(SourceRecord, UUID(batch.artifacts[0].source_record_id)) is not None
        assert session.get(IngestionRun, batch.ingestion_run_id) is not None
        with pytest.raises(ValueError, match="batch_ledger_missing"):
            read_bronze_batch(session, batch.ingestion_run_id)


@pytest.mark.integration
def test_new_processing_version_preserves_acquisition_metadata() -> None:
    with get_session() as session:
        original = prepare(session)
    batch = replace(original, parser_version="fixture-v2")
    assert batch_digest(batch) != batch_digest(original)
    with get_session() as session:
        persist_bronze_batch(session, batch)
    with get_session() as session:
        assert read_bronze_batch(session, batch.ingestion_run_id) == batch
        parent = session.get(SourceRecord, UUID(batch.artifacts[0].source_record_id))
        assert parent is not None and parent.parser_version == "fixture-v1"
        assert not session.dirty and not session.new and not session.deleted


@pytest.mark.integration
def test_conflicting_repeat_and_wrong_parent_are_not_accepted() -> None:
    with get_session() as session:
        batch = prepare(session)
        persist_bronze_batch(session, batch)
    with get_session() as session:
        conflicting = replace(batch, artifacts=(replace(batch.artifacts[0], is_new=False),))
        with pytest.raises(ValueError, match="existing_mismatch"):
            persist_bronze_batch(session, conflicting)
        assert read_bronze_batch(session, batch.ingestion_run_id) == batch
        wrong_parent = replace(
            batch, artifacts=(replace(batch.artifacts[0], content_sha256="b" * 64),)
        )
        with pytest.raises(ValueError, match="reference_mismatch"):
            persist_bronze_batch(session, wrong_parent)
        assert read_bronze_batch(session, batch.ingestion_run_id) == batch


@pytest.mark.integration
@pytest.mark.parametrize("table", ["ingestion_batch", "ingestion_batch_member"])
@pytest.mark.parametrize("verb", ["UPDATE", "DELETE"])
def test_sql_mutation_of_persisted_members_is_refused(table: str, verb: str) -> None:
    with get_session() as session:
        batch = prepare(session)
        persist_bronze_batch(session, batch)
    with get_session() as session:
        query = (
            f"UPDATE meta.{table} SET run_id = run_id WHERE run_id = :run_id"
            if verb == "UPDATE"
            else f"DELETE FROM meta.{table} WHERE run_id = :run_id"
        )
        with pytest.raises(DBAPIError) as error:
            with session.begin_nested():
                session.execute(text(query), {"run_id": batch.ingestion_run_id})
        assert getattr(error.value.orig, "sqlstate", None) == "55000"
        assert read_bronze_batch(session, batch.ingestion_run_id) == batch


@pytest.mark.integration
def test_pending_parent_change_is_not_overwritten_by_refresh() -> None:
    with get_session() as session:
        batch = prepare(session)
        persist_bronze_batch(session, batch)
    with get_session() as session:
        run = session.get(IngestionRun, batch.ingestion_run_id)
        assert run is not None
        run.n_fetched = 73
        with pytest.raises(ValueError, match="pending_parent_changes"):
            read_bronze_batch(session, batch.ingestion_run_id)
        assert run.n_fetched == 73 and run in session.dirty
        session.rollback()


@pytest.mark.integration
def test_same_run_concurrent_writer_is_bounded_and_retry_remains_exact() -> None:
    with get_session() as session:
        batch = prepare(session)
        persist_bronze_batch(session, batch)
    with get_session() as owner:
        owner.execute(
            text("SELECT run_id FROM meta.ingestion_run WHERE run_id = :run_id FOR UPDATE"),
            {"run_id": batch.ingestion_run_id},
        )
        with pytest.raises(DBAPIError) as error:
            with get_session() as competitor:
                competitor.execute(text("SET LOCAL lock_timeout = '200ms'"))
                persist_bronze_batch(competitor, batch)
        assert getattr(error.value.orig, "sqlstate", None) == "55P03"
        assert read_bronze_batch(owner, batch.ingestion_run_id) == batch
    with get_session() as session:
        assert persist_bronze_batch(session, batch) == batch_digest(batch)
        assert read_bronze_batch(session, batch.ingestion_run_id) == batch
