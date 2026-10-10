"""Actual SQL selection and DQ rereads; object failures stay in memory."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from ketrika.core.bronze import BronzeStore
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
def test_audit_persists_bound_results_and_missing_target_across_sessions(
    request: pytest.FixtureRequest,
):
    observation, content = price_example()
    source_id = f"test_provenance_{uuid4().hex}"
    digest = hashlib.sha256(content).hexdigest()
    key = f"{source_id}/2026/10/{digest}.json"
    target = ObservationTarget("price_observation", observation.observation_id)
    missing = ObservationTarget("price_observation", uuid4())
    with get_session() as session:
        url = session.get_bind().engine.url
        require_synthetic_test_database(url.host, url.database)
        reader = BronzeStore()
        assert reader.bucket == "ketrika-qa-bronze"
        artifact = reader.put(
            source_id=source_id,
            content=content,
            mime_type="application/json",
            url="https://example.invalid/test-only",
            retrieved_via="manual_upload",
            fetched_at=datetime(2026, 10, 10, tzinfo=UTC),
            http_status=0,
            http_headers={"x-ketrika-dataset": "synthetic; verified=false"},
        )
        assert artifact.object_key == key and artifact.content_sha256 == digest
        session.add(
            Source(
                source_id=source_id,
                spec={
                    "name": "Synthetic binding test",
                    "authenticity": "synthetic",
                    "verified": False,
                },
                status="disabled",
            )
        )
        session.flush()
        session.add(
            SourceRecord(
                source_record_id=observation.source_record_id,
                source_id=source_id,
                source_url="https://example.invalid/test-only",
                retrieved_via="manual_upload",
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
        assert saved.details is not None
        assert saved.details["total_records"] == 2
        assert saved.details["valid_provenance"] == 1
        assert saved.details["mode"] == "incremental"
        assert saved.metric == 50
        assert saved.details["results"][0]["content_sha256"] == digest
        assert all(
            set(result)
            == {
                "table",
                "observation_id",
                "source_record_id",
                "passed",
                "reason",
                "object_key",
                "content_sha256",
            }
            for result in saved.details["results"]
        )
        request.node.user_properties.append(
            (
                "ketrika.provenance.incremental",
                json.dumps(
                    {
                        "dq_id": str(saved.dq_id),
                        "mode": "incremental",
                        "valid": 1,
                        "total": 2,
                        "passed": False,
                        "objects_read": 1,
                        "backend": "isolated MinIO + SQL",
                        "dataset": "synthetic; never market qualification",
                    }
                ),
            )
        )
        unproven, _ = price_example()
        unproven.source_record_id = observation.source_record_id
        unproven.evidence = None
        session.add(unproven)
        session.flush()
        complete = audit_observation_provenance(session, reader)
        counts: dict[str, int] = {}
        for table, policy in POLICIES.items():
            count = session.scalar(select(func.count()).select_from(policy.model))
            assert count is not None
            counts[table] = count
        assert complete.report.total == sum(counts.values())
        assert target in complete.targets
        complete_dq = session.get(DqResult, complete.dq_id)
        assert complete_dq is not None and complete_dq.details is not None
        assert complete_dq.details["tables"] == list(POLICIES)
        assert ObservationTarget("price_observation", unproven.observation_id) in complete.targets
        assert not complete.report.passed  # The deliberately unproven row is not hidden.
        request.node.user_properties.append(
            (
                "ketrika.provenance.complete",
                json.dumps(
                    {
                        "dq_id": str(complete.dq_id),
                        "mode": "complete",
                        "valid": complete.report.valid,
                        "total": complete.report.total,
                        "passed": complete.report.passed,
                        "objects_read": complete.report.objects_read,
                        "tables": counts,
                        "dataset": "synthetic; never market qualification",
                    }
                ),
            )
        )


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
