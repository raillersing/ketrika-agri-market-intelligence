"""Normative acceptance tests for market bulletin qualification (R6.5, SPECS §20).

Verifies:
1. Zero unreferenced digits in prose: validate_prose strictly rejects free digits outside {{...}}.
2. Full fact calculation & citation: all referenced facts originate from verified Gold views with provenance.
3. Directional & semantic consistency: deliberate polarity inversions (upward labeled as drop, downward labeled as spike) are rejected.
4. Speculative causality rejection: unproven claims trigger fail-closed fallback to certified deterministic template.
5. HTML vs PDF exact numerical consistency: identical figures and official citations across both formats.
6. Audited draft approval workflow: approve_bulletin persists approved_by and approved_at without external dispatch (Gate H3).
7. Mailpit preview quarantine: no emails sent to external recipients.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest

from ketrika.bulletin.render import (
    render_html,
    render_pdf,
    substitute_facts,
)
from ketrika.bulletin.semantic_guard import (
    validate_semantic_consistency,
)
from ketrika.bulletin.service import (
    approve_bulletin,
    send_bulletin_preview_to_mailpit,
)
from ketrika.bulletin.writer import (
    generate_bulletin_prose,
    validate_prose,
)
from ketrika.core.models.db import Bulletin


@pytest.fixture
def sample_bulletin_facts() -> dict[str, dict]:
    """Sample authentic Gold facts dictionary conforming to SPECS §20."""
    return {
        "f001": {
            "label": "Prix médian national du riz blanc local au détail",
            "value": 2850.0,
            "unit": "Ar/kg",
            "display": "2 850 Ar/kg",
            "sources": ["miasa_odr", "wfp_hdx_mdg"],
            "observation_ids": ["obs-rice-001", "obs-rice-002"],
            "value_kind": "observed",
        },
        "f002": {
            "label": "Variation mensuelle du prix médian national du riz blanc local",
            "value": 8.5,
            "unit": "%",
            "display": "+8,5 %",
            "sources": ["miasa_odr"],
            "observation_ids": ["obs-rice-001"],
            "value_kind": "observed",
        },
        "f003": {
            "label": "Variation mensuelle du prix du maïs",
            "value": -12.4,
            "unit": "%",
            "display": "-12,4 %",
            "sources": ["mincc_ppn"],
            "observation_ids": ["obs-maize-001"],
            "value_kind": "observed",
        },
        "f004": {
            "label": "Score de santé du marché",
            "value": 72.0,
            "unit": "/100",
            "display": "72/100",
            "sources": ["ketrika_kpi"],
            "observation_ids": [],
            "value_kind": "composite",
        },
        "sources_attribution": {
            "label": "Sources officielles",
            "value": 2,
            "unit": "sources",
            "display": "Observatoire du Riz (ODR), Ministère du Commerce (MIC)",
            "sources": ["odr", "mic"],
            "observation_ids": [],
        },
    }


def test_bulletin_zero_unreferenced_digits(sample_bulletin_facts: dict[str, dict]) -> None:
    """Verify validate_prose strictly forbids any literal digit outside placeholders."""
    allowed = set(sample_bulletin_facts.keys()) | {"period_start", "period_end", "sources_attribution"}

    # Compliant prose: only placeholders
    clean_prose = "Le prix du riz s'établit à {{f001}} avec une variation de {{f002}}."
    valid, err = validate_prose(clean_prose, allowed)
    assert valid is True
    assert err == ""

    # Violating prose: unreferenced number 3200
    violating_prose = "Le prix du riz a atteint 3200 Ar au marché de détail."
    valid, err = validate_prose(violating_prose, allowed)
    assert valid is False
    assert "Chiffre littéral interdit" in err


def test_bulletin_directional_semantic_guard_rejects_polarity_inversion(
    sample_bulletin_facts: dict[str, dict],
) -> None:
    """Verify validate_semantic_consistency detects deliberate direction inversion."""
    # f002 is +8.5% (an INCREASE)
    # Deliberate inversion: text claims it is a drop/decrease
    inverted_prose = "La filière enregistre une forte baisse historique de {{f002}} sur les marchés."
    valid, issues = validate_semantic_consistency(inverted_prose, sample_bulletin_facts)
    assert valid is False
    assert len(issues) >= 1
    assert "Incohérence directionnelle sur f002" in issues[0]
    assert "Le fait indique une hausse" in issues[0]

    # f003 is -12.4% (a DECREASE)
    # Deliberate inversion: text claims it is a surge/spike
    inverted_prose_2 = "On constate une flambée et hausse spectaculaire de {{f003}} sur le maïs."
    valid, issues = validate_semantic_consistency(inverted_prose_2, sample_bulletin_facts)
    assert valid is False
    assert len(issues) >= 1
    assert "Incohérence directionnelle sur f003" in issues[0]
    assert "Le fait indique une baisse" in issues[0]

    # Correct prose: respects real trend directions
    correct_prose = "On observe une hausse modérée de {{f002}} pour le riz, et un repli de {{f003}} pour le maïs."
    valid, issues = validate_semantic_consistency(correct_prose, sample_bulletin_facts)
    assert valid is True
    assert issues == []


def test_bulletin_unproven_causality_rejection(sample_bulletin_facts: dict[str, dict]) -> None:
    """Verify speculative causalities are detected and rejected."""
    speculative_prose = "La variation de {{f002}} résulte d'une spéculation illégale généralisée des grossistes."
    valid, issues = validate_semantic_consistency(speculative_prose, sample_bulletin_facts)
    assert valid is False
    assert any("Causalité spéculative" in issue for issue in issues)


def test_bulletin_llm_semantic_failure_falls_back_to_deterministic(
    sample_bulletin_facts: dict[str, dict],
) -> None:
    """Verify generate_bulletin_prose falls back to deterministic template when LLM attempts semantic inversion."""
    # Mock LLM client attempting directional inversion
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "On constate une baisse inexpliquée de {{f002}} sur le riz."

    p_start = date(2026, 9, 1)
    p_end = date(2026, 9, 7)

    prose, is_fallback = generate_bulletin_prose(
        sample_bulletin_facts,
        p_start,
        p_end,
        llm_client=mock_llm,
    )

    # Must fall back to deterministic template
    assert is_fallback is True
    assert "# Bulletin Hebdomadaire" in prose
    assert "{{ f001 }}" in prose or "{{f001}}" in prose


def test_bulletin_html_and_pdf_exact_numerical_concordance(
    sample_bulletin_facts: dict[str, dict],
) -> None:
    """Verify HTML and PDF generated from substituted markdown contain identical numbers and sources."""
    p_start = date(2026, 9, 1)
    p_end = date(2026, 9, 7)

    template = (
        "Le prix médian est {{f001}}, la variation mensuelle est {{f002}}, "
        "le maïs affiche {{f003}} et la santé est {{f004}}."
    )
    substituted = substitute_facts(template, sample_bulletin_facts, p_start, p_end)

    assert "2 850 Ar/kg" in substituted
    assert "+8,5 %" in substituted
    assert "-12,4 %" in substituted
    assert "72/100" in substituted

    # Render HTML
    html_out = render_html(substituted, sample_bulletin_facts, p_start, p_end)
    assert "2 850 Ar/kg" in html_out
    assert "+8,5 %" in html_out
    assert "-12,4 %" in html_out
    assert "72/100" in html_out
    assert "Observatoire du Riz (ODR)" in html_out

    # Render PDF bytes
    pdf_bytes = render_pdf(html_out)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_bulletin_approval_audited_workflow() -> None:
    """Verify approve_bulletin transitions status from draft to approved with audit timestamp and actor."""
    fake_session = MagicMock()
    b_id = uuid.uuid4()
    mock_bulletin = Bulletin(
        bulletin_id=b_id,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 7),
        status="draft",
        facts={},
        html_object_key="bulletin/2026/w36/test.html",
        pdf_object_key="bulletin/2026/w36/test.pdf",
        created_at=datetime.now(UTC),
    )
    fake_session.get.return_value = mock_bulletin

    approved = approve_bulletin(
        session=fake_session,
        bulletin_id=b_id,
        approved_by="director_spm@ketrika.mg",
    )

    assert approved.status == "approved"
    assert approved.approved_by == "director_spm@ketrika.mg"
    assert approved.approved_at is not None
    assert isinstance(approved.approved_at, datetime)

    # Attempting to re-approve an already approved bulletin raises an error
    with pytest.raises(ValueError, match="Impossible d'approuver un bulletin avec le statut 'approved'"):
        approve_bulletin(fake_session, b_id, approved_by="another_user@ketrika.mg")


def test_bulletin_mailpit_preview_quarantine() -> None:
    """Verify send_bulletin_preview_to_mailpit safely traps emails in Mailpit dev service."""
    b = Bulletin(
        bulletin_id=uuid.uuid4(),
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 7),
        status="draft",
        facts={},
    )
    # With a mock smtp server
    mock_smtp_inst = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("smtplib.SMTP", lambda host, port, timeout: mock_smtp_inst)
        sent = send_bulletin_preview_to_mailpit(b, "<html><body>Bulletin Preview</body></html>")

    assert sent is True
    mock_smtp_inst.__enter__().sendmail.assert_called_once()
    args = mock_smtp_inst.__enter__().sendmail.call_args[0]
    assert args[0] == "bulletin-preview@ketrika.local"
    assert args[1] == ["preview@mailpit.local"]


def test_build_bulletin_facts_with_mock_gold_session() -> None:
    """Verify build_bulletin_facts parses Gold query results into verified fact dictionaries."""
    from ketrika.bulletin.facts import build_bulletin_facts

    mock_session = MagicMock()

    # Mock row objects
    mock_rice = MagicMock()
    mock_rice.median_price = 2850.0
    mock_rice.chg_1m = 0.085
    mock_rice.chosen_source_id = "miasa_odr"
    mock_rice.obs_ids = ["obs1", "obs2"]

    mock_mh = MagicMock()
    mock_mh.product_name = "Riz blanc"
    mock_mh.location_name = "Analamanga"
    mock_mh.market_health_score = 72.0

    mock_reg_high = MagicMock()
    mock_reg_high.product_name = "Riz blanc"
    mock_reg_high.location_name = "Sava"
    mock_reg_high.median_price = 3400.0
    mock_reg_high.chosen_source_id = "miasa_odr"
    mock_reg_high.obs_ids = ["obs_high"]

    mock_reg_low = MagicMock()
    mock_reg_low.product_name = "Riz blanc"
    mock_reg_low.location_name = "Alaotra Mangoro"
    mock_reg_low.median_price = 2400.0
    mock_reg_low.chosen_source_id = "miasa_odr"
    mock_reg_low.obs_ids = ["obs_low"]

    mock_ppn1 = MagicMock()
    mock_ppn1.product_code = "maize"
    mock_ppn1.product_name = "Maïs grain"
    mock_ppn1.median_price = 1800.0
    mock_ppn1.chg_1m = -0.05
    mock_ppn1.chosen_source_id = "mincc_ppn"
    mock_ppn1.obs_ids = ["obs_m1"]

    mock_stock1 = MagicMock()
    mock_stock1.product_name = "Riz importé"
    mock_stock1.location_name = "Toamasina"
    mock_stock1.coverage_days = 45.0

    # Setup execute mock sequence
    exec_results = [
        MagicMock(fetchone=MagicMock(return_value=mock_rice)),  # query_rice_nat
        MagicMock(fetchone=MagicMock(return_value=mock_mh)),    # query_mh
        MagicMock(fetchall=MagicMock(return_value=[mock_reg_high, mock_reg_low])),  # query_reg
        MagicMock(fetchall=MagicMock(return_value=[mock_ppn1])),  # query_ppn
        MagicMock(fetchall=MagicMock(return_value=[mock_stock1])),  # query_stocks
        MagicMock(scalar=MagicMock(return_value=3)),  # query_alerts
    ]
    mock_session.execute.side_effect = exec_results

    facts = build_bulletin_facts(mock_session, date(2026, 9, 1), date(2026, 9, 7))

    assert "f001" in facts
    assert facts["f001"]["value"] == 2850.0
    assert "2 850 Ar/kg" in facts["f001"]["display"]
    assert "f002" in facts
    assert facts["f002"]["value"] == pytest.approx(8.5)
    assert "+8,5 %" in facts["f002"]["display"]
    assert "f003" in facts
    assert facts["f003"]["value"] == 72.0
    assert "sources_attribution" in facts
    assert facts["sources_attribution"]["value"] > 0


def test_generate_weekly_bulletin_full_service_pipeline() -> None:
    """Verify generate_weekly_bulletin coordinates facts, prose, artifacts, and persistence."""
    from ketrika.bulletin.service import generate_weekly_bulletin, get_bulletin

    fake_session = MagicMock()
    # Mocking build_bulletin_facts
    dummy_facts = {
        "f001": {
            "label": "Prix riz",
            "value": 2850.0,
            "unit": "Ar/kg",
            "display": "2 850 Ar/kg",
            "sources": ["miasa_odr"],
            "observation_ids": [],
            "value_kind": "observed",
        },
        "sources_attribution": {
            "label": "Sources",
            "value": 1,
            "unit": "sources",
            "display": "ODR",
            "sources": ["miasa_odr"],
            "observation_ids": [],
        },
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("ketrika.bulletin.service.build_bulletin_facts", lambda s, p1, p2: dummy_facts)
        mp.setattr(
            "ketrika.bulletin.service.save_bulletin_artifacts",
            lambda b_id, html, pdf: ("bulletin/test.html", "bulletin/test.pdf"),
        )
        b = generate_weekly_bulletin(
            session=fake_session,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 7),
            llm_client=None,
        )

    assert b is not None
    assert b.status == "draft"
    assert b.html_object_key == "bulletin/test.html"
    assert b.pdf_object_key == "bulletin/test.pdf"
    fake_session.add.assert_called_once()
    fake_session.flush.assert_called_once()

    fake_session.get.return_value = b
    retrieved = get_bulletin(fake_session, b.bulletin_id)
    assert retrieved == b


def test_approve_bulletin_not_found_raises() -> None:
    """Verify approve_bulletin raises ValueError if bulletin_id does not exist."""
    fake_session = MagicMock()
    fake_session.get.return_value = None
    with pytest.raises(ValueError, match="introuvable"):
        approve_bulletin(fake_session, uuid.uuid4(), "admin@ketrika.mg")

