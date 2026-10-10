"""Pure verifier regressions; all in-memory objects are test-only, not live sources."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import replace
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from ketrika.core.provenance import (
    ArtifactReference,
    ObservationClaim,
    ProofError,
    ProvenanceVerifier,
    verify_cells,
)

CONTENT = b'[{"product":"rice","period":"2024-01","price":3000.1250},{"product":"maize","period":"2024-02","price":3000.1250}]'
SHA = hashlib.sha256(CONTENT).hexdigest()
KEY = f"test_source/2026/10/{SHA}.json"


def proof() -> dict[str, Any]:
    return {
        "version": 1,
        "format": "json",
        "scope_path": [0],
        "cells": [
            {
                "field": "price_value",
                "role": "value",
                "kind": "number",
                "path": [0, "price"],
                "expected": "3000.1250",
            },
            {
                "field": "product_raw",
                "role": "identity",
                "kind": "text",
                "path": [0, "product"],
                "expected": "rice",
            },
            {
                "field": "period",
                "role": "identity",
                "kind": "text",
                "path": [0, "period"],
                "expected": "2024-01",
            },
        ],
    }


def csv_proof() -> dict[str, Any]:
    result = proof()
    result.update({"format": "csv", "row": 0, "delimiter": ","})
    result.pop("scope_path")
    for cell in result["cells"]:
        cell["column"] = cell.pop("path")[-1]
    return result


class MemoryReader:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects
        self.calls: list[str] = []

    def get(self, key: str) -> bytes:
        self.calls.append(key)
        if key not in self.objects:
            raise RuntimeError("secret password in simulated SDK exception")
        return self.objects[key]


def example() -> tuple[ProvenanceVerifier, MemoryReader, ArtifactReference, ObservationClaim]:
    reference = ArtifactReference(uuid4(), "test_source", KEY, SHA, "application/json")
    reader = MemoryReader({KEY: CONTENT})
    verifier = ProvenanceVerifier(reader, {reference.source_record_id: reference})
    return (
        verifier,
        reader,
        reference,
        ObservationClaim(uuid4(), reference.source_record_id, proof()),
    )


def test_recomputed_bytes_and_decimal_cells() -> None:
    verifier, reader, _, claim = example()
    report = verifier.verify([claim])
    assert report.passed and report.valid == report.total == 1
    assert report.rate == Decimal(100)
    assert report.objects_read == report.object_read_attempts == 1
    assert reader.calls == [KEY]
    assert report.results[0].content_sha256 == SHA


def test_shared_object_is_read_once_and_cache_is_not_a_receipt() -> None:
    verifier, reader, _, claim = example()
    second = replace(claim, observation_id=uuid4())
    report = verifier.verify([claim, second], "incremental")
    assert report.total == report.valid == 2 and report.objects_read == 1
    assert report.mode == "incremental"
    reader.objects[KEY] = b"changed after first batch"
    next_report = verifier.verify([claim])
    assert reader.calls == [KEY, KEY]
    assert not next_report.passed and next_report.results[0].reason == "sha256_mismatch"


def test_missing_object_is_not_valid_and_error_is_redacted() -> None:
    verifier, reader, _, claim = example()
    reader.objects.clear()
    report = verifier.verify([claim, replace(claim, observation_id=uuid4())])
    assert report.valid == 0 and report.total == 2 and not report.passed
    assert report.objects_read == 0 and report.object_read_attempts == 1
    assert {result.reason for result in report.results} == {"object_unavailable"}
    assert "secret" not in repr(report) and "password" not in repr(report)


def test_missing_or_mismatched_foreign_reference() -> None:
    verifier, reader, reference, claim = example()
    for foreign in (None, uuid4()):
        result = verifier.verify([replace(claim, source_record_id=foreign)])
        assert not result.passed and result.results[0].reason == "source_record_missing"
    verifier.references = {reference.source_record_id: replace(reference, source_record_id=uuid4())}
    assert verifier.verify([claim]).results[0].reason == "source_record_missing"
    assert reader.calls == []


@pytest.mark.parametrize("digest", ["pseudo_sha", "0" * 63, "g" * 64])
def test_pseudo_hashes_refused(digest: str) -> None:
    verifier, reader, reference, claim = example()
    verifier.references = {reference.source_record_id: replace(reference, content_sha256=digest)}
    assert verifier.verify([claim]).results[0].reason == "invalid_sha256"
    assert reader.calls == []


@pytest.mark.parametrize(
    "key",
    [
        "../escape",
        f"bronze/{KEY}",
        KEY.replace("/10/", "/13/"),
        KEY.replace("/2026/", "/0000/"),
        KEY.replace(SHA, "0" * 64),
    ],
)
def test_non_content_addressed_keys_refused(key: str) -> None:
    verifier, reader, reference, claim = example()
    verifier.references = {reference.source_record_id: replace(reference, object_key=key)}
    assert verifier.verify([claim]).results[0].reason == "invalid_object_key"
    assert reader.calls == []


def test_empty_batch_and_duplicate_observation_never_certify() -> None:
    verifier, _, _, claim = example()
    empty = verifier.verify([])
    assert empty.total == empty.valid == 0 and not empty.passed and empty.rate is None
    duplicate = verifier.verify([claim, claim])
    assert not duplicate.passed and duplicate.rate == Decimal(50)
    assert duplicate.results[1].reason == "duplicate_observation"
    with pytest.raises(ValueError, match="Unsupported verification mode"):
        verifier.verify([], "other")  # type: ignore[arg-type]


def test_wrong_line_with_same_number_still_fails_identity() -> None:
    evidence = proof()
    evidence["scope_path"] = [1]
    for cell in evidence["cells"]:
        cell["path"][0] = 1
    with pytest.raises(ProofError, match="identity_mismatch"):
        verify_cells(CONTENT, "application/json", evidence)


def test_cell_cannot_escape_record_scope() -> None:
    evidence = proof()
    evidence["cells"][0]["path"][0] = 1
    with pytest.raises(ProofError, match="cell_outside_record"):
        verify_cells(CONTENT, "application/json", evidence)


@pytest.mark.parametrize("path", [[], [-1], [True], [None], [0, 0], [999], [0, "absent"]])
def test_bad_json_coordinates(path: list[Any]) -> None:
    evidence = proof()
    evidence["cells"][0]["path"] = path
    with pytest.raises(ProofError):
        verify_cells(CONTENT, "application/json", evidence)


@pytest.mark.parametrize(
    "change",
    [
        {"version": True},
        {"version": 2},
        {"cells": None},
        {"cells": []},
        {"cells": ["untrusted"]},
        {"format": "pdf"},
        {"scope_path": []},
    ],
)
def test_bad_proof_refused(change: dict[str, Any]) -> None:
    evidence = proof() | change
    with pytest.raises(ProofError):
        verify_cells(CONTENT, "application/json", evidence)


@pytest.mark.parametrize(
    "change",
    [
        {"role": None},
        {"role": []},
        {"role": "instruction"},
        {"field": ""},
        {"expected": 3000.125},
        {"kind": "instruction"},
        {"expected": "3001"},
    ],
)
def test_bad_cell_refused(change: dict[str, Any]) -> None:
    evidence = proof()
    evidence["cells"][0].update(change)
    with pytest.raises(ProofError):
        verify_cells(CONTENT, "application/json", evidence)


def test_duplicate_fields_and_coordinates_refused() -> None:
    evidence = proof()
    evidence["cells"].append(copy.deepcopy(evidence["cells"][0]))
    with pytest.raises(ProofError, match="invalid_field"):
        verify_cells(CONTENT, "application/json", evidence)
    evidence["cells"][-1]["field"] = "other_value"
    with pytest.raises(ProofError, match="duplicate_cell"):
        verify_cells(CONTENT, "application/json", evidence)


@pytest.mark.parametrize("content", [b"not json", b"\xff", b'[{"price":NaN}]'])
def test_bad_json_document_refused(content: bytes) -> None:
    with pytest.raises(ProofError, match="invalid_document"):
        verify_cells(content, "application/json", proof())


def test_csv_exact_row_and_decimal_styles() -> None:
    evidence = csv_proof()
    assert (
        verify_cells(b"product,period,price\nrice,2024-01,3000.1250\n", "text/csv", evidence) == 3
    )
    evidence["delimiter"] = ";"
    evidence["number_style"] = "decimal_comma"
    evidence["cells"][0]["expected"] = "2850.50"
    assert verify_cells(b"product;period;price\nrice;2024-01;2.850,50\n", "text/csv", evidence) == 3
    with pytest.raises(ProofError, match="identity_mismatch"):
        verify_cells(b"product;period;price\nmaize;2024-02;2.850,50\n", "text/csv", evidence)


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"product,period,price,price\nrice,2024-01,3000,3000\n",
        b"product,period,\nrice,2024-01,3000\n",
        b"product,period,price\n",
        b"product,period,price\nrice,2024-01\n",
        b'product,period,price\nrice,2024-01,"unterminated',
    ],
)
def test_bad_csv_documents(content: bytes) -> None:
    with pytest.raises(ProofError):
        verify_cells(content, "text/csv", csv_proof())


@pytest.mark.parametrize(
    "change", [{"row": -1}, {"row": True}, {"delimiter": ""}, {"number_style": "guess"}]
)
def test_bad_csv_coordinates(change: dict[str, Any]) -> None:
    with pytest.raises(ProofError):
        verify_cells(
            b"product,period,price\nrice,2024-01,3000.1250\n", "text/csv", csv_proof() | change
        )


def test_missing_csv_column_and_format_mismatch() -> None:
    evidence = csv_proof()
    evidence["cells"][0]["column"] = "absent"
    with pytest.raises(ProofError, match="cell_missing"):
        verify_cells(b"product,period,price\nrice,2024-01,3000.1250\n", "text/csv", evidence)
    with pytest.raises(ProofError, match="unsupported_format"):
        verify_cells(CONTENT, "application/pdf", proof())


@pytest.mark.parametrize("value", [True, None, "NaN", "Infinity", "3,000", "instruction 3000.1250"])
def test_unsupported_numeric_cells(value: Any) -> None:
    import json

    document = json.dumps([{"product": "rice", "period": "2024-01", "price": value}]).encode()
    with pytest.raises(ProofError, match="invalid_number"):
        verify_cells(document, "application/json", proof())


def test_result_ids_are_not_value_or_snippet_payloads() -> None:
    verifier, _, _, claim = example()
    result = verifier.verify([claim]).results[0]
    assert isinstance(result.observation_id, UUID)
    assert "rice" not in repr(result) and "3000.125" not in repr(result)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("content_sha256", None, "invalid_sha256"),
        ("source_id", None, "invalid_object_key"),
        ("source_id", "../outside", "invalid_object_key"),
        ("object_key", None, "invalid_object_key"),
        ("mime_type", None, "unsupported_format"),
    ],
)
def test_malformed_reference_is_fail_closed(field: str, value: Any, reason: str) -> None:
    verifier, _, reference, claim = example()
    verifier.references = {reference.source_record_id: replace(reference, **{field: value})}
    report = verifier.verify([claim])
    assert not report.passed and report.results[0].reason == reason


@pytest.mark.parametrize("payload", [None, "secret text is not bytes"])
def test_nonbyte_object_is_not_a_success(payload: Any) -> None:
    verifier, reader, _, claim = example()
    reader.objects[KEY] = payload
    report = verifier.verify([claim])
    assert not report.passed and report.results[0].reason == "object_unavailable"
    assert "secret" not in repr(report)


def test_missing_proof_identity_and_text_value() -> None:
    with pytest.raises(ProofError, match="invalid_proof"):
        verify_cells(CONTENT, "application/json", None)  # type: ignore[arg-type]
    evidence = proof()
    evidence["cells"] = [evidence["cells"][0]]
    with pytest.raises(ProofError, match="identity_or_value_missing"):
        verify_cells(CONTENT, "application/json", evidence)
    evidence = proof()
    evidence["cells"][0].update({"kind": "text", "expected": "3000.1250"})
    with pytest.raises(ProofError, match="value_mismatch"):
        verify_cells(CONTENT, "application/json", evidence)
