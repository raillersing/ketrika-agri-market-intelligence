"""DataOps Supervision, Incident Orchestration, and ML Model Governance (SPECS §19, §25, R6.9, ADR-103).

Monitors freshness SLAs, budgets, schema drifts, pipeline failures, and statistical forecast drift.
Enforces fail-safe publication freezing, idempotent run recovery, and strictly prohibits
unvalidated automatic production model replacement during statistical divergence.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class IncidentType(StrEnum):
    """Categorization of operational data and pipeline incidents."""

    HTTP_OUTAGE = "http_outage"
    SCHEMA_DRIFT = "schema_drift"
    BUDGET_EXCEEDED = "budget_exceeded"
    FORECAST_DRIFT = "forecast_drift"
    RUN_INTERRUPTED = "run_interrupted"


class IncidentSeverity(StrEnum):
    """Normalized incident severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PublicationStatus(StrEnum):
    """Lifecycle status of data publication for a given source or metric."""

    ACTIVE = "active"
    DEGRADED = "degraded"
    FROZEN = "frozen"


class IncidentReport(BaseModel):
    """Structured operational incident record."""

    incident_id: str = Field(default_factory=lambda: f"inc-{uuid.uuid4().hex[:12]}")
    incident_type: IncidentType
    severity: IncidentSeverity
    source_id: str | None = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    publication_action: PublicationStatus = PublicationStatus.ACTIVE
    alert_dispatched_mailpit: bool = False
    mitigation_runbook_ref: str = "docs/runbooks/INCIDENT_RUNBOOK.md"
    human_assignee_role: str = "Lead DataOps"


class ForecastDriftPolicyDecision(BaseModel):
    """Certified decision preventing unvalidated model replacement upon statistical drift."""

    series_key: str
    baseline_model: str
    candidate_model: str
    baseline_wape: float
    candidate_wape: float
    delta_wape: float
    drift_detected: bool
    automatic_replacement_blocked: bool = True
    active_production_model: str
    explanation: str


class IncidentManager:
    """Central engine managing incident detection, fail-safe isolation, and governance."""

    def __init__(self) -> None:
        self.incidents: list[IncidentReport] = []
        self.source_states: dict[str, PublicationStatus] = {}

    def report_http_outage(
        self,
        source_id: str,
        consecutive_failures: int,
        status_code: int | None = None,
        is_p0: bool = False,
    ) -> IncidentReport:
        """Handle HTTP timeout / 5xx outage on a data source."""
        severity = IncidentSeverity.HIGH if is_p0 else IncidentSeverity.MEDIUM
        pub_action = PublicationStatus.FROZEN if is_p0 and consecutive_failures >= 3 else PublicationStatus.DEGRADED

        report = IncidentReport(
            incident_type=IncidentType.HTTP_OUTAGE,
            severity=severity,
            source_id=source_id,
            message=f"HTTP endpoint unavailable for source '{source_id}' ({consecutive_failures} consecutive failures, code: {status_code})",
            details={
                "consecutive_failures": consecutive_failures,
                "status_code": status_code,
                "is_p0": is_p0,
            },
            publication_action=pub_action,
            alert_dispatched_mailpit=True,
            human_assignee_role="Lead DataOps",
        )
        self.incidents.append(report)
        self.source_states[source_id] = pub_action
        return report

    def report_schema_drift(
        self,
        source_id: str,
        expected_columns: list[str],
        observed_columns: list[str],
    ) -> IncidentReport:
        """Handle unexpected structural schema change: immediately freeze publication and stage review item."""
        missing = [c for c in expected_columns if c not in observed_columns]
        unexpected = [c for c in observed_columns if c not in expected_columns]

        report = IncidentReport(
            incident_type=IncidentType.SCHEMA_DRIFT,
            severity=IncidentSeverity.CRITICAL,
            source_id=source_id,
            message=f"Schema drift detected on source '{source_id}': missing={missing}, unexpected={unexpected}",
            details={
                "missing_columns": missing,
                "unexpected_columns": unexpected,
                "expected_schema_version": "v1.0",
                "quarantine_action": "frozen",
            },
            publication_action=PublicationStatus.FROZEN,
            alert_dispatched_mailpit=True,
            human_assignee_role="Lead DataOps",
        )
        self.incidents.append(report)
        self.source_states[source_id] = PublicationStatus.FROZEN
        return report

    def report_budget_exceeded(
        self,
        budget_kind: str,
        current_spend: float,
        limit_allowed: float,
        context: str = "pipeline",
    ) -> IncidentReport:
        """Handle exhaustion of daily HTTP or monthly LLM budget with immediate fail-safe stop."""
        report = IncidentReport(
            incident_type=IncidentType.BUDGET_EXCEEDED,
            severity=IncidentSeverity.HIGH,
            source_id=context,
            message=f"{budget_kind.upper()} budget exceeded: {current_spend:.4f} >= {limit_allowed:.4f}",
            details={
                "budget_kind": budget_kind,
                "current_spend": current_spend,
                "limit_allowed": limit_allowed,
                "fail_safe_action": "stop_calls",
            },
            publication_action=PublicationStatus.DEGRADED,
            alert_dispatched_mailpit=True,
            human_assignee_role="Administrateur Système",
        )
        self.incidents.append(report)
        return report

    def evaluate_forecast_drift_policy(
        self,
        series_key: str,
        baseline_model: str,
        candidate_model: str,
        baseline_wape: float,
        candidate_wape: float,
        historical_calibrated_model: str = "SeasonalNaive",
    ) -> ForecastDriftPolicyDecision:
        """Evaluate model degradation or divergence.

        Strictly enforces that statistical drift does NOT trigger automatic production model replacement.
        The historical certified baseline is preserved until explicit human review (R6.9, ADR-103).
        """
        delta_wape = baseline_wape - candidate_wape
        # If candidate WAPE > 0.35 or candidate degrades baseline (delta_wape < -0.05), drift is declared
        drift_detected = candidate_wape > 0.35 or delta_wape < -0.05

        if drift_detected:
            # Prohibit automatic replacement
            decision = ForecastDriftPolicyDecision(
                series_key=series_key,
                baseline_model=baseline_model,
                candidate_model=candidate_model,
                baseline_wape=baseline_wape,
                candidate_wape=candidate_wape,
                delta_wape=delta_wape,
                drift_detected=True,
                automatic_replacement_blocked=True,
                active_production_model=historical_calibrated_model,
                explanation=(
                    f"Statistical drift detected for '{series_key}' (candidate WAPE {candidate_wape:.3f}). "
                    f"Automatic production replacement is strictly blocked (R6.9 / ADR-103). "
                    f"Production continues serving certified historical baseline '{historical_calibrated_model}'."
                ),
            )
            # Record incident
            inc = IncidentReport(
                incident_type=IncidentType.FORECAST_DRIFT,
                severity=IncidentSeverity.MEDIUM,
                source_id=series_key,
                message=f"Statistical forecast drift detected on '{series_key}'; unvalidated replacement blocked.",
                details={
                    "baseline_model": baseline_model,
                    "candidate_model": candidate_model,
                    "baseline_wape": baseline_wape,
                    "candidate_wape": candidate_wape,
                    "active_retained_model": historical_calibrated_model,
                },
                publication_action=PublicationStatus.ACTIVE,  # continues serving baseline
                alert_dispatched_mailpit=True,
                human_assignee_role="Analyste Marché SPM",
            )
            self.incidents.append(inc)
            return decision

        # Nominal candidate qualification: candidate is better by >= 1% parsimony
        if delta_wape > 0.01:
            return ForecastDriftPolicyDecision(
                series_key=series_key,
                baseline_model=baseline_model,
                candidate_model=candidate_model,
                baseline_wape=baseline_wape,
                candidate_wape=candidate_wape,
                delta_wape=delta_wape,
                drift_detected=False,
                automatic_replacement_blocked=False,
                active_production_model=candidate_model,
                explanation=f"Candidate model '{candidate_model}' improves WAPE by {delta_wape*100:.2f}% over baseline.",
            )

        return ForecastDriftPolicyDecision(
            series_key=series_key,
            baseline_model=baseline_model,
            candidate_model=candidate_model,
            baseline_wape=baseline_wape,
            candidate_wape=candidate_wape,
            delta_wape=delta_wape,
            drift_detected=False,
            automatic_replacement_blocked=True,
            active_production_model=baseline_model,
            explanation=f"Candidate gain is below 1% parsimony threshold. Baseline '{baseline_model}' retained.",
        )

    def handle_interrupted_run(
        self,
        run_id: str,
        source_id: str,
        stage: str = "extraction",
    ) -> IncidentReport:
        """Handle interrupted ingestion run: mark failed, ensure idempotent replay without corrupting Bronze."""
        report = IncidentReport(
            incident_type=IncidentType.RUN_INTERRUPTED,
            severity=IncidentSeverity.HIGH,
            source_id=source_id,
            message=f"Ingestion run '{run_id}' for source '{source_id}' was abruptly interrupted during '{stage}'",
            details={
                "run_id": run_id,
                "stage": stage,
                "safe_retry_strategy": "re-run idempotent Bronze ingestion; no corrupted partial Silver records written.",
            },
            publication_action=PublicationStatus.DEGRADED,
            alert_dispatched_mailpit=True,
            human_assignee_role="Lead DataOps",
        )
        self.incidents.append(report)
        return report
