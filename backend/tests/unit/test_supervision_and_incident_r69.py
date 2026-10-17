"""Normative Acceptance Tests for DataOps Supervision, Incidents & Model Drift Governance (R6.9, ADR-103, SPECS §19, §25).

Verifies:
1. HTTP outage handling: consecutive timeouts trigger degraded/frozen publication and Mailpit notification without fake successes.
2. Schema drift handling: unexpected columns or missing fields freeze publication into quarantine.
3. Budget exhaustion handling: exceeding HTTP daily budget or LLM monthly limit triggers fail-safe stop.
4. Forecast drift policy: statistical model divergence strictly prohibits automatic unvalidated production model replacement.
5. Parsimonious model promotion: candidate promoted only when validated improvement > 1% over baseline.
6. Interrupted run handling: abrupt crashes marked interrupted with safe idempotent Bronze/Silver retry strategy.
7. Runbook compliance and Gate H7: roles defined, zero unauthorized external communication.
"""

from __future__ import annotations

from pathlib import Path

from ketrika.ops.supervision import (
    IncidentManager,
    IncidentSeverity,
    IncidentType,
    PublicationStatus,
)


def test_http_outage_handling_and_publication_freezing() -> None:
    """R6.9 Acceptance: P0 HTTP outage freezes publication without masquerading failures."""
    manager = IncidentManager()

    # 1. Non-P0 source with 2 failures -> Degraded
    rep1 = manager.report_http_outage(
        source_id="minae_stat_mdg",
        consecutive_failures=2,
        status_code=504,
        is_p0=False,
    )
    assert rep1.incident_type == IncidentType.HTTP_OUTAGE
    assert rep1.severity == IncidentSeverity.MEDIUM
    assert rep1.publication_action == PublicationStatus.DEGRADED
    assert rep1.alert_dispatched_mailpit is True

    # 2. Critical P0 source with 3 consecutive failures -> FROZEN
    rep_p0 = manager.report_http_outage(
        source_id="wfp_hdx_mdg",
        consecutive_failures=3,
        status_code=503,
        is_p0=True,
    )
    assert rep_p0.severity == IncidentSeverity.HIGH
    assert rep_p0.publication_action == PublicationStatus.FROZEN
    assert manager.source_states["wfp_hdx_mdg"] == PublicationStatus.FROZEN


def test_schema_drift_detection_and_quarantine() -> None:
    """R6.9 Acceptance: Schema drift freezes publication and creates an isolated incident."""
    manager = IncidentManager()

    expected = ["date", "market", "product", "price_ariary", "unit"]
    observed = ["date", "market", "commodity_name", "price_ariary"]  # missing 'product', 'unit'; unexpected 'commodity_name'

    report = manager.report_schema_drift(
        source_id="odr_rice_mdg",
        expected_columns=expected,
        observed_columns=observed,
    )

    assert report.incident_type == IncidentType.SCHEMA_DRIFT
    assert report.severity == IncidentSeverity.CRITICAL
    assert report.publication_action == PublicationStatus.FROZEN
    assert "missing_columns" in report.details
    assert "product" in report.details["missing_columns"]
    assert "unexpected_columns" in report.details
    assert "commodity_name" in report.details["unexpected_columns"]
    assert manager.source_states["odr_rice_mdg"] == PublicationStatus.FROZEN


def test_budget_exceeded_fail_safe_trigger() -> None:
    """R6.9 Acceptance: Exhausted budget triggers fail-safe stop and alerts."""
    manager = IncidentManager()

    # 1. LLM monthly budget exceeded
    rep_llm = manager.report_budget_exceeded(
        budget_kind="llm_monthly",
        current_spend=20.05,
        limit_allowed=20.00,
        context="gemini_extraction",
    )
    assert rep_llm.incident_type == IncidentType.BUDGET_EXCEEDED
    assert rep_llm.severity == IncidentSeverity.HIGH
    assert rep_llm.publication_action == PublicationStatus.DEGRADED
    assert rep_llm.details["fail_safe_action"] == "stop_calls"
    assert rep_llm.human_assignee_role == "Administrateur Système"

    # 2. HTTP daily requests budget exceeded
    rep_http = manager.report_budget_exceeded(
        budget_kind="http_daily",
        current_spend=501,
        limit_allowed=500,
        context="inflow_scraper",
    )
    assert rep_http.incident_type == IncidentType.BUDGET_EXCEEDED
    assert rep_http.details["current_spend"] == 501


def test_forecast_drift_policy_strictly_prohibits_automatic_replacement() -> None:
    """R6.9 Acceptance: Statistical divergence strictly prohibits unvalidated model replacement."""
    manager = IncidentManager()

    # Candidate model exhibits heavy degradation (WAPE = 0.42 > 0.35 limit)
    decision = manager.evaluate_forecast_drift_policy(
        series_key="rice_gasikara_vakinankaratra",
        baseline_model="SeasonalNaive",
        candidate_model="ExperimentalDeepAR",
        baseline_wape=0.18,
        candidate_wape=0.42,
        historical_calibrated_model="SeasonalNaive",
    )

    assert decision.drift_detected is True
    assert decision.automatic_replacement_blocked is True
    assert decision.active_production_model == "SeasonalNaive"
    assert "Automatic production replacement is strictly blocked" in decision.explanation

    # Verify incident was logged
    drift_incidents = [i for i in manager.incidents if i.incident_type == IncidentType.FORECAST_DRIFT]
    assert len(drift_incidents) == 1
    assert drift_incidents[0].source_id == "rice_gasikara_vakinankaratra"
    assert drift_incidents[0].human_assignee_role == "Analyste Marché SPM"


def test_forecast_parsimonious_model_promotion() -> None:
    """R6.9 Acceptance: Model is promoted only when gain exceeds parsimony threshold (>1%)."""
    manager = IncidentManager()

    # 1. Gain is 3.5% (> 1%) -> Validated promotion
    decision_promoted = manager.evaluate_forecast_drift_policy(
        series_key="maize_dry_atsimo_andrefana",
        baseline_model="SeasonalNaive",
        candidate_model="AutoETS",
        baseline_wape=0.22,
        candidate_wape=0.185,  # delta = +0.035
    )
    assert decision_promoted.drift_detected is False
    assert decision_promoted.automatic_replacement_blocked is False
    assert decision_promoted.active_production_model == "AutoETS"

    # 2. Insignificant gain of 0.4% (<= 1%) -> Retain baseline by parsimony
    decision_parsimony = manager.evaluate_forecast_drift_policy(
        series_key="cassava_fresh_analamanga",
        baseline_model="NaiveLast",
        candidate_model="ComplexARIMA",
        baseline_wape=0.150,
        candidate_wape=0.146,  # delta = +0.004 <= 0.010
    )
    assert decision_parsimony.drift_detected is False
    assert decision_parsimony.automatic_replacement_blocked is True
    assert decision_parsimony.active_production_model == "NaiveLast"


def test_interrupted_run_handling_and_idempotent_recovery() -> None:
    """R6.9 Acceptance: Abruptly interrupted ingestion run is logged with safe idempotent strategy."""
    manager = IncidentManager()

    report = manager.handle_interrupted_run(
        run_id="run-20261017-0915-interrupted",
        source_id="wfp_hdx_mdg",
        stage="transformation_silver",
    )

    assert report.incident_type == IncidentType.RUN_INTERRUPTED
    assert report.severity == IncidentSeverity.HIGH
    assert report.details["run_id"] == "run-20261017-0915-interrupted"
    assert "idempotent" in report.details["safe_retry_strategy"]


def test_supervision_runbook_documentation_and_gate_h7() -> None:
    """R6.9 Acceptance: Incident runbook specifies human roles and enforces Gate H7."""
    repo_root = Path("/workspace")
    if not repo_root.exists():
        repo_root = Path(__file__).resolve().parents[3]

    runbook_path = repo_root / "docs" / "runbooks" / "INCIDENT_RUNBOOK.md"
    assert runbook_path.exists(), f"Runbook missing at {runbook_path}"

    content = runbook_path.read_text(encoding="utf-8")

    # Roles verification
    assert "Lead DataOps" in content
    assert "Analyste Marché" in content
    assert "Administrateur Système" in content

    # All 5 incident types covered
    assert "http_outage" in content
    assert "schema_drift" in content
    assert "budget_exceeded" in content
    assert "forecast_drift" in content
    assert "run_interrupted" in content

    # Gate H7: strict prohibition of autonomous external communication
    assert "Gate H7" in content
    assert "Mailpit" in content
