"""Budget guard enforcing LLM cost limits (SPECS §11.3, AGENTS §5.3 H6)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ketrika.core.models.db import LlmCall
from ketrika.core.settings import get_settings


class BudgetExceededError(Exception):
    """Raised when an LLM call would exceed monthly or per-run cost thresholds."""

    pass


class BudgetGuard:
    """Enforces LLM spending guardrails (monthly and per-run budgets)."""

    def __init__(
        self,
        monthly_limit_usd: float | None = None,
        per_run_limit_usd: float | None = None,
    ) -> None:
        settings = get_settings()
        self.monthly_limit_usd = (
            monthly_limit_usd if monthly_limit_usd is not None else settings.llm_monthly_budget_usd
        )
        self.per_run_limit_usd = (
            per_run_limit_usd if per_run_limit_usd is not None else settings.llm_per_run_budget_usd
        )
        self._in_memory_spend: float = 0.0

    def get_monthly_spend(self, session: Session | None = None) -> float:
        """Calculate total spend for the current calendar month in UTC."""
        db_spend = 0.0
        if session is not None:
            now = datetime.now(UTC)
            first_of_month = datetime(now.year, now.month, 1, tzinfo=UTC)
            stmt = select(func.coalesce(func.sum(LlmCall.cost_usd), 0.0)).where(
                LlmCall.created_at >= first_of_month,
                LlmCall.status.in_(["ok", "cache_hit"]),
            )
            result = session.execute(stmt).scalar()
            db_spend = float(result) if result is not None else 0.0

        return db_spend + self._in_memory_spend

    def check_can_spend(
        self,
        cost_usd: float,
        current_run_spend: float = 0.0,
        session: Session | None = None,
    ) -> None:
        """Check if cost can be incurred without violating monthly or per-run limits."""
        if current_run_spend + cost_usd > self.per_run_limit_usd:
            raise BudgetExceededError(
                f"LLM call would exceed per-run budget: {current_run_spend + cost_usd:.4f}$ > {self.per_run_limit_usd:.2f}$"
            )

        total_monthly = self.get_monthly_spend(session)
        if total_monthly + cost_usd > self.monthly_limit_usd:
            raise BudgetExceededError(
                f"LLM call would exceed monthly budget: {total_monthly + cost_usd:.4f}$ > {self.monthly_limit_usd:.2f}$"
            )

    def record_spend(
        self,
        cost_usd: float,
        session: Session | None = None,
        provider: str = "replay",
        model: str = "default",
        purpose: str = "extract",
        prompt_version: str = "v1",
        cache_key: str = "default",
        input_tokens: int = 0,
        output_tokens: int = 0,
        status: str = "ok",
        source_record_id: uuid.UUID | None = None,
    ) -> None:
        """Record spend in database if session available, and in memory."""
        self._in_memory_spend += cost_usd

        if session is not None:
            llm_call = LlmCall(
                llm_call_id=uuid.uuid4(),
                provider=provider,
                model=model,
                purpose=purpose,
                prompt_version=prompt_version,
                cache_key=cache_key,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                source_record_id=source_record_id,
                created_at=datetime.now(UTC),
                status=status,
            )
            session.add(llm_call)
            session.flush()
