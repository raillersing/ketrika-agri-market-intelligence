"""Mechanical LLM evidence after exact cell verification (ADR-019)."""

from __future__ import annotations

import io
import re
from collections.abc import Mapping, Sequence
from typing import Any

import pdfplumber
from rapidfuzz import fuzz

from ketrika.core.provenance import ProofError
from ketrika.extraction.evidence import normalize_text_for_evidence
from ketrika.extraction.html import extract_html_content


def verify_llm_evidence(
    content: bytes,
    proof: Mapping[str, Any],
    verified_values: Sequence[str],
) -> None:
    """Read the source page and ground every already-verified cell token."""
    evidence = proof.get("llm_evidence")
    if not isinstance(evidence, dict):
        raise ProofError("llm_evidence_missing")
    page = evidence.get("page")
    snippet = evidence.get("text")
    if type(page) is not int or page < 1 or not isinstance(snippet, str) or not snippet.strip():
        raise ProofError("invalid_llm_evidence")
    format_name = proof.get("format")
    try:
        if format_name == "pdf_table":
            if page != proof.get("page"):
                raise ProofError("llm_page_mismatch")
            with pdfplumber.open(io.BytesIO(content)) as document:
                if page > len(document.pages):
                    raise ProofError("llm_page_missing")
                text = document.pages[page - 1].extract_text() or ""
        elif format_name == "html_table":
            if page != 1:
                raise ProofError("llm_page_mismatch")
            text = extract_html_content(content).text
        else:
            raise ProofError("unsupported_llm_format")
    except ProofError:
        raise
    except Exception as exc:
        raise ProofError("invalid_document") from exc
    normalized_page = normalize_text_for_evidence(text)
    normalized_snippet = normalize_text_for_evidence(snippet)
    if not normalized_page or not normalized_snippet:
        raise ProofError("llm_page_unverifiable")
    if (
        normalized_snippet not in normalized_page
        and fuzz.partial_ratio(normalized_snippet, normalized_page) < 95
    ):
        raise ProofError("llm_excerpt_unanchored")
    if not verified_values:
        raise ProofError("llm_cells_missing")
    for value in verified_values:
        if not isinstance(value, str):
            raise ProofError("llm_cell_unverifiable")
        token = normalize_text_for_evidence(value)
        numeric = re.fullmatch(r"[+-]?\d[\d\s.,]*", token) is not None
        suffix = r"(?!\w|[.,]\d)" if numeric else r"(?!\w)"
        prefix = r"(?<![\w.,+-])" if numeric else r"(?<!\w)"
        if not token or re.search(prefix + re.escape(token) + suffix, normalized_snippet) is None:
            raise ProofError("llm_cell_not_in_excerpt")
