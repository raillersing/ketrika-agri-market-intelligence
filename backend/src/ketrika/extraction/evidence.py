"""Evidence verification module for LLM extracted data (SPECS §11.2)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from rapidfuzz import fuzz


def normalize_text_for_evidence(text: str) -> str:
    """Normalize text according to SPECS §11.2:

    1. NFKC unicode normalization
    2. Lowercase
    3. Non-breaking spaces (\u00a0, \u202f, \u2007) converted to standard space
    4. Multiple whitespace collapsed to single space
    5. Strip leading/trailing whitespace
    """
    if not text:
        return ""
    # 1. NFKC normalization
    normalized = unicodedata.normalize("NFKC", text)
    # 2. Lowercase
    normalized = normalized.lower()
    # 3. Non-breaking spaces and table pipe separators to standard space
    normalized = re.sub(r"[\u00a0\u202f\u2007\u200b\t\r\n|]+", " ", normalized)
    # 4. Collapse multiple whitespace
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def generate_number_variants(value: float | int | str) -> list[str]:
    """Generate expected numeric string representations:

    2850, 2 850, 2.850, 2,850, plus decimal variants (2 850.50, 2 850,50, 2850.5).
    """
    if isinstance(value, str):
        clean = value.replace(" ", "").replace(",", ".").strip()
        try:
            num = float(clean)
        except ValueError:
            return [value.strip().lower()]
    elif isinstance(value, (int, float)):
        num = float(value)
    else:
        return []

    variants: set[str] = set()

    # Integer representation if whole number
    is_integer = num.is_integer()
    int_val = int(num)

    if is_integer:
        s_int = str(int_val)
        variants.add(s_int)  # 2850

        # With thousands separators
        if len(s_int) > 3:
            # 2 850 (space)
            rev = s_int[::-1]
            chunks = [rev[i : i + 3] for i in range(0, len(rev), 3)]
            formatted_space = " ".join(chunks)[::-1]
            variants.add(formatted_space)  # 2 850
            variants.add(formatted_space.replace(" ", "."))  # 2.850
            variants.add(formatted_space.replace(" ", ","))  # 2,850
    else:
        # Float formatting: e.g. 2850.5 or 2850.50
        s_dot = f"{num:.2f}".rstrip("0").rstrip(".")
        variants.add(s_dot)  # 2850.5
        variants.add(f"{num:.2f}")  # 2850.50
        variants.add(s_dot.replace(".", ","))  # 2850,5
        variants.add(f"{num:.2f}".replace(".", ","))  # 2850,50

        # Thousands separator with decimal
        int_part = int(num)
        dec_part_2 = f"{num:.2f}".split(".")[1]
        dec_part_clean = s_dot.split(".")[1] if "." in s_dot else dec_part_2

        s_int = str(int_part)
        if len(s_int) > 3:
            rev = s_int[::-1]
            chunks = [rev[i : i + 3] for i in range(0, len(rev), 3)]
            spaced_int = " ".join(chunks)[::-1]

            variants.add(f"{spaced_int}.{dec_part_2}")  # 2 850.50
            variants.add(f"{spaced_int},{dec_part_2}")  # 2 850,50
            variants.add(f"{spaced_int.replace(' ', '.')},{dec_part_2}")  # 2.850,50
            variants.add(f"{spaced_int}.{dec_part_clean}")  # 2 850.5
            variants.add(f"{spaced_int},{dec_part_clean}")  # 2 850,5

    return sorted(variants, key=len, reverse=True)


def verify_evidence(
    value: Any,
    evidence: dict[str, Any] | None,
    page_text: str | None,
    min_text_similarity: float = 95.0,
    expected_location: str | None = None,
    expected_product: str | None = None,
) -> bool:
    """Verify that extracted value and its evidence snippet are grounded in page_text (SPECS §11.2, R1.4).

    Rules:
    1. page_text and evidence.text must be non-empty (scan without OCR -> unverifiable).
    2. Normalize page_text and evidence.text (NFKC, lowercase, collapse whitespace).
    3. evidence.text must be substring of page_text or partial_ratio >= 95%.
    4. Numeric representation of value must appear in evidence.text.
    5. If expected_location is given, evidence.text must explicitly contain the location tokens
       to prevent neighboring table cells from being accepted as proof.
    """
    if not evidence or not isinstance(evidence, dict):
        return False
    if page_text is None:
        return False

    raw_evidence_text = evidence.get("text")
    if (
        not raw_evidence_text
        or not isinstance(raw_evidence_text, str)
        or not raw_evidence_text.strip()
    ):
        return False

    norm_page = normalize_text_for_evidence(page_text)
    norm_evidence = normalize_text_for_evidence(raw_evidence_text)

    if not norm_page or not norm_evidence:
        return False

    # 1. Text ground check: substring or fuzzy partial ratio >= 95
    if norm_evidence not in norm_page:
        similarity = fuzz.partial_ratio(norm_evidence, norm_page)
        if similarity < min_text_similarity:
            return False

    # 2. Location grounding: reject neighboring table/row cells when page lists locations
    if expected_location:
        norm_loc = normalize_text_for_evidence(expected_location)
        # Extract location keywords (e.g. "Analamanga (Antananarivo)" -> ["analamanga", "antananarivo"])
        loc_tokens = [
            t.strip("()[],.-")
            for t in re.split(r"[\s\(\)\[\],]+", norm_loc)
            if len(t.strip("()[],.-")) >= 3
        ]
        page_has_location = bool(loc_tokens and any(tok in norm_page for tok in loc_tokens))
        if page_has_location and not any(tok in norm_evidence for tok in loc_tokens):
            return False

    # 3. Numeric value check: at least one representation variant must be in norm_evidence
    variants = generate_number_variants(value)
    if not variants:
        return False

    # Check for presence of any numeric variant in normalized evidence text
    norm_evidence_no_punc = re.sub(r"[\(\)\[\]]", " ", norm_evidence)
    found_number = False
    for v in variants:
        # Match variant as token or with word boundaries
        pattern = r"(?<!\d)" + re.escape(v) + r"(?!\d)"
        if re.search(pattern, norm_evidence_no_punc):
            found_number = True
            break

    return found_number
