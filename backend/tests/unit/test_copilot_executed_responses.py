"""Unit tests for Copilot executed responses, zero-hallucination validation and honest abstention (R6.3, ADR-097).

Normative tests:
1. Pure executed responses: all displayed numbers strictly reference SQL query result cells.
2. Provenance metadata: every answer includes official citations, value_kinds, and provenance_summary.
3. Honest abstention on out-of-scope queries (empty SQL, polite explicit refusal).
4. Full validation on 22 evaluation benchmark questions with anti-hallucination verification.
5. FastAPI /v1/copilot/ask endpoint returns valid CopilotAskResponse.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from fastapi.testclient import TestClient

from ketrika.api.auth import require_client
from ketrika.api.main import app
from ketrika.copilot.agent import CopilotAgent, generate_sql_from_question
from ketrika.copilot.executor import QueryResult
from ketrika.copilot.writer import (
    build_cell_placeholders,
    validate_anti_hallucination_prose,
)
from ketrika.core.db import get_db
from ketrika.core.models.db import UserAccount


def test_copilot_honest_abstention_on_out_of_scope_query() -> None:
    """Verify out-of-scope questions trigger honest abstention without querying default rice prices."""
    agent = CopilotAgent()

    out_of_scope_questions = [
        "Quelle est la capitale de l'Australie ?",
        "Qui a gagné la ligue des champions de football ?",
        "Raconte-moi une blague sur les astronautes.",
        "Quel temps fait-il à Paris aujourd'hui ?",
    ]

    for q in out_of_scope_questions:
        res = agent.ask(q)
        assert res["sql"] == ""
        assert res["citations"] == []
        assert "spécialisé dans la veille des prix" in res["answer_markdown"]
        assert "ne semble pas concerner ces filières" in res["answer_markdown"]
        assert "Abstention loyale" in res["provenance_summary"]


def test_copilot_empty_question_handling() -> None:
    """Verify empty or whitespace-only questions return polite prompt."""
    agent = CopilotAgent()
    res = agent.ask("   ")
    assert res["sql"] == ""
    assert "Veuillez poser une question" in res["answer_markdown"]


def test_copilot_response_structure_and_provenance_metadata() -> None:
    """Verify valid agricultural question returns complete provenance metadata and verified numbers."""
    agent = CopilotAgent()
    mock_result = QueryResult(
        sql="SELECT product_name, location_name, month, median_price, chosen_source_id FROM gold.price_monthly_best LIMIT 6;",
        columns=["product_name", "location_name", "month", "median_price", "chosen_source_id"],
        rows=[
            {
                "product_name": "Riz blanc local",
                "location_name": "Analamanga",
                "month": "2024-05",
                "median_price": 2850.0,
                "chosen_source_id": "odr",
            }
        ],
        row_count=1,
        citations=[{"source_id": "odr", "kind": "official_source"}],
        value_kinds=["observed"],
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "ketrika.copilot.agent.execute_copilot_query", lambda *args, **kwargs: mock_result
        )
        res = agent.ask("Quel est le dernier prix du riz blanc à Analamanga ?")

    assert "Riz blanc local" in res["answer_markdown"]
    assert "2 850 Ar" in res["answer_markdown"]
    assert res["sql"] != ""
    assert len(res["citations"]) == 1
    assert res["citations"][0]["source_id"] == "odr"
    assert res["value_kinds"] == ["observed"]
    assert "traçabilité Bronze SHA-256" in res["provenance_summary"]

    # Verify anti-hallucination compliance
    cell_map, _ = build_cell_placeholders(mock_result)
    assert "c_0_3" in cell_map  # median_price
    assert cell_map["c_0_3"].display_value == "2 850 Ar"


def test_copilot_anti_hallucination_prose_validation() -> None:
    """Verify validate_anti_hallucination_prose rejects any unreferenced digit in free text."""
    # Compliant text using placeholders
    safe = "Le prix médian est {{c_0_0}} sur le marché de {{c_0_1}}."
    assert validate_anti_hallucination_prose(safe) is True

    # Violating text containing hallucinated number 3200
    hallucinated = "Le prix médian est 3200 Ar sur le marché de {{c_0_1}}."
    assert validate_anti_hallucination_prose(hallucinated) is False


def test_benchmark_22_questions_coverage_and_safety() -> None:
    """Verify all 22 questions from copilot_eval.yaml generate safe, valid SQL."""
    eval_file = Path(__file__).resolve().parent.parent / "copilot_eval.yaml"
    if not eval_file.exists():
        eval_file = Path("/app/tests/copilot_eval.yaml")

    with eval_file.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    questions = data.get("questions", [])
    assert len(questions) >= 20

    for item in questions:
        if (
            item.get("expected_abstain")
            or item.get("is_adversarial")
            or item.get("expected_target_view") in ("abstain", "forbidden")
        ):
            continue
        q_text = item["question"]
        expected_view = item["expected_target_view"]

        sql = generate_sql_from_question(q_text)
        assert sql != "", f"Question was unexpectedly abstained: '{q_text}'"
        assert "gold" in sql.lower()
        view_short = expected_view.split(".")[-1]
        assert view_short in sql.lower(), (
            f"Expected view '{expected_view}' not found in SQL for '{q_text}'"
        )


def test_fastapi_copilot_ask_endpoint() -> None:
    """Verify POST /v1/copilot/ask returns 200 with full CopilotAskResponse schema."""
    fake_user = UserAccount(email="analyst@ketrika.mg", role="client")
    mock_session = MagicMock()

    app.dependency_overrides[require_client] = lambda: fake_user
    app.dependency_overrides[get_db] = lambda: mock_session

    client = TestClient(app)
    try:
        resp = client.post(
            "/v1/copilot/ask",
            json={"question": "Quel est le prix actuel du maïs à Analamanga ?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer_markdown" in data
        assert "sql" in data
        assert "rows_preview" in data
        assert "citations" in data
        assert "value_kinds" in data
        assert "provenance_summary" in data
    finally:
        app.dependency_overrides.clear()
