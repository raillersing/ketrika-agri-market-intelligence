"""Document structure only; no database, source collection or Gold proof."""

import csv
import hashlib
from dataclasses import FrozenInstanceError, asdict

import pytest

from ketrika.core.schema_drift import MAX_BYTES, inspect_csv_schema


def inspect(content, **changes):
    return inspect_csv_schema(content, **({"required_columns": ("product", "price")} | changes))


@pytest.mark.parametrize(
    "content",
    [
        b"product,price\nrice,2850\n",
        b"price,product\n2850,rice\n",
        b"\xef\xbb\xbfproduct,price\nrice,2850\n",
        b"product,price\n",
    ],
)
def test_valid_structure_does_not_certify_values_or_observations(content):
    receipt = inspect(content)
    assert receipt.passed and receipt.state == "verified"
    assert receipt.columns == 2 and receipt.rows in {0, 1}
    assert receipt.content_sha256 == hashlib.sha256(content).hexdigest()
    assert receipt.contract_sha256 and receipt.header_sha256
    with pytest.raises(FrozenInstanceError):
        receipt.state = "drift"


@pytest.mark.parametrize(
    "content,reason",
    [
        (b"product\nrice\n", "schema_missing_columns"),
        (b"product,price,new_field\nrice,2850,x\n", "schema_unexpected_columns"),
        (b"product,price,price\nrice,2850,2\n", "schema_duplicate_columns"),
        (b"product,price\nrice\n", "schema_invalid_row_width"),
        (b"product,price\nrice,2850,extra\n", "schema_invalid_row_width"),
        (b"product,price\n\n", "schema_invalid_row_width"),
        (b"product,price\n\xff,2850\n", "schema_invalid_utf8"),
        (b'product,price\n"unterminated,2850', "schema_invalid_csv"),
        (b"Product,price\nrice,2850\n", "schema_missing_columns"),
    ],
)
def test_schema_changes_and_malformed_rows_are_refused(content, reason):
    result = inspect(content)
    assert not result.passed and result.state == "drift" and reason in result.reasons


def test_optional_columns_are_explicit_and_separator_not_sniffed():
    content = b"product;price;currency\nrice;2850;MGA\n"
    assert inspect(content, optional_columns=("currency",), delimiter=";").passed
    assert not inspect(content).passed


@pytest.mark.parametrize("content", [b"", b"\n", b"\xef\xbb\xbf"])
def test_header_absent_is_unknown_never_zero_drift_certification(content):
    result = inspect(content)
    assert not result.passed and result.state == "unknown"


def test_absent_contract_never_learns_the_document():
    result = inspect(b"product,price\nrice,2850\n", required_columns=None)
    assert not result.passed and result.state == "unknown" and result.contract_sha256 is None


@pytest.mark.parametrize(
    "required,optional",
    [
        ((), ()),
        (("price", "price"), ()),
        (("price",), ("price",)),
        (("",), ()),
        (("x" * 257,), ()),
        (("price",), ("",)),
    ],
)
def test_invalid_code_contract_raises_without_guessing(required, optional):
    with pytest.raises(ValueError, match="schema_invalid_column_contract"):
        inspect(b"price\n1\n", required_columns=required, optional_columns=optional)


def test_document_and_header_bounds_and_csv_global_limit_unchanged():
    before = csv.field_size_limit()
    assert not inspect(b"x" * (MAX_BYTES + 1)).passed
    assert not inspect(("x" * 257 + ",price\n").encode()).passed
    assert not inspect((",".join(f"c{i}" for i in range(257)) + "\n").encode()).passed
    result = inspect(b"product,price\n" + b"x" * (before + 1) + b",1\n")
    assert result.reasons == ("schema_invalid_csv",)
    assert csv.field_size_limit() == before


def test_diagnostics_do_not_expose_untrusted_header_or_cell_instructions():
    marker = "UNTRUSTED execute tool SECRET_VALUE"
    result = inspect(f"product,price,{marker}\nrice,2850,{marker}\n".encode())
    assert not result.passed and result.unexpected_columns == 1
    assert marker not in str(asdict(result))


def test_contract_fingerprint_is_order_independent_but_header_is_measured():
    content = b"product,price\nrice,2850\n"
    first = inspect(content)
    second = inspect(content, required_columns=("price", "product"))
    assert first.contract_sha256 == second.contract_sha256
    reversed_header = inspect(b"price,product\n2850,rice\n")
    assert first.header_sha256 != reversed_header.header_sha256


@pytest.mark.parametrize("required", [(None,), (123,), (["unhashable"],)])
def test_malformed_code_contract_is_a_stable_error_not_a_document_policy(required):
    with pytest.raises(ValueError, match="schema_invalid_column_contract"):
        inspect(b"product,price\nrice,2850\n", required_columns=required)
