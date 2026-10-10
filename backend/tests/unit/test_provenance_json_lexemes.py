"""Synthetic JSON token regressions, not source acquisition evidence."""

import copy
import json

import pytest

from ketrika.core.provenance import MAX_CONTENT_BYTES, MAX_JSON_DEPTH, ProofError, verify_cells
from tests.unit.test_provenance import proof


@pytest.mark.parametrize(
    "token",
    ["3000.1250", "3000", "-0", "1e3", "1E+3", "9007199254740993", "0.00000000000000012300"],
)
def test_explicit_encoding_preserves_original_numeric_token(token: str) -> None:
    content = ('[{"product":"rice","period":"2024-01","price":' + token + "}]").encode()
    candidate = proof()
    candidate["cells"][0].update(
        expected=token, raw_expected=token, raw_encoding="json_number_lexeme"
    )
    assert verify_cells(content, "application/json", candidate) == 3


@pytest.mark.parametrize(
    "actual,claimed", [("1e3", "1000"), ("1e3", "1E+3"), ("-0", "0"), ("3000.1250", "3000.125")]
)
def test_decimal_equivalence_does_not_prove_the_claimed_raw(actual: str, claimed: str) -> None:
    content = ('[{"product":"rice","period":"2024-01","price":' + actual + "}]").encode()
    candidate = proof()
    candidate["cells"][0].update(
        expected=actual, raw_expected=claimed, raw_encoding="json_number_lexeme"
    )
    with pytest.raises(ProofError, match="raw_value_mismatch"):
        verify_cells(content, "application/json", candidate)


def test_string_is_not_a_numeric_json_token() -> None:
    candidate = proof()
    candidate["cells"][0].update(raw_encoding="json_number_lexeme")
    with pytest.raises(ProofError, match="json_number_token_required"):
        verify_cells(
            b'[{"product":"rice","period":"2024-01","price":"3000.1250"}]',
            "application/json",
            candidate,
        )


def test_duplicate_keys_are_not_resolved_opportunistically() -> None:
    with pytest.raises(ProofError, match="duplicate_json_key"):
        verify_cells(
            b'[{"product":"maize","product":"rice","period":"2024-01","price":3000.1250}]',
            "application/json",
            proof(),
        )


def test_numeric_identity_is_not_implicitly_cast_to_text() -> None:
    candidate = copy.deepcopy(proof())
    candidate["cells"][1]["expected"] = "123"
    with pytest.raises(ProofError, match="identity_mismatch"):
        verify_cells(
            b'[{"product":123,"period":"2024-01","price":3000.1250}]', "application/json", candidate
        )


@pytest.mark.parametrize("encoding", ["unknown", True, 1, None, ""])
def test_unknown_encoding_is_refused(encoding) -> None:
    candidate = proof()
    candidate["cells"][0]["raw_encoding"] = encoding
    with pytest.raises(ProofError, match="unsupported_raw_encoding"):
        verify_cells(
            b'[{"product":"rice","period":"2024-01","price":3000.1250}]',
            "application/json",
            candidate,
        )


def test_oversized_content_is_refused_before_parsing() -> None:
    with pytest.raises(ProofError, match="content_too_large"):
        verify_cells(b" " * (MAX_CONTENT_BYTES + 1), "application/json", proof())


def test_excessive_json_depth_has_a_stable_rejection() -> None:
    with pytest.raises(ProofError, match="invalid_document"):
        verify_cells(b"[" * 3000 + b"0" + b"]" * 3000, "application/json", proof())


def test_uninterpretable_exponent_has_a_stable_rejection() -> None:
    with pytest.raises(ProofError, match="invalid_document"):
        verify_cells(
            b'[{"product":"rice","period":"2024-01","price":1e999999999999999999999999}]',
            "application/json",
            proof(),
        )


def test_brackets_and_escaped_quotes_in_strings_are_not_depth() -> None:
    product = "[" * 300 + '\\"{' + "}" * 300
    content = json.dumps([{"product": product, "period": "2024-01", "price": 3000.1250}]).encode()
    candidate = proof()
    candidate["cells"][1]["expected"] = product
    assert verify_cells(content, "application/json", candidate) == 3


@pytest.mark.parametrize("extra", [0, 1])
def test_depth_boundary_is_explicit(extra: int) -> None:
    nesting = MAX_JSON_DEPTH - 1 + extra
    body = b'{"product":"rice","period":"2024-01","price":3000.1250}'
    content = b"[" * nesting + body + b"]" * nesting
    candidate = proof()
    candidate["scope_path"] = [0] * nesting
    for cell in candidate["cells"]:
        cell["path"] = [0] * nesting + [cell["path"][-1]]
    if extra:
        with pytest.raises(ProofError, match="invalid_document"):
            verify_cells(content, "application/json", candidate)
    else:
        assert verify_cells(content, "application/json", candidate) == 3
