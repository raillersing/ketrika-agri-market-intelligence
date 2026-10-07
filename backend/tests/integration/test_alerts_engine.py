"""Integration tests for Market Intelligence alerts engine (SPECS §18, T8.1)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from ketrika.alerts.engine import evaluate_alerts
from ketrika.alerts.rules import AlertCandidate
from ketrika.core.db import check_db_connection
from ketrika.core.models.db import Alert, Location, Product
from ketrika.core.settings import get_settings
from ketrika.gold.refresh import init_gold_views


@pytest.fixture
def db_session():
    """Create an active database session."""
    if not check_db_connection():
        pytest.skip("Database is not reachable (skipping integration tests)")
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session = Session(engine)
    try:
        init_gold_views(session)
        session.commit()
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def clear_mailpit_messages() -> None:
    """Clear messages in local Mailpit instance."""
    try:
        httpx.delete("http://mailpit:8025/api/v1/messages", timeout=5)
    except Exception:
        pass


def get_mailpit_messages() -> list[dict[str, Any]]:
    """Retrieve all messages from Mailpit."""
    try:
        resp = httpx.get("http://mailpit:8025/api/v1/messages", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                msgs = data.get("messages", [])
                if isinstance(msgs, list):
                    return msgs
    except Exception:
        pass
    return []


@pytest.mark.integration
def test_alerts_engine_lifecycle_and_notifications(db_session: Session) -> None:
    """Verify alert triggering, deduplication, auto-resolution after 2 cycles, and Mailpit notification."""
    settings = get_settings()

    # Clean test alerts
    db_session.execute(text("DELETE FROM ops.alert WHERE rule_code LIKE 'TEST_%';"))
    db_session.commit()
    clear_mailpit_messages()

    test_product = db_session.execute(select(Product)).scalars().first()
    test_location = db_session.execute(select(Location)).scalars().first()
    prod_id = test_product.product_id if test_product else None
    loc_id = test_location.location_id if test_location else None

    # 1. Trigger an alert candidate
    candidate_1 = AlertCandidate(
        rule_code="TEST_PRICE_SPIKE",
        dedupe_key="TEST_PRICE_SPIKE|rice_milled_local|MG-T|2026-09",
        severity="high",
        title="Flambée test : Riz blanc local à Analamanga (+30%)",
        evidence={"chg_1m": 0.30, "z_score": 3.8, "n_sources": 2},
        product_id=prod_id,
        location_id=loc_id,
    )

    with patch("ketrika.alerts.engine.evaluate_all_rules", return_value=[candidate_1]):
        active_1 = evaluate_alerts(db_session, send_notifications=True, settings=settings)
        db_session.commit()

    assert len(active_1) == 1
    alert_row = db_session.execute(
        select(Alert).where(Alert.dedupe_key == candidate_1.dedupe_key)
    ).scalar_one()
    assert alert_row.state == "open"
    assert alert_row.severity == "high"
    assert alert_row.evidence["miss_count"] == 0
    assert alert_row.last_seen_at is not None

    # Check email reached Mailpit
    msgs = get_mailpit_messages()
    assert len(msgs) >= 1
    latest_msg = msgs[0]
    assert "Flambée test" in latest_msg["Subject"]

    # 2. Test Deduplication on recurring evaluation
    with patch("ketrika.alerts.engine.evaluate_all_rules", return_value=[candidate_1]):
        evaluate_alerts(db_session, send_notifications=True, settings=settings)
        db_session.commit()

    # Count of rows in DB should NOT increase
    count = db_session.execute(
        text("SELECT count(*) FROM ops.alert WHERE dedupe_key = :k"),
        {"k": candidate_1.dedupe_key},
    ).scalar()
    assert count == 1

    # 3. Test Auto-Resolution: condition disappears (miss 1)
    with patch("ketrika.alerts.engine.evaluate_all_rules", return_value=[]):
        evaluate_alerts(db_session, send_notifications=True, settings=settings)
        db_session.commit()

    alert_row = db_session.execute(
        select(Alert).where(Alert.dedupe_key == candidate_1.dedupe_key)
    ).scalar_one()
    # After 1 miss, still open, miss_count = 1
    assert alert_row.state == "open"
    assert alert_row.evidence["miss_count"] == 1

    # 4. Condition still absent (miss 2) -> must transition to 'resolved'
    with patch("ketrika.alerts.engine.evaluate_all_rules", return_value=[]):
        evaluate_alerts(db_session, send_notifications=True, settings=settings)
        db_session.commit()

    alert_row = db_session.execute(
        select(Alert).where(Alert.dedupe_key == candidate_1.dedupe_key)
    ).scalar_one()
    assert alert_row.state == "resolved"
    assert alert_row.evidence["miss_count"] == 2


@pytest.mark.integration
def test_multi_source_severity_rule(db_session: Session) -> None:
    """Verify that PRICE_SPIKE gets severity 'high' when >= 2 sources confirm, and 'medium' with 1 source."""
    from ketrika.alerts.rules import evaluate_price_spike_rules

    # Execute against current database state
    candidates = evaluate_price_spike_rules(db_session)
    for cand in candidates:
        n_sources = cand.evidence.get("n_sources", 1)
        if n_sources >= 2:
            assert cand.severity == "high"
        else:
            assert cand.severity == "medium"
