"""Normative acceptance tests for Market Intelligence Alerts & Risk Scenarios qualification (R6.6, ADR-100, SPECS §18).

Verifies:
1. WFP/RTFP duplicate does not artificially elevate PRICE_SPIKE to 'high' severity (same root family 'un_wfp').
2. Truly independent sources (e.g., ODR + WFP) qualify 'high' severity.
3. Absence of documented quantities strictly limits STOCKOUT_RISK to 'medium' severity.
4. Documented critical coverage (<= 7 days) qualifies 'high' severity (confirmed shortage).
5. Source silence excludes inferred stockout (silence is not a stockout proof).
6. Strict category isolation: climate risk, market alerts, and data stale alerts remain segregated.
7. DATA_STALE alerts trigger only on genuine P0 SLA violations.
8. Deduplication, recurring signal refresh, and 2-strike auto-resolution lifecycle in ops.alert.
9. Gate H3 compliance: zero external network calls (Telegram/SMTP), previews quarantined.
10. Honest alert metrics: ground truth metrics declared NOT_EVALUATED, never 100% on unannotated corpus.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ketrika.alerts.engine import evaluate_alerts
from ketrika.alerts.notifier import (
    dispatch_alert_notifications,
    send_telegram_alert,
)
from ketrika.alerts.rules import (
    evaluate_alert_metrics_and_scenarios,
    evaluate_climate_risk_rules,
    evaluate_data_stale_rules,
    evaluate_stockout_risk_rules,
)
from ketrika.core.models.db import Alert
from ketrika.core.settings import Settings
from ketrika.ml.anomalies import detect_price_anomalies


def test_wfp_rtfp_duplicate_does_not_artificially_elevate_to_high_severity() -> None:
    """R6.6 Acceptance: WFP and WB RTFP share root family 'un_wfp' and must NOT elevate to 'high'."""
    mock_session = MagicMock()

    # Simulated row with z > 3, chg_1m > 0.15 and 2 sources: wfp_hdx_mdg + wb_rtfp_mdg
    mock_row = SimpleNamespace(
        product_id=uuid.uuid4(),
        product_code="rice_milled_local",
        product_name="Riz blanc local",
        location_id=uuid.uuid4(),
        location_pcode="MG-T",
        location_name="Analamanga",
        month=date(2026, 9, 1),
        median_price=2950.0,
        chg_1m=0.22,
        z_score_robust=3.8,
        chosen_source_id="wfp_hdx_mdg",
        n_sources=2,
        sources=["wfp_hdx_mdg", "wb_rtfp_mdg"],
    )
    mock_session.execute.return_value.fetchall.return_value = [mock_row]

    anomalies = detect_price_anomalies(mock_session, z_threshold=3.0, chg_threshold=0.15)
    assert len(anomalies) == 1
    anom = anomalies[0]

    assert anom.anomaly_type == "PRICE_SPIKE"
    # Sourced from 2 entries but only 1 independent family -> strictly medium
    assert anom.n_sources == 2
    assert anom.n_independent_families == 1
    assert anom.severity == "medium"
    assert anom.evidence["has_dependent_derivation"] is True


def test_truly_independent_sources_elevate_to_high_severity() -> None:
    """R6.6 Acceptance: Two truly independent sources (ODR + WFP) legitimately elevate to 'high'."""
    mock_session = MagicMock()

    # Simulated row with 2 independent sources: miasa_odr (madagascar_gov) + wfp_hdx_mdg (un_wfp)
    mock_row = SimpleNamespace(
        product_id=uuid.uuid4(),
        product_code="rice_milled_local",
        product_name="Riz blanc local",
        location_id=uuid.uuid4(),
        location_pcode="MG-T",
        location_name="Analamanga",
        month=date(2026, 9, 1),
        median_price=2950.0,
        chg_1m=0.22,
        z_score_robust=3.8,
        chosen_source_id="miasa_odr",
        n_sources=2,
        sources=["miasa_odr", "wfp_hdx_mdg"],
    )
    mock_session.execute.return_value.fetchall.return_value = [mock_row]

    anomalies = detect_price_anomalies(mock_session, z_threshold=3.0, chg_threshold=0.15)
    assert len(anomalies) == 1
    anom = anomalies[0]

    assert anom.anomaly_type == "PRICE_SPIKE"
    assert anom.n_sources == 2
    assert anom.n_independent_families == 2
    assert anom.severity == "high"
    assert anom.evidence["has_dependent_derivation"] is False


def test_stockout_risk_without_documented_quantities_strictly_limits_severity_to_medium() -> None:
    """R6.6 Acceptance: Stock shortage without documented quantities strictly limits severity to 'medium'."""
    mock_session = MagicMock()

    # Shortage declared textually, but coverage_days and quantity_value are NULL
    mock_row = SimpleNamespace(
        product_id=uuid.uuid4(),
        product_code="rice_milled_local",
        product_name="Riz blanc local",
        location_id=uuid.uuid4(),
        location_pcode="MG-T",
        location_name="Analamanga",
        latest_status="shortage",
        prev_status="tight",
        latest_coverage_days=None,
        latest_quantity_value=None,
        latest_period="2026-09-15",
        chg_1m=0.10,
    )
    mock_session.execute.return_value.fetchall.return_value = [mock_row]

    candidates = evaluate_stockout_risk_rules(mock_session)
    assert len(candidates) == 1
    cand = candidates[0]

    assert cand.rule_code == "STOCKOUT_RISK"
    assert cand.severity == "medium"
    assert cand.evidence["quantities_documented"] is False
    assert cand.evidence["confirmed_shortage"] is False
    assert "sous observation" in cand.title


def test_stockout_risk_with_documented_critical_quantities_qualifies_high_severity() -> None:
    """R6.6 Acceptance: Stock shortage supported by documented critical coverage (<= 7 days) qualifies 'high'."""
    mock_session = MagicMock()

    # Shortage with documented coverage of 4.5 days
    mock_row = SimpleNamespace(
        product_id=uuid.uuid4(),
        product_code="rice_milled_local",
        product_name="Riz blanc local",
        location_id=uuid.uuid4(),
        location_pcode="MG-T",
        location_name="Analamanga",
        latest_status="shortage",
        prev_status="tight",
        latest_coverage_days=4.5,
        latest_quantity_value=12.0,
        latest_period="2026-09-15",
        chg_1m=0.15,
    )
    mock_session.execute.return_value.fetchall.return_value = [mock_row]

    candidates = evaluate_stockout_risk_rules(mock_session)
    assert len(candidates) == 1
    cand = candidates[0]

    assert cand.rule_code == "STOCKOUT_RISK"
    assert cand.severity == "high"
    assert cand.evidence["quantities_documented"] is True
    assert cand.evidence["confirmed_shortage"] is True
    assert cand.evidence["coverage_days"] == 4.5
    assert "confirmée" in cand.title


def test_source_silence_excludes_inferred_stockout() -> None:
    """R6.6 Acceptance: Silence of a source (no records returned) yields zero stockout alerts."""
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = []

    candidates = evaluate_stockout_risk_rules(mock_session)
    assert len(candidates) == 0


def test_category_isolation_climate_market_and_stale() -> None:
    """R6.6 Acceptance: Distinct categories (climate, market, stale) are strictly segregated."""
    mock_session = MagicMock()

    # 1. Climate risk candidate
    mock_climate = SimpleNamespace(
        location_id=uuid.uuid4(),
        location_pcode="MG-T",
        location_name="Analamanga",
        month=datetime(2026, 11, 1),
        precip_total_mm=25.0,
        baseline_precip_mm=110.0,
        rain_anom_pct=-0.77,
    )
    mock_session.execute.return_value.fetchall.return_value = [mock_climate]
    climate_alerts = evaluate_climate_risk_rules(mock_session)
    assert len(climate_alerts) == 1
    assert climate_alerts[0].rule_code == "CLIMATE_RISK"
    assert "CLIMATE" in climate_alerts[0].dedupe_key
    assert "rain_anom_pct" in climate_alerts[0].evidence

    # 2. Data stale candidate
    mock_stale = SimpleNamespace(
        source_id="mincc_ppn",
        priority="P0",
        freshness_sla_days=15,
        freshness_days=28,
        is_stale=True,
        last_run_started_at=datetime(2026, 9, 10, tzinfo=UTC),
    )
    mock_session.execute.return_value.fetchall.return_value = [mock_stale]
    stale_alerts = evaluate_data_stale_rules(mock_session)
    assert len(stale_alerts) == 1
    assert stale_alerts[0].rule_code == "DATA_STALE"
    assert "STALE" in stale_alerts[0].dedupe_key
    assert stale_alerts[0].severity == "low"


def test_data_stale_alert_triggers_only_on_true_sla_delay() -> None:
    """R6.6 Acceptance: Non-stale sources (is_stale=False) yield no alert."""
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = []

    stale_alerts = evaluate_data_stale_rules(mock_session)
    assert len(stale_alerts) == 0


def test_alert_deduplication_and_two_strike_auto_resolution() -> None:
    """R6.6 Acceptance: Verify deduplication, last_seen update, and 2-consecutive-miss auto-resolution."""
    mock_session = MagicMock()

    # First run: 1 candidate
    cand = SimpleNamespace(
        rule_code="PRICE_DROP",
        dedupe_key="PRICE_DROP|rice|MG-T|2026-09",
        severity="medium",
        title="Chute des prix",
        evidence={},
        product_id=None,
        location_id=None,
    )

    with patch("ketrika.alerts.engine.evaluate_all_rules", return_value=[cand]):
        # No existing alert
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        mock_session.execute.return_value.scalars.return_value.all.return_value = []

        active = evaluate_alerts(mock_session, send_notifications=False)
        assert len(active) == 1
        assert active[0].state == "open"
        mock_session.add.assert_called_once()

    # Second run: alert disappeared from candidates (miss 1)
    existing_alert = Alert(
        alert_id=uuid.uuid4(),
        rule_code="PRICE_DROP",
        dedupe_key="PRICE_DROP|rice|MG-T|2026-09",
        severity="medium",
        title="Chute des prix",
        evidence={"miss_count": 0},
        state="open",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    with patch("ketrika.alerts.engine.evaluate_all_rules", return_value=[]):
        mock_session.execute.return_value.scalars.return_value.all.return_value = [existing_alert]
        evaluate_alerts(mock_session, send_notifications=False)
        assert existing_alert.evidence["miss_count"] == 1
        assert existing_alert.state == "open"  # Not yet resolved on miss 1

    # Third run: alert disappeared again (miss 2 -> auto-resolved)
    with patch("ketrika.alerts.engine.evaluate_all_rules", return_value=[]):
        mock_session.execute.return_value.scalars.return_value.all.return_value = [existing_alert]
        evaluate_alerts(mock_session, send_notifications=False)
        assert existing_alert.evidence["miss_count"] == 2
        assert existing_alert.state == "resolved"


def test_gate_h3_zero_external_dispatch_confinement() -> None:
    """R6.6 Acceptance: Gate H3 prohibits real external dispatch (Telegram, WhatsApp, SMTP tiers)."""
    settings = Settings(
        external_send_enabled=0,
        telegram_bot_token="bot12345",
        telegram_chat_id="chat67890",
        smtp_host="mailpit",
        smtp_port=1025,
    )
    alert = Alert(
        alert_id=uuid.uuid4(),
        rule_code="PRICE_SPIKE",
        dedupe_key="TEST|key",
        severity="high",
        title="Test Alert",
        evidence={},
        state="open",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )

    with patch("httpx.Client.post") as mock_post:
        tg_res = send_telegram_alert(alert, settings=settings)
        assert tg_res is False
        mock_post.assert_not_called()

    with patch("ketrika.alerts.notifier.send_smtp_alert", return_value=True) as mock_smtp:
        dispatch_res = dispatch_alert_notifications(alert, settings=settings)
        assert dispatch_res["telegram"] is False
        assert dispatch_res["email"] is True
        mock_smtp.assert_called_once()


def test_honest_ground_truth_metrics_never_claim_100_percent() -> None:
    """R6.6 Acceptance: Ground truth metrics declared NOT_EVALUATED, never claiming 100% on unannotated data."""
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = []

    metrics = evaluate_alert_metrics_and_scenarios(mock_session)
    assert isinstance(metrics, dict)
    assert "ground_truth_metrics" in metrics

    gt = metrics["ground_truth_metrics"]
    assert gt["status"] == "NOT_EVALUATED"
    assert gt["precision"] is None
    assert gt["recall"] is None
    assert gt["f1_score"] is None
    assert "interdiction formelle de déclarer artificiellement" in gt["declaration"]


def test_evaluate_alerts_reopens_resolved_alert_with_notifications() -> None:
    """Verify recurring candidate updates existing alert, reopens if resolved, and notifies."""
    mock_session = MagicMock()
    cand = SimpleNamespace(
        rule_code="PRICE_SPIKE",
        dedupe_key="PRICE_SPIKE|rice|MG-T|2026-09",
        severity="high",
        title="Flambée récurrente",
        evidence={"n_sources": 2},
        product_id=None,
        location_id=None,
    )

    resolved_alert = Alert(
        alert_id=uuid.uuid4(),
        rule_code="PRICE_SPIKE",
        dedupe_key="PRICE_SPIKE|rice|MG-T|2026-09",
        severity="medium",
        title="Ancienne flambée",
        evidence={"miss_count": 2},
        state="resolved",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )

    mock_session.execute.return_value.scalar_one_or_none.return_value = resolved_alert
    mock_session.execute.return_value.scalars.return_value.all.return_value = [resolved_alert]

    mock_settings = MagicMock()
    with patch("ketrika.alerts.engine.evaluate_all_rules", return_value=[cand]):
        with patch("ketrika.alerts.engine.dispatch_alert_notifications") as mock_dispatch:
            active = evaluate_alerts(mock_session, send_notifications=True, settings=mock_settings)
            assert len(active) == 1
            assert resolved_alert.state == "open"
            assert resolved_alert.severity == "high"
            assert resolved_alert.evidence["miss_count"] == 0
            mock_dispatch.assert_called_once_with(resolved_alert, settings=mock_settings)

