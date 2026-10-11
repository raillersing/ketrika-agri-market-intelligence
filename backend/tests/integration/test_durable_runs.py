"""Prepared real rollback test; no main-check concurrency or pipeline claim."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from ketrika.connectors.durable_runs import (
    create_durable_ingestion_run,
    persist_durable_run_failure,
)
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import IngestionRun, PriceObservation, Source, SourceRecord
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification import require_synthetic_test_database
from tests.unit.test_provenance_audit import price_example


def prepare_source():
    source_id = f"dummy_durable_{uuid4().hex}"
    with get_session() as session:
        target = session.get_bind().engine.url
        require_synthetic_test_database(target.host, target.database)
        session.add(
            Source(
                source_id=source_id,
                status="disabled",
                spec={"dataset": "synthetic", "verified": False},
            )
        )
    return source_id


def price_signature(session):
    return session.execute(
        text(
            "SELECT count(*), md5(coalesce(string_agg(to_jsonb(p)::text, ',' "
            "ORDER BY observation_id), '')) FROM obs.price_observation p"
        )
    ).one()


@pytest.mark.integration
def test_failure_metadata_survives_data_rollback_and_retry(request):
    source_id = prepare_source()
    store = BronzeStore()
    assert store.bucket == "ketrika-qa-bronze"
    observation, content = price_example()
    artifact = store.put(
        source_id=source_id,
        content=content,
        mime_type="application/json",
        url="https://example.invalid/synthetic-durable-run",
        retrieved_via="manual_upload",
        fetched_at=datetime.now(UTC),
        http_status=0,
        http_headers={"x-ketrika-dataset": "synthetic;verified=false"},
    )
    with get_session() as session:
        session.add(
            SourceRecord(
                source_record_id=observation.source_record_id,
                source_id=source_id,
                source_url="https://example.invalid/synthetic-durable-run",
                object_key=artifact.object_key,
                content_sha256=artifact.content_sha256,
                mime_type="application/json",
                retrieved_via="manual_upload",
                fetched_at=datetime.now(UTC),
                parser_version="fixture-v1",
                extraction_status="pending",
            )
        )
        signature = price_signature(session)
    reference = create_durable_ingestion_run(source_id, str(uuid4()))
    with pytest.raises(RuntimeError, match="UNTRUSTED_COLLECTED_MESSAGE"):
        with get_session() as data_session:
            run = data_session.get(IngestionRun, reference.run_id)
            assert run is not None and run.status == "running"
            run.n_records = 42
            data_session.add(observation)
            data_session.flush()
            assert data_session.get(PriceObservation, observation.observation_id) is not None
            raise RuntimeError("UNTRUSTED_COLLECTED_MESSAGE")
    assert persist_durable_run_failure(reference, RuntimeError) == reference.run_id
    with get_session() as session:
        failed = session.get(IngestionRun, reference.run_id)
        assert failed is not None and failed.status == "failed"
        assert failed.error == "RuntimeError" and failed.n_records == 0
        assert failed.finished_at is not None
        finished = failed.finished_at
        assert session.get(PriceObservation, observation.observation_id) is None
        assert price_signature(session) == signature
    assert persist_durable_run_failure(reference, RuntimeError) == reference.run_id
    with get_session() as session:
        retried = session.get(IngestionRun, reference.run_id)
        assert retried is not None and retried.finished_at == finished
        assert price_signature(session) == signature
    assert (
        hashlib.sha256(BronzeProofReader(store).get(artifact.object_key)).hexdigest()
        == artifact.content_sha256
    )
    request.node.user_properties.append(
        (
            "ketrika.run.durable",
            json.dumps(
                {
                    "run_id": str(reference.run_id),
                    "status": "failed",
                    "error_class_only": True,
                    "rolled_back_observation_absent": True,
                    "price_signature_unchanged": True,
                    "bronze_sha_unchanged": True,
                    "retry_keeps_finish_time": True,
                    "scope": "independent metadata helpers with actual rollback; not pipeline/assets/ledger/DQ durability",
                }
            ),
        )
    )


@pytest.mark.integration
def test_successful_run_cannot_be_replaced_by_failure():
    source_id = prepare_source()
    reference = create_durable_ingestion_run(source_id)
    with get_session() as session:
        run = session.get(IngestionRun, reference.run_id)
        assert run is not None
        run.status, run.finished_at = "success", datetime.now(UTC)
        finished = run.finished_at
    with pytest.raises(ValueError, match="already_terminal"):
        persist_durable_run_failure(reference, RuntimeError)
    with get_session() as session:
        preserved = session.get(IngestionRun, reference.run_id)
        assert preserved is not None and preserved.status == "success"
        assert preserved.finished_at == finished and preserved.error is None
