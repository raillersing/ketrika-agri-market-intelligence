"""Bounded AI Workflow Engine with state persistence, idempotence, and strict safety guardrails (SPECS §11.3, R6.2, ADR-096).

Normative rules:
1. Small specialized deterministic roles: reconnaissance, extraction, analysis, drafting.
2. Hard ceilings per workflow: max_steps, max_tool_calls, max_tokens, max_duration_seconds, max_budget_usd.
3. Strict prevention of autonomous source registration: suggested new sources are isolated in proposed_sources with status PENDING_HUMAN_REVIEW, never written to registry/sources.yaml.
4. Idempotent resumption without double publication: resumed workflow skips completed steps and never re-emits published artifacts.
5. Hostile document defense: scraped/collected content is purely data, never instructions. Attempts to modify limits or permissions trigger HostileDocumentDetectedError.
6. Zero secret leakage in logs and audit events.
7. Explicit replay fail-closed semantics: missing replay fixture raises ReplayNotFoundError.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from ketrika.extraction.llm.budget import BudgetGuard

logger = logging.getLogger("ketrika.copilot.workflow")

PROHIBITED_INJECTION_PATTERNS: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore all instructions",
    "system prompt override",
    "grant admin",
    "disable budget",
    "update registry",
    "auto_registered: true",
)

SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(AIza[0-9A-Za-z_\-]{30,45})"),  # Gemini / Google API Key
    re.compile(r"(sk-[a-zA-Z0-9]{20,})"),        # OpenAI Key
    re.compile(r"(postgres://[^\s]+)"),          # DB URL with password
    re.compile(r"(password=['\"][^'\"]+['\"])", re.IGNORECASE),
)


class WorkflowLimitExceededError(RuntimeError):
    """Raised when an AI workflow exceeds its hard ceilings (steps, tools, tokens, time, or budget)."""

    def __init__(self, limit_name: str, current_value: Any, max_value: Any) -> None:
        super().__init__(
            f"Plafond de workflow dépassé pour '{limit_name}': {current_value} > {max_value}"
        )
        self.limit_name = limit_name
        self.current_value = current_value
        self.max_value = max_value


class HostileDocumentDetectedError(ValueError):
    """Raised when an external document attempts to manipulate workflow parameters or permissions."""

    pass


class ReplayNotFoundError(KeyError):
    """Raised when an expected pre-recorded replay fixture is missing in LLM replay mode."""

    pass


class WorkflowStepType(StrEnum):
    """Specialized small roles for market intelligence workflows."""

    RECONNAISSANCE = "reconnaissance"
    EXTRACTION = "extraction"
    ANALYSIS = "analysis"
    DRAFTING = "drafting"
    REVIEW_PROPOSAL = "review_proposal"


class WorkflowStepStatus(StrEnum):
    """Lifecycle status of an individual workflow step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class WorkflowLimits(BaseModel):
    """Contractual limits constraining an AI workflow."""

    max_steps: int = 5
    max_tool_calls: int = 10
    max_tokens: int = 8000
    max_duration_seconds: float = 30.0
    max_budget_usd: float = 0.05


class WorkflowStep(BaseModel):
    """Record of an individual step in the workflow execution sequence."""

    step_id: str
    step_type: WorkflowStepType
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING
    input_summary: str = ""
    output_summary: str = ""
    tool_calls_count: int = 0
    tokens_consumed: int = 0
    cost_usd: float = 0.0
    error_message: str | None = None
    completed_at: str | None = None


class SourceProposal(BaseModel):
    """Proposal for a newly discovered external data source submitted strictly for human review."""

    domain: str
    suggested_name: str
    rationale: str
    status: str = "PENDING_HUMAN_REVIEW"
    auto_registered: bool = False  # STRICT: never auto-registered


class WorkflowExecutionState(BaseModel):
    """Persistent state of a bounded AI workflow supporting idempotent resumption."""

    workflow_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_name: str
    status: str = "RUNNING"  # RUNNING | COMPLETED | FAILED | ABORTED
    limits: WorkflowLimits = Field(default_factory=WorkflowLimits)
    steps: list[WorkflowStep] = Field(default_factory=list)
    total_steps_executed: int = 0
    total_tool_calls: int = 0
    total_tokens_consumed: int = 0
    total_cost_usd: float = 0.0
    elapsed_seconds: float = 0.0
    published_outputs: list[str] = Field(default_factory=list)
    proposed_sources: list[SourceProposal] = Field(default_factory=list)
    audit_events: list[dict[str, Any]] = Field(default_factory=list)


def sanitize_audit_log(text: str) -> str:
    """Mask any accidental secrets, tokens, or credentials before writing to audit trail."""
    sanitized = text
    for pat in SECRET_PATTERNS:
        sanitized = pat.sub("[REDACTED_SECRET]", sanitized)
    return sanitized


class BoundedWorkflowRunner:
    """Orchestrator enforcing strict ceilings, concurrency budgets, and idempotent recovery."""

    def __init__(
        self,
        budget_guard: BudgetGuard | None = None,
        default_limits: WorkflowLimits | None = None,
    ) -> None:
        self.budget_guard = budget_guard or BudgetGuard()
        self.default_limits = default_limits or WorkflowLimits()

    def create_workflow(
        self,
        workflow_name: str,
        steps: list[WorkflowStep],
        limits: WorkflowLimits | None = None,
    ) -> WorkflowExecutionState:
        """Initialize a new bounded workflow state with versioned limits."""
        active_limits = limits or self.default_limits
        return WorkflowExecutionState(
            workflow_name=workflow_name,
            limits=active_limits,
            steps=steps,
        )

    def check_limits(
        self,
        state: WorkflowExecutionState,
        additional_steps: int = 0,
        additional_tools: int = 0,
        additional_tokens: int = 0,
        additional_cost_usd: float = 0.0,
        elapsed_seconds: float = 0.0,
    ) -> None:
        """Enforce strict workflow limits and throw WorkflowLimitExceededError if exceeded."""
        lim = state.limits

        if state.total_steps_executed + additional_steps > lim.max_steps:
            raise WorkflowLimitExceededError(
                "max_steps",
                state.total_steps_executed + additional_steps,
                lim.max_steps,
            )

        if state.total_tool_calls + additional_tools > lim.max_tool_calls:
            raise WorkflowLimitExceededError(
                "max_tool_calls",
                state.total_tool_calls + additional_tools,
                lim.max_tool_calls,
            )

        if state.total_tokens_consumed + additional_tokens > lim.max_tokens:
            raise WorkflowLimitExceededError(
                "max_tokens",
                state.total_tokens_consumed + additional_tokens,
                lim.max_tokens,
            )

        if elapsed_seconds > lim.max_duration_seconds:
            raise WorkflowLimitExceededError(
                "max_duration_seconds",
                elapsed_seconds,
                lim.max_duration_seconds,
            )

        if state.total_cost_usd + additional_cost_usd > lim.max_budget_usd:
            raise WorkflowLimitExceededError(
                "max_budget_usd",
                round(state.total_cost_usd + additional_cost_usd, 5),
                lim.max_budget_usd,
            )

    def execute_step(
        self,
        state: WorkflowExecutionState,
        step_id: str,
        step_func: Callable[[], dict[str, Any]],
        start_time: float,
    ) -> dict[str, Any]:
        """Execute a single workflow step safely under atomic budget and ceiling checks."""
        # Find step
        step = next((s for s in state.steps if s.step_id == step_id), None)
        if step is None:
            raise ValueError(f"Étape inconnue '{step_id}' dans le workflow.")

        if step.status == WorkflowStepStatus.COMPLETED:
            # Idempotence: skip already completed step
            logger.info("Step %s already completed. Skipping without side-effects.", step_id)
            return {"status": "skipped", "step_id": step_id}

        step.status = WorkflowStepStatus.RUNNING

        elapsed = time.monotonic() - start_time
        self.check_limits(state, additional_steps=1, elapsed_seconds=elapsed)

        # Estimate cost (baseline $0.0001 per step)
        estimated_step_cost = 0.0001
        self.budget_guard.check_and_reserve(estimated_step_cost)

        try:
            result = step_func()
        except Exception as exc:
            self.budget_guard.rollback_reservation(estimated_step_cost)
            step.status = WorkflowStepStatus.FAILED
            step.error_message = str(exc)
            state.status = "FAILED"
            raise exc

        # Inspect outputs for hostile injection attempts
        output_str = str(result)
        for pattern in PROHIBITED_INJECTION_PATTERNS:
            if pattern in output_str.lower():
                self.budget_guard.rollback_reservation(estimated_step_cost)
                step.status = WorkflowStepStatus.FAILED
                state.status = "ABORTED"
                raise HostileDocumentDetectedError(
                    f"Tentative de manipulation hostile détectée dans le document : '{pattern}'."
                )

        # Handle proposed external sources (isolate for human review, forbid auto-registration)
        if "propose_source" in result:
            src_info = result["propose_source"]
            proposal = SourceProposal(
                domain=src_info.get("domain", "unknown"),
                suggested_name=src_info.get("name", "Unnamed Source"),
                rationale=src_info.get("rationale", "Extracted reference"),
                status="PENDING_HUMAN_REVIEW",
                auto_registered=False,  # Enforce strict human review gate
            )
            state.proposed_sources.append(proposal)

        # Update step metrics
        step.status = WorkflowStepStatus.COMPLETED
        step.output_summary = sanitize_audit_log(result.get("summary", "Step executed successfully"))
        step.tool_calls_count = result.get("tool_calls", 1)
        step.tokens_consumed = result.get("tokens", 150)
        step.cost_usd = result.get("cost_usd", estimated_step_cost)
        step.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Update cumulative state
        state.total_steps_executed += 1
        state.total_tool_calls += step.tool_calls_count
        state.total_tokens_consumed += step.tokens_consumed
        state.total_cost_usd += step.cost_usd
        state.elapsed_seconds = round(time.monotonic() - start_time, 2)

        # Audit event
        state.audit_events.append(
            {
                "step_id": step_id,
                "step_type": step.step_type.value,
                "status": step.status.value,
                "cost_usd": step.cost_usd,
                "tokens": step.tokens_consumed,
                "tool_calls": step.tool_calls_count,
            }
        )

        return result

    def publish_output(
        self,
        state: WorkflowExecutionState,
        output_id: str,
        content: str,
    ) -> bool:
        """Idempotently publish a workflow output, strictly preventing duplicate publication."""
        if output_id in state.published_outputs:
            logger.warning("Output '%s' already published. Skipping duplicate publication.", output_id)
            return False  # Not re-published

        state.published_outputs.append(output_id)
        logger.info("Output '%s' safely published for workflow %s.", output_id, state.workflow_id)
        return True  # Freshly published

    def resume_workflow(
        self,
        state: WorkflowExecutionState,
        step_executors: dict[str, Callable[[], dict[str, Any]]],
    ) -> WorkflowExecutionState:
        """Resume a workflow execution from its persistent state without repeating completed steps."""
        start_time = time.monotonic()
        state.status = "RUNNING"

        for step in state.steps:
            if step.status == WorkflowStepStatus.COMPLETED:
                continue  # Skip already completed step

            executor = step_executors.get(step.step_id)
            if executor is None:
                raise ValueError(f"Exécuteur manquant pour l'étape '{step.step_id}'.")

            self.execute_step(state, step.step_id, executor, start_time)

        state.status = "COMPLETED"
        return state
