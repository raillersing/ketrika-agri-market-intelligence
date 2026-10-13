"""Re-read corruption refusal with simulated SQL; no live receipt claim."""

from contextlib import contextmanager
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest

from ketrika.connectors.base import RawArtifact
from ketrika.connectors.batch_ledger import batch_digest
from ketrika.connectors.document_partitions import document_key
from ketrika.connectors.silver_attempts import read_success
from ketrika.connectors.stages import BronzeBatch


@pytest.fixture
def receipt(monkeypatch):
    artifact = RawArtifact(
        str(uuid4()),
        "dummy_receipt/2026/10/" + "a" * 64 + ".csv",
        "a" * 64,
        "text/csv",
        "https://example.invalid/synthetic",
        True,
    )
    batch = BronzeBatch("dummy_receipt", uuid4(), "fixture-v1", (artifact,))
    stats = {
        "n_fetched": 1,
        "n_new_artifacts": 1,
        "n_inserted": 3,
        "n_superseded": 0,
        "n_skipped": 0,
    }
    header = {
        "attempt_id": uuid4(),
        "batch_sha256": batch_digest(batch),
        "status": "success",
        "stats": stats,
        "run_status": "success",
        "n_fetched": 1,
        "n_new_artifacts": 1,
        "n_records": 3,
        "n_review": 0,
    }
    member = {
        "ordinal": 0,
        "source_record_id": UUID(artifact.source_record_id),
        "document_key": document_key(batch, artifact),
        "processing_key": None,
        "normalizer_version": None,
        "reference_manifest_sha256": None,
    }
    members = [member]
    session = Mock()
    header_result, member_result = Mock(), Mock()
    header_result.mappings.return_value.one_or_none.side_effect = lambda: header
    member_result.mappings.return_value.all.side_effect = lambda: members
    session.execute.side_effect = [header_result, member_result]

    @contextmanager
    def transaction():
        yield session

    monkeypatch.setattr("ketrika.connectors.silver_attempts.get_session", transaction)
    monkeypatch.setattr(
        "ketrika.connectors.silver_attempts.read_bronze_batch", Mock(return_value=batch)
    )
    return batch, header, members


def test_complete_receipt_returns_only_stored_stats(receipt):
    batch, header, _ = receipt
    assert read_success(batch) == header["stats"]


@pytest.mark.parametrize(
    "corruption",
    [
        "no_members",
        "ordinal",
        "reference",
        "document",
        "processing",
        "partial_identity",
        "missing_counter",
        "wrong_count",
        "run_running",
    ],
)
def test_incomplete_or_inconsistent_success_refused(receipt, corruption):
    batch, header, members = receipt
    if corruption == "no_members":
        members.clear()
    elif corruption == "ordinal":
        members[0]["ordinal"] = 1
    elif corruption == "reference":
        members[0]["source_record_id"] = uuid4()
    elif corruption == "document":
        members[0]["document_key"] = "b" * 64
    elif corruption == "processing":
        members[0].update(
            processing_key="b" * 64,
            normalizer_version="price_normalizer_v1",
            reference_manifest_sha256="a" * 64,
        )
    elif corruption == "partial_identity":
        members[0]["reference_manifest_sha256"] = "a" * 64
    elif corruption == "missing_counter":
        del header["stats"]["n_inserted"]
    elif corruption == "wrong_count":
        header["n_records"] = 4
    else:
        header["run_status"] = "running"
    with pytest.raises(ValueError, match="silver_attempt_"):
        read_success(batch)
