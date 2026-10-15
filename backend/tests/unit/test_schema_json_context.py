"""Declared scopes/variants, never schema inference or arbitrary type coercion."""

import hashlib
import json

import pytest

from ketrika.core.schema_json import (
    JSONSchemaAlternatives,
    JSONSchemaContract,
    JSONShape,
    inspect_json_schema,
)


@pytest.mark.parametrize("value", [b'"123.45"', b"123.45", b"0", b'"0"', b'"1e2"'])
def test_declared_decimal_accepts_exact_finite_number_or_numeric_text(value):
    assert inspect_json_schema(value, JSONSchemaContract("d1", JSONShape("decimal"))).passed


@pytest.mark.parametrize(
    "value", [b"true", b"null", b'""', b'"NaN"', b'"Infinity"', b'"not a number"', b"[]"]
)
def test_decimal_refuses_boolean_missing_nonfinite_and_other_types(value):
    assert not inspect_json_schema(value, JSONSchemaContract("d1", JSONShape("decimal"))).passed


def test_context_scope_preserves_full_document_sha_and_does_not_expand_contract():
    contract = JSONSchemaContract("ctx1", JSONShape("string"), ("context", "unit"))
    content = b'{"context":{"unit":"KG"},"narrative":"data not instructions"}'
    report = inspect_json_schema(content, contract)
    assert report.passed
    assert report.content_sha256 == hashlib.sha256(content).hexdigest()
    assert contract.sha256 != JSONSchemaContract("ctx1", JSONShape("string")).sha256
    assert not inspect_json_schema(b'{"context":{"unit":42}}', contract).passed
    assert not inspect_json_schema(b'{"other":"KG"}', contract).passed
    assert not inspect_json_schema(b'{"context":{"unit":"KG","unit":"t"}}', contract).passed


def test_context_remains_closed_inside_declared_scope():
    shape = JSONShape("object", properties=(("unit", JSONShape("string"), True),))
    contract = JSONSchemaContract("ctx1", shape, ("context",))
    assert not inspect_json_schema(b'{"context":{"unit":"KG","extra":1}}', contract).passed


def test_exactly_one_alternative_required():
    one = JSONSchemaContract("s1", JSONShape("string"))
    two = JSONSchemaContract("n1", JSONShape("number"))
    contract = JSONSchemaAlternatives("either1", (one, two))
    assert inspect_json_schema(b'"a"', contract).passed
    assert inspect_json_schema(b"12", contract).passed
    assert not inspect_json_schema(b"true", contract).passed
    ambiguous = JSONSchemaAlternatives(
        "bad1", (two, JSONSchemaContract("d1", JSONShape("decimal")))
    )
    assert inspect_json_schema(b"12", ambiguous).reasons == ("schema_ambiguous_variant",)
    assert inspect_json_schema(b'"a"', contract).contract_sha256 == contract.sha256


def test_v1_contract_hash_unchanged_without_scope():
    contract = JSONSchemaContract("s1", JSONShape("string"))
    frame = ["json_structure_contract_v1", "s1", ["string", False, [], None, []]]
    expected = hashlib.sha256(
        json.dumps(frame, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    assert contract.sha256 == expected


@pytest.mark.parametrize("scope", [(True,), (-1,), ("",), ("a",) * 33, ["a"]])
def test_invalid_code_owned_scope_refused(scope):
    with pytest.raises(ValueError):
        JSONSchemaContract("s1", JSONShape("string"), scope)


def test_duplicate_and_unbounded_alternatives_refused():
    item = JSONSchemaContract("s1", JSONShape("string"))
    with pytest.raises(ValueError):
        JSONSchemaAlternatives("a", (item, item))
    with pytest.raises(ValueError):
        JSONSchemaAlternatives("a", ())
