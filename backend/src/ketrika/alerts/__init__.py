"""Ketrika Market Intelligence alerts module (SPECS §18)."""

from ketrika.alerts.engine import evaluate_alerts
from ketrika.alerts.notifier import (
    dispatch_alert_notifications,
    send_smtp_alert,
    send_telegram_alert,
)
from ketrika.alerts.rules import AlertCandidate, evaluate_all_rules

__all__ = [
    "AlertCandidate",
    "dispatch_alert_notifications",
    "evaluate_alerts",
    "evaluate_all_rules",
    "send_smtp_alert",
    "send_telegram_alert",
]
