"""Explicit synthetic JSON contracts, never learned or market-qualified."""

import json
from typing import Any

import pytest

from ketrika.core.schema_json import JSONSchemaContract, JSONShape, inspect_json_schema

NUMBER = JSONShape("number")
TEXT = JSONShape("string")
ROW = JSONShape(
    "object",
    properties=(("value", NUMBER, True), ("unit", TEXT, True), ("note", TEXT, False)),
)
CONTRACT = JSONSchemaContract("synthetic-row-v1", JSONShape("array", items=ROW))
INVALID_FLAG: Any = 1  # Deliberately wrong runtime type, not a typing suppression in production.


def test_known_shape_counts_and_hashes_without_exposing_content():
    content = b'[{"unit":"kg","value":3000.1250,"note":"RUN_TOOL_NOW"}]'
    report = inspect_json_schema(content, CONTRACT)
    assert report.passed and report.state == "verified"
    assert report.objects == report.arrays == 1 and report.nodes_visited == 5
    assert report.contract_sha256 == CONTRACT.sha256
    assert "RUN_TOOL_NOW" not in repr(report) and "kg" not in repr(report)


def test_bom_and_empty_array_only_prove_structure():
    report = inspect_json_schema(b"\xef\xbb\xbf[]", CONTRACT)
    assert report.passed and report.objects == 0 and report.nodes_visited == 1


@pytest.mark.parametrize("value", [True, "3000", None, [], {}])
def test_number_not_coerced_from_other_types(value):
    content = json.dumps([{"unit": "kg", "value": value}]).encode()
    report = inspect_json_schema(content, CONTRACT)
    assert not report.passed and report.invalid_types == 1
    assert report.reasons == ("schema_invalid_types",)


@pytest.mark.parametrize(
    "content,missing,unexpected",
    [
        (b'[{"value":1}]', 1, 0),
        (b'[{"value":1,"unit":"kg","instruction":"SEND_MESSAGE"}]', 0, 1),
    ],
)
def test_closed_object_contract_counts_missing_and_unexpected(content, missing, unexpected):
    report = inspect_json_schema(content, CONTRACT)
    assert not report.passed
    assert report.missing_fields == missing and report.unexpected_fields == unexpected
    assert "instruction" not in repr(report) and "SEND_MESSAGE" not in repr(report)


@pytest.mark.parametrize(
    "content",
    [
        b'[{"value":1,"value":2,"unit":"kg"}]',
        b'[{"value":NaN,"unit":"kg"}]',
        b'[{"value":Infinity,"unit":"kg"}]',
        b'[{"value":-Infinity,"unit":"kg"}]',
        b"[] trailing",
        b"[",
        b"[" * 129 + b"0" + b"]" * 129,
    ],
    ids=["duplicate-key", "nan", "infinity", "negative-infinity", "trailing", "malformed", "depth"],
)
def test_invalid_json_refused_with_fixed_reason(content):
    report = inspect_json_schema(content, CONTRACT)
    assert report.state == "drift" and report.reasons == ("schema_invalid_json",)


def test_invalid_utf8_refused():
    assert inspect_json_schema(b"\xff", CONTRACT).reasons == ("schema_invalid_utf8",)


def test_absent_contract_never_inferred():
    report = inspect_json_schema(b'[{"value":1,"unit":"kg"}]', None)
    assert report.state == "unknown" and not report.passed
    assert report.contract_sha256 is None and report.nodes_visited == 0


def test_numeric_lexeme_is_not_economic_validation():
    report = inspect_json_schema(b'[{"value":1e999999999,"unit":"kg"}]', CONTRACT)
    assert report.passed  # JSON number type only; finite/precision checks remain separate.


def test_nested_tuple_positions_and_nullable_values():
    shape = JSONShape(
        "tuple",
        prefix=(JSONShape("object"), JSONShape("array", items=JSONShape("number", nullable=True))),
    )
    contract = JSONSchemaContract("synthetic-envelope-v1", shape)
    assert inspect_json_schema(b"[{},[1,null,2.5]]", contract).passed
    assert not inspect_json_schema(b"[[1],{}]", contract).passed
    assert not inspect_json_schema(b"[{},[],0]", contract).passed


def test_contract_fingerprint_canonical_property_order():
    first = JSONSchemaContract("v1", JSONShape("object", properties=ROW.properties))
    second = JSONSchemaContract(
        "v1", JSONShape("object", properties=tuple(reversed(ROW.properties)))
    )
    assert first.sha256 == second.sha256
    assert first.sha256 != JSONSchemaContract("v2", first.root).sha256


@pytest.mark.parametrize(
    "shape",
    [
        JSONShape("unknown"),
        JSONShape("array"),
        JSONShape("number", items=NUMBER),
        JSONShape("string", properties=(("name", TEXT, True),)),
        JSONShape("object", properties=(("same", TEXT, True), ("same", NUMBER, False))),
        JSONShape("object", properties=(("", TEXT, True),)),
        JSONShape("object", properties=(("bad\nname", TEXT, True),)),
        JSONShape("object", properties=(("name", TEXT, INVALID_FLAG),)),
        JSONShape("number", nullable=INVALID_FLAG),
        JSONShape("null", prefix=(NUMBER,)),
    ],
)
def test_invalid_contracts_are_not_source_success(shape):
    with pytest.raises(ValueError, match="json_contract_"):
        JSONSchemaContract("v1", shape)


def test_contract_depth_is_bounded():
    shape = NUMBER
    for _ in range(34):
        shape = JSONShape("array", items=shape)
    with pytest.raises(ValueError, match="outside_bounds"):
        JSONSchemaContract("v1", shape)


def test_contract_node_count_is_bounded(monkeypatch):
    monkeypatch.setattr("ketrika.core.schema_json.MAX_SHAPE_NODES", 2)
    with pytest.raises(ValueError, match="outside_bounds"):
        JSONSchemaContract("v1", ROW)


@pytest.mark.parametrize("content", [None, "[]", {}])
def test_content_requires_bytes(content):
    with pytest.raises(ValueError, match="requires_bytes"):
        inspect_json_schema(content, CONTRACT)


def test_data_traversal_limit_fails_not_truncates(monkeypatch):
    monkeypatch.setattr("ketrika.core.schema_json.MAX_DATA_NODES", 3)
    report = inspect_json_schema(b'[{"value":1,"unit":"kg"}]', CONTRACT)
    assert not report.passed and report.reasons == ("schema_nodes_outside_bounds",)


def test_byte_limit_applies_without_contract(monkeypatch):
    monkeypatch.setattr("ketrika.core.schema_json.MAX_CONTENT_BYTES", 1)
    report = inspect_json_schema(b"[]", None)
    assert report.reasons == ("schema_document_too_large",) and not report.passed
