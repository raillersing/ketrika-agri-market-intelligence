"""Copilot analyst endpoint (SPECS §19, §21)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ketrika.api.auth import require_client
from ketrika.core.db import get_db
from ketrika.core.models.db import UserAccount

router = APIRouter(prefix="/v1/copilot", tags=["copilot"])


class CopilotAskRequest(BaseModel):
    """Copilot query request."""

    question: str


class CopilotAskResponse(BaseModel):
    """Copilot query answer, SQL query and structured citations."""

    answer_markdown: str
    sql: str
    rows_preview: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    value_kinds: list[str]


@router.post("/ask", response_model=CopilotAskResponse)
def ask_copilot(
    payload: CopilotAskRequest,
    user: UserAccount = Depends(require_client),
    session: Session = Depends(get_db),
) -> CopilotAskResponse:
    """Ask natural language question to Ketrika market analyst copilot (SPECS §19, §21)."""
    # Baseline deterministic answer structure for T6.1 (full LLM copilot agent developed in Phase 10)
    question = payload.question.strip()
    return CopilotAskResponse(
        answer_markdown=f"Analyse de marché pour: {question}",
        sql="SELECT product_code, month, median_price FROM gold.price_monthly_best LIMIT 10;",
        rows_preview=[],
        citations=[{"source_id": "miasa_odr", "type": "official"}],
        value_kinds=["observed"],
    )
