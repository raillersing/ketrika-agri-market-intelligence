"""Every transport boundary enforces the still-closed human gate (ADR-122)."""

from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from ketrika.alerts.notifier import (
    send_pipeline_failure_email,
    send_smtp_alert,
    send_telegram_alert,
)
from ketrika.bulletin.service import send_bulletin_preview_to_mailpit
from ketrika.core.models.db import Alert, Bulletin
from ketrika.core.settings import Settings


def _alert() -> Alert:
    return Alert(
        alert_id=uuid4(),
        rule_code="TEST",
        title="Capture test",
        dedupe_key="test",
        state="open",
        severity="low",
        evidence={},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


@pytest.mark.parametrize("enabled", [0, 1])
@pytest.mark.parametrize(
    "host,port,environment",
    [
        ("smtp.example.invalid", 1025, "dev"),
        ("mailpit.evil.invalid", 1025, "test"),
        ("localhost", 1025, "dev"),
        ("mailpit", 25, "dev"),
        ("mailpit", 1025, "prod"),
    ],
)
def test_smtp_alert_and_incident_refuse_before_transport(enabled, host, port, environment):
    settings = (Settings.model_construct if environment == "prod" else Settings)(
        app_env=environment, smtp_host=host, smtp_port=port, external_send_enabled=enabled
    )
    with patch("smtplib.SMTP") as smtp:
        assert not send_smtp_alert(_alert(), settings=settings)
        assert not send_pipeline_failure_email("test", "run-test", "test", settings=settings)
        smtp.assert_not_called()


@pytest.mark.parametrize("enabled", [0, 1])
def test_telegram_does_not_construct_any_http_transport(enabled):
    settings = Settings(
        external_send_enabled=enabled, telegram_bot_token="test-only", telegram_chat_id="test-only"
    )
    with patch("httpx.Client") as client:
        assert not send_telegram_alert(_alert(), settings=settings)
        client.assert_not_called()


def test_preview_parameters_cannot_route_to_external_smtp():
    bulletin = Bulletin(
        bulletin_id=uuid4(), period_start=date(2026, 10, 1), period_end=date(2026, 10, 7)
    )
    with patch("smtplib.SMTP") as smtp:
        assert not send_bulletin_preview_to_mailpit(
            bulletin, "<p>draft</p>", smtp_host="smtp.example.invalid"
        )
        smtp.assert_not_called()


def test_success_only_after_local_transport_acceptance():
    settings = Settings(app_env="test", smtp_host="mailpit", smtp_port=1025)
    with patch("smtplib.SMTP") as smtp:
        smtp.return_value.__enter__.return_value = MagicMock()
        assert send_smtp_alert(_alert(), settings=settings)
        smtp.assert_called_once_with("mailpit", 1025, timeout=10)
        smtp.return_value.__enter__.return_value.send_message.assert_called_once()
    with patch("smtplib.SMTP", side_effect=OSError("must not be logged verbatim")):
        assert not send_pipeline_failure_email("test", "run-test", "test", settings=settings)
