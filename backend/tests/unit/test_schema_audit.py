"""Synthetic structural measurement; SQL sessions and stores simulated here."""

import hashlib
import json
from unittest.mock import Mock
from uuid import uuid4

import pytest

from ketrika.core.models.db import SourceRecord
from ketrika.core.schema_audit import CSVSchemaContract, audit_source_schema
from ketrika.core.schema_json import JSONSchemaContract, JSONShape

CONTRACT = CSVSchemaContract("fixture-v1", ("product", "price"))
JSON_CONTRACT = JSONSchemaContract(
    "synthetic-json-v1",
    JSONShape(
        "object",
        properties=(("product", JSONShape("string"), True), ("price", JSONShape("string"), True)),
    ),
)


def example(content=b"product,price\nrice,3000\n", *, mime="text/csv"):
    sha = hashlib.sha256(content).hexdigest()
    record = SourceRecord(
        source_record_id=uuid4(),
        source_id="dummy_schema",
        object_key=f"dummy_schema/2026/10/{sha}.{'json' if mime == 'application/json' else 'csv'}",
        content_sha256=sha,
        mime_type=mime,
    )
    session = Mock()
    session.scalars.return_value.all.return_value = [record]
    reader = Mock()
    reader.get.return_value = content
    return session, reader, record


def test_valid_measurement_and_receipt_do_not_commit():
    session, reader, _ = example()
    receipt = audit_source_schema(session, reader, "dummy_schema", CONTRACT)
    assert receipt.report.passed and receipt.report.state == "verified"
    assert receipt.report.valid_artifacts == receipt.report.total_artifacts == 1
    assert receipt.report.objects_read == receipt.report.read_attempts == 1
    dq = session.add.call_args.args[0]
    assert dq.dq_id == receipt.dq_id and dq.check_name == "schema_drift"
    assert dq.metric == dq.threshold == 0
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "content,passed",
    [
        (b'{"product":"rice","price":"3000"}', True),
        (b'{"product":"rice","price":"3000","tool":"RUN_TOOL_NOW"}', False),
        (b'{"product":"rice"}', False),
        (b'{"product":"rice","price":true}', False),
    ],
)
def test_json_audit_uses_explicit_contract_and_fresh_sha(content, passed):
    session, reader, _ = example(content, mime="application/json")
    receipt = audit_source_schema(session, reader, "dummy_schema", JSON_CONTRACT)
    assert receipt.report.passed is passed
    assert receipt.report.total_artifacts == receipt.report.objects_read == 1
    assert receipt.report.valid_artifacts == int(passed)
    assert receipt.report.results[0]["contract_sha256"] == JSON_CONTRACT.sha256
    assert receipt.report.results[0]["contract_version"] == JSON_CONTRACT.version
    assert session.add.call_args.args[0].metric == int(not passed)
    assert "RUN_TOOL_NOW" not in json.dumps(receipt.report.results)
    reader.get.assert_called_once()
    session.commit.assert_not_called()


def test_json_contract_does_not_accept_csv_mime():
    session, reader, _ = example()
    receipt = audit_source_schema(session, reader, "dummy_schema", JSON_CONTRACT)
    assert not receipt.report.passed
    assert receipt.report.results[0]["state"] == "unknown"
    assert receipt.report.results[0]["reasons"] == ["schema_format_unsupported"]


def test_invalid_contract_rejected_before_sql():
    session, reader, _ = example()
    with pytest.raises(ValueError, match="invalid_contract"):
        audit_source_schema(session, reader, "dummy_schema", {"guessed": "schema"})
    session.scalars.assert_not_called()
    reader.get.assert_not_called()


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b"product,price,new\nrice,3000,instruction\n", "schema_unexpected_columns"),
        (b"product\nrice\n", "schema_missing_columns"),
        (b"product,price\nrice,3000,extra\n", "schema_invalid_row_width"),
        (b"", "schema_header_absent"),
    ],
)
def test_drift_or_unknown_cannot_pass(content, reason):
    session, reader, _ = example(content)
    receipt = audit_source_schema(session, reader, "dummy_schema", CONTRACT)
    assert not receipt.report.passed and receipt.report.valid_artifacts == 0
    assert reason in receipt.report.results[0]["reasons"]
    assert session.add.call_args.args[0].metric == 1


@pytest.mark.parametrize(
    "mode", ["no_contract", "wrong_mime", "corrupt", "unreadable", "not_bytes"]
)
def test_refusals_are_explicit(mode):
    session, reader, _ = example(mime="application/json" if mode == "wrong_mime" else "text/csv")
    contract = None if mode == "no_contract" else CONTRACT
    if mode == "corrupt":
        reader.get.return_value = b"wrong bytes"
    elif mode == "unreadable":
        reader.get.side_effect = RuntimeError("untrusted detail")
    elif mode == "not_bytes":
        reader.get.return_value = "not bytes"
    report = audit_source_schema(session, reader, "dummy_schema", contract).report
    assert not report.passed and report.valid_artifacts == 0
    assert "untrusted detail" not in json.dumps(report.results)


def test_empty_is_failed_and_metric_is_null():
    session, reader, _ = example()
    session.scalars.return_value.all.return_value = []
    report = audit_source_schema(session, reader, "dummy_schema", CONTRACT).report
    assert not report.passed and report.state == "empty"
    assert report.total_artifacts == report.objects_read == report.read_attempts == 0
    assert session.add.call_args.args[0].metric is None
    reader.get.assert_not_called()


def test_invalid_reference_never_reads_object():
    session, reader, record = example()
    record.object_key = "outside/source.csv"
    report = audit_source_schema(session, reader, "dummy_schema", CONTRACT).report
    assert not report.passed and report.read_attempts == 0
    reader.get.assert_not_called()


def test_duplicate_object_is_read_once_but_both_references_measured():
    session, reader, record = example()
    second = SourceRecord(
        source_record_id=uuid4(),
        source_id=record.source_id,
        object_key=record.object_key,
        content_sha256=record.content_sha256,
        mime_type=record.mime_type,
    )
    session.scalars.return_value.all.return_value.append(second)
    report = audit_source_schema(session, reader, "dummy_schema", CONTRACT).report
    assert report.passed and report.valid_artifacts == report.total_artifacts == 2
    assert report.objects_read == report.read_attempts == 1
    reader.get.assert_called_once()


def test_sql_failure_propagates_without_receipt():
    session, reader, _ = example()
    session.scalars.side_effect = RuntimeError("simulated SQL")
    with pytest.raises(RuntimeError):
        audit_source_schema(session, reader, "dummy_schema", CONTRACT)
    session.add.assert_not_called()


def test_artifact_bound_refuses_not_truncates(monkeypatch):
    session, reader, _ = example()
    monkeypatch.setattr("ketrika.core.schema_audit.MAX_ARTIFACTS", 0)
    with pytest.raises(ValueError, match="outside_bounds"):
        audit_source_schema(session, reader, "dummy_schema", CONTRACT)
    reader.get.assert_not_called()


def test_object_bound_refuses_even_without_contract(monkeypatch):
    session, reader, _ = example()
    monkeypatch.setattr("ketrika.core.schema_audit.MAX_BYTES", 1)
    report = audit_source_schema(session, reader, "dummy_schema", None).report
    assert not report.passed and report.objects_read == report.read_attempts == 1
    assert report.results[0]["reasons"] == ["schema_artifact_outside_bounds"]


@pytest.mark.parametrize("version", ["", " v1", "v" * 129])
def test_invalid_contract_version_refused(version):
    with pytest.raises(ValueError, match="invalid_version"):
        CSVSchemaContract(version, ("product", "price"))
