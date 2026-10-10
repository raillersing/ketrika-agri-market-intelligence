"""Actual SQL selection and DQ rereads; object failures stay in memory."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from ketrika.core.db import get_session
from ketrika.core.models.db import DqResult, Source, SourceRecord
from ketrika.core.provenance_audit import (
    POLICIES,
    ObservationTarget,
    audit_observation_provenance,
)
from ketrika.core.qualification import require_synthetic_test_database
from tests.unit.test_provenance import MemoryReader
from tests.unit.test_provenance_audit import price_example


@pytest.mark.integration
def test_audit_persists_bound_results_and_missing_target_across_sessions():
    observation, content = price_example()
    source_id = f"test_provenance_{uuid4().hex}"
    digest = hashlib.sha256(content).hexdigest()
    key = f"{source_id}/2026/10/{digest}.json"
    reader = MemoryReader({key: content})
    target = ObservationTarget("price_observation", observation.observation_id)
    missing = ObservationTarget("price_observation", uuid4())
    with get_session() as session:
        url = session.get_bind().engine.url
        require_synthetic_test_database(url.host, url.database)
        session.add(
            Source(source_id=source_id, spec={"name": "Synthetic binding test"}, status="disabled")
        )
        session.flush()
        session.add(
            SourceRecord(
                source_record_id=observation.source_record_id,
                source_id=source_id,
                source_url="https://example.invalid/test-only",
                retrieved_via="direct",
                object_key=key,
                content_sha256=digest,
                mime_type="application/json",
                fetched_at=datetime.now(UTC),
                extraction_status="parsed",
                parser_version="test",
            )
        )
        session.flush()
        session.add(observation)
        session.flush()
        receipt = audit_observation_provenance(
            session, reader, mode="incremental", targets=[target, missing]
        )
        assert receipt.report.total == 2 and receipt.report.valid == 1
        assert not receipt.report.passed
        assert receipt.report.results[1].reason == "observation_missing"
        assert receipt.report.objects_read == 1
        dq_id = receipt.dq_id
    with get_session() as session:
        saved = session.get(DqResult, dq_id)
        assert saved is not None and not saved.passed
        assert saved.details["total_records"] == 2
        assert saved.details["valid_provenance"] == 1
        assert saved.details["mode"] == "incremental"
        assert saved.metric == 50
        assert saved.details["results"][0]["content_sha256"] == digest
        assert "3000" not in str(saved.details)
        assert "example.invalid" not in str(saved.details)
        unproven, _ = price_example()
        unproven.source_record_id = observation.source_record_id
        unproven.evidence = None
        session.add(unproven)
        session.flush()
        complete = audit_observation_provenance(session, reader)
        counts = {
            table: session.scalar(select(func.count()).select_from(policy.model))
            for table, policy in POLICIES.items()
        }
        assert complete.report.total == sum(counts.values())
        assert target in complete.targets
        assert session.get(DqResult, complete.dq_id).details["tables"] == list(POLICIES)
        assert ObservationTarget("price_observation", unproven.observation_id) in complete.targets
        assert not complete.report.passed  # The deliberately unproven row is not hidden.


@pytest.mark.integration
def test_audit_cannot_commit_or_use_ambiguous_scope():
    with get_session() as session:
        url = session.get_bind().engine.url
        require_synthetic_test_database(url.host, url.database)
        with pytest.raises(ValueError):
            audit_observation_provenance(session, MemoryReader({}), mode="incremental")
        with pytest.raises(ValueError):
            audit_observation_provenance(session, MemoryReader({}), targets=[])
        with pytest.raises(ValueError):
            audit_observation_provenance(
                session,
                MemoryReader({}),
                mode="incremental",
                targets=[ObservationTarget("unknown", uuid4())],
            )
        receipt = audit_observation_provenance(
            session,
            MemoryReader({}),
            mode="incremental",
            targets=[ObservationTarget("cpi_observation", uuid4())],
        )
        dq_id = receipt.dq_id
        assert receipt.report.valid == 0 and receipt.report.total == 1
        assert not receipt.report.passed
        session.rollback()
    with get_session() as session:
        assert session.get(DqResult, dq_id) is None
