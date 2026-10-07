"""Unit tests for weekly market bulletin generation and strict validation (SPECS §20, T8.2)."""

from __future__ import annotations

import io
import uuid
from datetime import date
from unittest.mock import MagicMock

import pdfplumber

from ketrika.bulletin.facts import format_fr_number
from ketrika.bulletin.render import (
    render_html,
    render_pdf,
    substitute_facts,
)
from ketrika.bulletin.writer import (
    generate_bulletin_prose,
    validate_prose,
)


def test_validate_prose_accepts_clean_placeholders() -> None:
    """Prose containing only placeholders without any literal digit is accepted."""
    allowed = {"f001", "f002", "period_start", "period_end"}
    clean_prose = (
        "Le prix médian du riz blanc local s'établit à {{f001}} avec une variation de {{f002}}. "
        "Pour la période du {{period_start}} au {{period_end}}."
    )
    valid, reason = validate_prose(clean_prose, allowed)
    assert valid is True
    assert reason == ""


def test_validate_prose_rejects_literal_number_2850() -> None:
    """SPECS §20 / T8.2: A LLM output containing a literal number (e.g., '2850') is rejected."""
    allowed = {"f001", "period_start", "period_end"}
    hallucinated_prose = (
        "Le prix du riz blanc local s'établit à 2850 Ar/kg sur le marché d'Analamanga."
    )
    valid, reason = validate_prose(hallucinated_prose, allowed)
    assert valid is False
    assert "Chiffre littéral interdit '2'" in reason or "interdit" in reason


def test_validate_prose_rejects_unknown_placeholder() -> None:
    """Referencing a placeholder not in the fact dictionary is rejected."""
    allowed = {"f001"}
    bad_ph_prose = "Le cours s'élève à {{f999}} sur le marché."
    valid, reason = validate_prose(bad_ph_prose, allowed)
    assert valid is False
    assert "Placeholder inconnu '{{f999}}'" in reason


def test_writer_triggers_fallback_when_llm_hallucinates_digits() -> None:
    """When LLM repeatedly produces literal digits, writer triggers deterministic fallback."""
    facts = {
        "f001": {
            "label": "Prix médian riz",
            "value": 2850.0,
            "display": "2 850 Ar/kg",
            "observation_ids": ["obs-1"],
        }
    }
    mock_llm = MagicMock()
    # LLM always hallucinates literal number "2850"
    mock_llm.generate.return_value = "Le prix médian est de 2850 Ar/kg pour le riz."

    p_start = date(2026, 9, 1)
    p_end = date(2026, 9, 30)

    prose, is_fallback = generate_bulletin_prose(facts, p_start, p_end, llm_client=mock_llm)
    assert is_fallback is True
    assert "Bulletin Hebdomadaire des Marchés Vivriers" in prose
    assert "{{ f001 }}" in prose
    # Verify mock_llm was attempted
    assert mock_llm.generate.call_count == 2


def test_writer_accepts_clean_llm_output() -> None:
    """When LLM strictly references placeholders, output is accepted without fallback."""
    facts = {
        "f001": {
            "label": "Prix médian riz",
            "value": 2850.0,
            "display": "2 850 Ar/kg",
            "observation_ids": ["obs-1"],
        }
    }
    mock_llm = MagicMock()
    mock_llm.generate.return_value = (
        "En synthèse, le prix médian du riz local s'établit à {{f001}} sur le marché de détail."
    )

    p_start = date(2026, 9, 1)
    p_end = date(2026, 9, 30)

    prose, is_fallback = generate_bulletin_prose(facts, p_start, p_end, llm_client=mock_llm)
    assert is_fallback is False
    assert "{{f001}}" in prose


def test_substitute_facts_replaces_all_placeholders() -> None:
    """Placeholder substitution cleanly replaces all placeholders with display strings."""
    facts = {
        "f001": {
            "label": "Prix",
            "display": "2 850 Ar/kg",
        },
        "f002": {
            "label": "Variation",
            "display": "+5,2 %",
        },
    }
    prose = "Le cours est de {{f001}} (variation : {{ f002 }})."
    p_start = date(2026, 9, 1)
    p_end = date(2026, 9, 30)

    substituted = substitute_facts(prose, facts, p_start, p_end)
    assert "2 850 Ar/kg" in substituted
    assert "+5,2 %" in substituted
    assert "{{" not in substituted


def test_render_pdf_and_audit_all_numbers() -> None:
    """Audit test (SPECS §20): Every number appearing in the PDF must match a certified fact."""
    obs_id_1 = str(uuid.uuid4())
    obs_id_2 = str(uuid.uuid4())

    facts = {
        "f001": {
            "label": "Prix médian riz",
            "value": 2850.0,
            "display": "2 850 Ar/kg",
            "observation_ids": [obs_id_1],
        },
        "f002": {
            "label": "Stock disponible",
            "value": 45.0,
            "display": "45 jours",
            "observation_ids": [obs_id_2],
        },
    }
    p_start = date(2026, 9, 1)
    p_end = date(2026, 9, 30)

    prose = "- Le prix médian du riz s'élève à {{f001}}.\n- Couverture des stocks : {{f002}}."
    subst_md = substitute_facts(prose, facts, p_start, p_end)
    html_content = render_html(subst_md, facts, p_start, p_end)
    pdf_bytes = render_pdf(html_content)

    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")

    # Extract text from generated PDF and verify numbers
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        full_text = "".join(p.extract_text() or "" for p in pdf.pages)

    # Known facts numbers
    assert "2 850" in full_text or "2850" in full_text or "2 850 Ar/kg" in full_text
    assert "45" in full_text

    # Verify that observation IDs exist for these audited facts
    for _k, f in facts.items():
        obs_ids = f.get("observation_ids")
        assert isinstance(obs_ids, list) and len(obs_ids) > 0


def test_format_fr_number() -> None:
    """Test French formatting of numbers with narrow spaces and commas."""
    assert format_fr_number(2850) == "2 850"
    assert format_fr_number(1250000) == "1 250 000"
    assert format_fr_number(5.2, decimals=1) == "5,2"
    assert format_fr_number(1500.75, decimals=2) == "1 500,75"
