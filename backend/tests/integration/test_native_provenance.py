"""Synthetic native coordinates and original JSON lexemes through SQL/MinIO."""

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.records import PriceRecord
from ketrika.connectors.runner import load_record_with_supersession
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import DqResult, PriceObservation, Source, SourceRecord
from ketrika.core.provenance_audit import ObservationTarget, audit_observation_provenance
from ketrika.core.qualification import require_synthetic_test_database
from tests.unit.test_provenance_audit import price_example


@pytest.mark.integration
@pytest.mark.parametrize("format_name", ["json", "csv"])
def test_native_cells_and_raw_rejection_persist_across_sessions(
    format_name: str, request: pytest.FixtureRequest
) -> None:
    candidate, content = price_example()
    assert candidate.evidence is not None
    if format_name == "json":
        content = content.replace(b'"3000.1250"', b"3000.1250")
        candidate.evidence["provenance"]["cells"][0]["raw_encoding"] = "json_number_lexeme"
        mime_type = "application/json"
    else:
        content = b"product,market,actor_level,period_start,period_end,price,unit,currency\nrice,synthetic-place,retail,2024-01-01,2024-01-01,3000.1250,kg,MGA\nmaize,other-place,retail,2024-01-01,2024-01-01,3000.1250,kg,MGA\n"
        mime_type = "text/csv"
    source_id, reference_id = "test-native-" + uuid4().hex, uuid4()
    with get_session() as session:
        url = session.get_bind().engine.url
        require_synthetic_test_database(url.host, url.database)
        reader = BronzeStore()
        assert reader.bucket == "ketrika-qa-bronze"
        session.add(
            Source(
                source_id=source_id,
                status="disabled",
                spec={"authenticity": "synthetic", "verified": False},
            )
        )
        session.flush()
        artifact = reader.put(
            source_id=source_id,
            content=content,
            mime_type=mime_type,
            url="https://example.invalid/synthetic-native",
            retrieved_via="manual_upload",
            fetched_at=datetime(2026, 10, 10, tzinfo=UTC),
            http_status=0,
            http_headers={"x-ketrika-dataset": "synthetic; verified=false"},
        )
        session.add(
            SourceRecord(
                source_record_id=reference_id,
                source_id=source_id,
                object_key=artifact.object_key,
                content_sha256=artifact.content_sha256,
                mime_type=mime_type,
                source_url="https://example.invalid/synthetic-native",
                retrieved_via="manual_upload",
                fetched_at=datetime.now(UTC),
                extraction_status="parsed",
                parser_version="synthetic-test",
            )
        )
        session.flush()
        if format_name == "csv":
            raw = RawArtifact(
                str(reference_id),
                artifact.object_key,
                artifact.content_sha256,
                mime_type,
                "https://example.invalid/synthetic-native",
                True,
            )
            parsed = DummyCsvConnector().parse(
                raw, RunContext(source_id=source_id, bronze_store=reader, offline=True)
            )
            assert len(parsed.records) == 2
            record = parsed.records[0]
            assert isinstance(record, PriceRecord)
            status, observation_id = load_record_with_supersession(
                session, record, source_id, reference_id
            )
            assert status == "inserted"
        else:
            candidate.source_record_id = reference_id
            session.add(candidate)
            session.flush()
            observation_id = candidate.observation_id
    with get_session() as session:
        stored = session.get(PriceObservation, observation_id)
        assert stored is not None and stored.price_raw == "3000.1250"
        assert stored.evidence is not None
        good = audit_observation_provenance(
            session,
            reader,
            mode="incremental",
            targets=[ObservationTarget("price_observation", observation_id)],
        )
        assert good.report.passed and good.report.valid == good.report.total == 1
        assert good.report.objects_read == 1
        rejected, _ = price_example()
        rejected.source_record_id = reference_id
        rejected.evidence = deepcopy(stored.evidence)
        if format_name == "json":
            rejected.price_raw = "3000.125"
            reason = "raw_value_mismatch"
        else:
            rejected.location_raw = stored.location_raw
            rejected.evidence["provenance"]["row"] = 1
            reason = "identity_mismatch"
        session.add(rejected)
        session.flush()
        bad = audit_observation_provenance(
            session,
            reader,
            mode="incremental",
            targets=[ObservationTarget("price_observation", rejected.observation_id)],
        )
        assert not bad.report.passed and bad.report.total == 1 and bad.report.valid == 0
        assert bad.report.results[0].reason == reason
        good_id, bad_id = good.dq_id, bad.dq_id
    with get_session() as session:
        for identifier, passed, valid in ((good_id, True, 1), (bad_id, False, 0)):
            saved = session.get(DqResult, identifier)
            assert saved is not None and saved.passed is passed
            assert saved.details is not None
            assert (
                saved.details["total_records"] == 1 and saved.details["valid_provenance"] == valid
            )
        request.node.user_properties.append(
            (
                "ketrika.native.provenance",
                f"synthetic SQL/MinIO only; format={format_name}; valid=1/1; rejected=0/1; persisted=true",
            )
        )
