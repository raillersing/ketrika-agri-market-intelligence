"""Unit tests for Market Intelligence alerts rules, notifier, and H3 gate (SPECS §18)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from ketrika.alerts.notifier import (
    dispatch_alert_notifications,
    format_alert_email_body,
    send_smtp_alert,
    send_telegram_alert,
)
from ketrika.alerts.rules import load_crop_calendar_sensitive_months
from ketrika.core.models.db import Alert
from ketrika.core.settings import Settings


def test_load_crop_calendar_sensitive_months() -> None:
    """Test loading and parsing of sensitive agricultural calendar months."""
    cal_map = load_crop_calendar_sensitive_months()
    assert isinstance(cal_map, dict)
    assert len(cal_map) > 0
    # Analamanga should be in calendar
    found = any("analamanga" in k for k in cal_map)
    assert found is True


def test_format_alert_email_body() -> None:
    """Test plaintext and HTML generation for alerts."""
    now = datetime.now(UTC)
    alert = Alert(
        alert_id=uuid.uuid4(),
        rule_code="PRICE_SPIKE",
        dedupe_key="PRICE_SPIKE|rice_milled_local|MG-T|2026-09",
        severity="high",
        title="Flambée des prix : Riz blanc local à Analamanga (+25% sur 1 mois)",
        evidence={"chg_1m": 0.25, "z_score": 3.4, "n_sources": 2},
        state="open",
        first_seen_at=now,
        last_seen_at=now,
    )

    text_body, html_body = format_alert_email_body(alert)
    assert "Flambée des prix" in text_body
    assert "PRICE_SPIKE|rice_milled_local|MG-T|2026-09" in text_body
    assert "badge-high" in html_body
    assert "http://localhost:3005/alerts" in html_body


def test_telegram_send_neutralized_when_external_send_disabled() -> None:
    """AGENTS.md Gate H3: When EXTERNAL_SEND_ENABLED=0, Telegram send is strictly neutralized."""
    settings = Settings(
        external_send_enabled=0,
        telegram_bot_token="test_bot_token_123",
        telegram_chat_id="12345678",
    )
    alert = Alert(
        alert_id=uuid.uuid4(),
        rule_code="PRICE_SPIKE",
        dedupe_key="PRICE_SPIKE|test|test|2026-09",
        severity="high",
        title="Test Alert",
        evidence={},
        state="open",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )

    with patch("httpx.Client.post") as mock_post:
        res = send_telegram_alert(alert, settings=settings)
        assert res is False
        mock_post.assert_not_called()


def test_telegram_send_executed_when_external_send_enabled() -> None:
    """When EXTERNAL_SEND_ENABLED=1 and credentials provided, Telegram API POST is made."""
    settings = Settings(
        external_send_enabled=1,
        telegram_bot_token="valid_token",
        telegram_chat_id="99999",
    )
    alert = Alert(
        alert_id=uuid.uuid4(),
        rule_code="PRICE_SPIKE",
        dedupe_key="PRICE_SPIKE|test|test|2026-09",
        severity="high",
        title="Test Alert",
        evidence={},
        state="open",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )

    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        res = send_telegram_alert(alert, settings=settings)
        assert res is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "https://api.telegram.org/botvalid_token/sendMessage" in args[0]
        assert kwargs["json"]["chat_id"] == "99999"


def test_dispatch_alert_notifications() -> None:
    """Test full dispatch routing to email and telegram channels."""
    settings = Settings(
        external_send_enabled=0,
        smtp_host="mailpit",
        smtp_port=1025,
    )
    alert = Alert(
        alert_id=uuid.uuid4(),
        rule_code="PRICE_DROP",
        dedupe_key="PRICE_DROP|test|test|2026-09",
        severity="medium",
        title="Test Price Drop",
        evidence={},
        state="open",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )

    with patch("ketrika.alerts.notifier.send_smtp_alert", return_value=True) as mock_smtp:
        res = dispatch_alert_notifications(alert, settings=settings)
        assert res["email"] is True
        assert res["telegram"] is False
        mock_smtp.assert_called_once()


def test_smtp_send_failure_handled() -> None:
    """Test SMTP connection error handling."""
    settings = Settings(
        smtp_host="invalid_host_12345",
        smtp_port=9999,
    )
    alert = Alert(
        alert_id=uuid.uuid4(),
        rule_code="TEST",
        dedupe_key="TEST|key",
        severity="low",
        title="Test",
        evidence={},
        state="open",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    res = send_smtp_alert(alert, settings=settings)
    assert res is False


def test_telegram_send_failure_handled() -> None:
    """Test Telegram HTTP error handling."""
    settings = Settings(
        external_send_enabled=1,
        telegram_bot_token="test_tok",
        telegram_chat_id="test_chat",
    )
    alert = Alert(
        alert_id=uuid.uuid4(),
        rule_code="TEST",
        dedupe_key="TEST|key",
        severity="low",
        title="Test",
        evidence={},
        state="open",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    with patch("httpx.Client.post", side_effect=Exception("Network error")):
        res = send_telegram_alert(alert, settings=settings)
        assert res is False


def test_evaluate_rules_unit_scenarios() -> None:
    """Test all rule evaluation generators with simulated query returns."""
    from types import SimpleNamespace

    from ketrika.alerts.rules import (
        evaluate_all_rules,
        evaluate_climate_risk_rules,
        evaluate_data_stale_rules,
        evaluate_price_drop_rules,
        evaluate_price_spike_rules,
        evaluate_stockout_risk_rules,
    )

    mock_session = MagicMock()

    # 1. Price Drop
    mock_session.execute.return_value.fetchall.return_value = [
        SimpleNamespace(
            product_id=uuid.uuid4(),
            product_code="rice_milled_local",
            product_name="Riz blanc local",
            location_id=uuid.uuid4(),
            location_pcode="MG-T",
            location_name="Analamanga",
            month="2026-09-01",
            median_price=2100.0,
            chg_1m=-0.22,
            z_score_robust=-3.5,
            chosen_source_id="miasa_odr",
        )
    ]
    drops = evaluate_price_drop_rules(mock_session)
    assert len(drops) == 1
    assert drops[0].rule_code == "PRICE_DROP"
    assert drops[0].severity == "medium"
    assert "PRICE_DROP|rice_milled_local|MG-T|2026-09" == drops[0].dedupe_key

    # 2. Stockout Risk
    mock_session.execute.return_value.fetchall.return_value = [
        SimpleNamespace(
            product_id=uuid.uuid4(),
            product_code="rice_milled_local",
            product_name="Riz blanc local",
            location_id=uuid.uuid4(),
            location_pcode="MG-T",
            location_name="Analamanga",
            latest_status="shortage",
            prev_status="tight",
            latest_coverage_days=5.0,
            latest_quantity_value=20.0,
            latest_period="2026-09-15",
            chg_1m=0.12,
        )
    ]
    stockouts = evaluate_stockout_risk_rules(mock_session)
    assert len(stockouts) == 1
    assert stockouts[0].rule_code == "STOCKOUT_RISK"
    assert (
        stockouts[0].severity == "high"
    )  # because latest is 'shortage' with documented critical coverage <= 7 days (ADR-100)

    # 3. Climate Risk
    mock_session.execute.return_value.fetchall.return_value = [
        SimpleNamespace(
            location_id=uuid.uuid4(),
            location_pcode="MG-T",
            location_name="Analamanga",
            month=datetime(2026, 11, 1),
            precip_total_mm=30.0,
            baseline_precip_mm=100.0,
            rain_anom_pct=-0.70,
        )
    ]
    climate_alerts = evaluate_climate_risk_rules(mock_session)
    assert len(climate_alerts) == 1
    assert climate_alerts[0].rule_code == "CLIMATE_RISK"
    assert climate_alerts[0].severity == "high"  # anomaly < -0.50

    # 4. Data Stale
    mock_session.execute.return_value.fetchall.return_value = [
        SimpleNamespace(
            source_id="mincc_ppn",
            priority="P0",
            freshness_sla_days=15,
            freshness_days=22,
            is_stale=True,
            last_run_started_at=datetime(2026, 9, 15, tzinfo=UTC),
        )
    ]
    stales = evaluate_data_stale_rules(mock_session)
    assert len(stales) == 1
    assert stales[0].rule_code == "DATA_STALE"
    assert stales[0].severity == "low"

    # 5. Price Spike
    mock_session.execute.return_value.fetchall.return_value = [
        SimpleNamespace(
            product_id=uuid.uuid4(),
            product_code="rice_milled_local",
            product_name="Riz blanc local",
            location_id=uuid.uuid4(),
            location_pcode="MG-T",
            location_name="Analamanga",
            month="2026-09-01",
            median_price=2850.0,
            chg_1m=0.25,
            z_score_robust=3.5,
            chosen_source_id="miasa_odr",
            n_sources=2,
            sources=["miasa_odr", "wfp_hdx_mdg"],
        )
    ]
    spikes = evaluate_price_spike_rules(mock_session)
    assert len(spikes) == 1
    assert spikes[0].rule_code == "PRICE_SPIKE"
    assert spikes[0].severity == "high"

    # 6. Evaluate all rules when queries return empty
    mock_session.execute.return_value.fetchall.return_value = []
    all_cands = evaluate_all_rules(mock_session)
    assert len(all_cands) == 0
