"""Copilot analyst endpoint (SPECS §19, §21)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ketrika.api.auth import require_client
from ketrika.copilot.agent import CopilotAgent
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


_copilot_agent: CopilotAgent | None = None


def get_copilot_agent() -> CopilotAgent:
    """Singleton getter for CopilotAgent."""
    global _copilot_agent
    if _copilot_agent is None:
        _copilot_agent = CopilotAgent()
    return _copilot_agent


@router.post("/ask", response_model=CopilotAskResponse)
def ask_copilot(
    payload: CopilotAskRequest,
    user: UserAccount = Depends(require_client),
    session: Session = Depends(get_db),
    agent: CopilotAgent = Depends(get_copilot_agent),
) -> CopilotAskResponse:
    """Ask natural language question to Ketrika market analyst copilot (SPECS §19, §21)."""
    question = payload.question.strip()
    result = agent.ask(question)
    return CopilotAskResponse(
        answer_markdown=result["answer_markdown"],
        sql=result["sql"],
        rows_preview=result["rows_preview"],
        citations=result["citations"],
        value_kinds=result["value_kinds"],
    )
