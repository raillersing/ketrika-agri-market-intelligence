"""Alert evaluation and lifecycle state management engine (SPECS §18)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.alerts.notifier import dispatch_alert_notifications
from ketrika.alerts.rules import AlertCandidate, evaluate_all_rules
from ketrika.core.logging import get_logger
from ketrika.core.models.db import Alert
from ketrika.core.settings import Settings, get_settings

logger = get_logger(__name__)


def evaluate_alerts(
    session: Session,
    send_notifications: bool = True,
    settings: Settings | None = None,
) -> list[Alert]:
    """Execute all alert rules against Gold views and manage lifecycle states.

    Features:
    - Idempotent upsert on `dedupe_key`.
    - Updates `last_seen_at` on recurring signals.
    - Transitions alerts to `resolved` when condition is unfulfilled for 2 consecutive runs.
    - Dispatches notifications via SMTP/Telegram when a new alert is generated.
    """
    cfg = settings or get_settings()
    now_utc = datetime.now(UTC)

    # 1. Generate alert candidates from Gold views
    candidates: list[AlertCandidate] = evaluate_all_rules(session)
    logger.info("alert_rules_evaluated", candidate_count=len(candidates))

    seen_dedupe_keys: set[str] = set()
    active_alerts: list[Alert] = []

    # 2. Upsert candidate alerts
    for cand in candidates:
        seen_dedupe_keys.add(cand.dedupe_key)
        stmt = select(Alert).where(Alert.dedupe_key == cand.dedupe_key)
        existing = session.execute(stmt).scalar_one_or_none()

        if existing:
            # Recurring alert
            existing.last_seen_at = now_utc
            existing.severity = cand.severity
            existing.title = cand.title
            ev = dict(cand.evidence)
            ev["miss_count"] = 0
            existing.evidence = ev

            # If it was resolved earlier, reopen
            if existing.state == "resolved":
                existing.state = "open"
                if send_notifications:
                    dispatch_alert_notifications(existing, settings=cfg)

            active_alerts.append(existing)
        else:
            # New alert
            ev = dict(cand.evidence)
            ev["miss_count"] = 0

            new_alert = Alert(
                rule_code=cand.rule_code,
                dedupe_key=cand.dedupe_key,
                severity=cand.severity,
                product_id=cand.product_id,
                location_id=cand.location_id,
                title=cand.title,
                evidence=ev,
                state="open",
                first_seen_at=now_utc,
                last_seen_at=now_utc,
            )
            session.add(new_alert)
            session.flush()

            if send_notifications:
                dispatch_alert_notifications(new_alert, settings=cfg)

            active_alerts.append(new_alert)

    # 3. Handle unfulfilled alerts and resolve after 2 evaluations (SPECS §18)
    stmt_open = select(Alert).where(Alert.state.in_(["open", "acknowledged"]))
    open_alerts = list(session.execute(stmt_open).scalars().all())

    for alert in open_alerts:
        if alert.dedupe_key not in seen_dedupe_keys:
            ev = dict(alert.evidence or {})
            miss_count = int(ev.get("miss_count", 0)) + 1
            ev["miss_count"] = miss_count
            alert.evidence = ev

            if miss_count >= 2:
                alert.state = "resolved"
                logger.info(
                    "alert_auto_resolved",
                    dedupe_key=alert.dedupe_key,
                    consecutive_misses=miss_count,
                )

    session.flush()
    return active_alerts
