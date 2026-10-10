"""Synthetic LLM proof checks, without inference or source qualification."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from ketrika.core.provenance import ProofError, verify_cells
from ketrika.core.provenance_llm import verify_llm_evidence

HTML = b"<table><tr><td>rice</td><td>3000.1250</td></tr></table><script>maize 9999</script>"


def proof() -> dict[str, Any]:
    return {
        "version": 1,
        "format": "html_table",
        "table": 0,
        "row": 0,
        "cells": [
            {
                "field": "product_raw",
                "role": "identity",
                "kind": "text",
                "column": 0,
                "expected": "rice",
            },
            {
                "field": "price_value",
                "role": "value",
                "kind": "number",
                "column": 1,
                "expected": "3000.125",
                "raw_expected": "3000.1250",
            },
        ],
        "llm_evidence": {"page": 1, "text": "rice 3000.1250"},
    }


def test_html_exact_cells_and_source_excerpt_pass():
    candidate = proof()
    original = deepcopy(candidate)
    assert verify_cells(HTML, "text/html", candidate) == 2
    assert candidate == original


def test_empty_source_page_cannot_ground_a_snippet() -> None:
    with pytest.raises(ProofError, match="llm_page_unverifiable"):
        verify_llm_evidence(b"", proof(), ["rice", "3000.1250"])


def test_empty_cell_set_cannot_be_certified() -> None:
    with pytest.raises(ProofError, match="llm_cells_missing"):
        verify_llm_evidence(HTML, proof(), [])


def test_empty_cell_token_cannot_be_certified() -> None:
    with pytest.raises(ProofError, match="llm_cell_not_in_excerpt"):
        verify_llm_evidence(HTML, proof(), [""])


def test_invalid_pdf_is_not_an_llm_success() -> None:
    candidate = proof()
    candidate.update(format="pdf_table", page=1)
    with pytest.raises(ProofError, match="invalid_document"):
        verify_llm_evidence(b"not a PDF", candidate, ["rice"])


def test_pdf_page_missing_cannot_be_certified() -> None:
    content = (
        Path(__file__).resolve().parents[1] / "fixtures/miasa_odr/odr_bulletin_850.pdf"
    ).read_bytes()
    candidate = proof()
    candidate.update(format="pdf_table", page=99)
    candidate["llm_evidence"]["page"] = 99
    with pytest.raises(ProofError, match="llm_page_missing"):
        verify_llm_evidence(content, candidate, ["rice"])


@pytest.mark.parametrize(
    "evidence,reason",
    [
        (None, "llm_evidence_missing"),
        ({"page": True, "text": "rice 3000.1250"}, "invalid_llm_evidence"),
        ({"page": 0, "text": "rice 3000.1250"}, "invalid_llm_evidence"),
        ({"page": 1, "text": ""}, "invalid_llm_evidence"),
        ({"page": 2, "text": "rice 3000.1250"}, "llm_page_mismatch"),
        ({"page": 1, "text": "maize 9999"}, "llm_excerpt_unanchored"),
        ({"page": 1, "text": "rice"}, "llm_cell_not_in_excerpt"),
        ({"page": 1, "text": "3000.1250"}, "llm_cell_not_in_excerpt"),
        ({"page": 1, "text": "rice 3000.125"}, "llm_cell_not_in_excerpt"),
    ],
)
def test_invalid_or_incomplete_excerpt_refused(evidence, reason):
    candidate = proof()
    candidate["llm_evidence"] = evidence
    with pytest.raises(ProofError, match=reason):
        verify_cells(HTML, "text/html", candidate)


def test_incorrect_cell_is_refused_even_when_excerpt_is_real():
    candidate = proof()
    candidate["cells"][1]["expected"] = "9999"
    with pytest.raises(ProofError, match="value_mismatch"):
        verify_cells(HTML, "text/html", candidate)


@pytest.mark.parametrize(
    "number", ["1650.99", "1650,99", "11650", "16500", "-1650", "+1650", ".1650"]
)
def test_numeric_token_is_not_a_prefix_of_a_different_number(number: str) -> None:
    candidate = proof()
    candidate["llm_evidence"]["text"] = "rice " + number
    with pytest.raises(ProofError, match="llm_cell_not_in_excerpt"):
        verify_llm_evidence(("<p>rice " + number + "</p>").encode(), candidate, ["rice", "1650"])


def test_identity_is_not_a_substring_of_a_different_word():
    candidate = proof()
    candidate["llm_evidence"]["text"] = "price 3000.1250"
    with pytest.raises(ProofError, match="llm_cell_not_in_excerpt"):
        verify_llm_evidence(b"<p>price 3000.1250</p>", candidate, ["rice", "3000.1250"])


@pytest.mark.parametrize("format_name", ["xlsx_table", "json", "csv"])
def test_unsupported_llm_formats_fail_closed(format_name):
    candidate = proof()
    candidate["format"] = format_name
    with pytest.raises(ProofError, match="unsupported_llm_format"):
        verify_llm_evidence(HTML, candidate, ["rice", "3000.1250"])


def test_pdf_excerpt_is_read_from_the_same_page():
    content = (
        Path(__file__).resolve().parents[1] / "fixtures/miasa_odr/odr_bulletin_850.pdf"
    ).read_bytes()
    candidate = {
        "version": 1,
        "format": "pdf_table",
        "page": 1,
        "table": 0,
        "row": 1,
        "cells": [
            {
                "field": "location_raw",
                "role": "identity",
                "kind": "text",
                "column": 0,
                "expected": "Alaotra Mangoro (Ambatondrazaka)",
            },
            {
                "field": "price_value",
                "role": "value",
                "kind": "number",
                "column": 1,
                "expected": "1650",
            },
        ],
        "llm_evidence": {"page": 1, "text": "Alaotra Mangoro (Ambatondrazaka) 1650"},
    }
    assert verify_cells(content, "application/pdf", candidate) == 2
    candidate["llm_evidence"]["page"] = 2
    with pytest.raises(ProofError, match="llm_page_mismatch"):
        verify_cells(content, "application/pdf", candidate)
