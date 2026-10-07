"""Integration tests for Data Quality (DQ) cockpit and DATA_STALE alerts (SPECS §14, §15, T5.3)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from ketrika.core.db import check_db_connection
from ketrika.core.models.db import (
    Alert,
    DqResult,
    PriceObservation,
    Product,
    Source,
    SourceRecord,
)
from ketrika.core.settings import get_settings
from ketrika.gold.dq import (
    check_freshness_and_manage_alerts,
    check_parse_success_rate,
    check_price_range_sanity,
    check_provenance_complete,
    run_all_dq_checks,
)
from ketrika.gold.refresh import init_gold_views, refresh_gold_views
from ketrika.pipelines.rebuild import wipe_silver_gold_tables


@pytest.fixture
def db_session():
    """Create a database session connected to PostgreSQL."""
    if not check_db_connection():
        pytest.skip("Database is not reachable (skipping integration tests)")
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session = Session(engine)
    try:
        # Ensure gold views definitions are up to date
        init_gold_views(session)
        session.commit()
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.integration
def test_gold_source_health_stale_and_alert_lifecycle(db_session: Session):
    """Verify that an artificially aged source appears out of SLA (is_stale=true) in gold.source_health,

    triggers a DATA_STALE alert in ops.alert and ops.dq_result, and resolves when updated.
    """
    # 1. Clean slate for obs, ml, and ops tables (without violating bronze immutability)
    wipe_silver_gold_tables(db_session)
    db_session.execute(text("DELETE FROM ops.alert;"))
    db_session.commit()

    # 2. Setup source with freshness_sla_days = 20
    unique_suffix = uuid.uuid4().hex[:6]
    source_id = f"test_stale_{unique_suffix}"
    source = Source(
        source_id=source_id,
        spec={
            "name": f"Stale Test Source {unique_suffix}",
            "priority": "P0",
            "freshness_sla_days": 20,
        },
        status="active",
    )
    db_session.add(source)
    db_session.commit()

    # 3. Insert an artificially aged source record (fetched 50 days ago -> SLA is 20 days)
    old_record_id = uuid.uuid4()
    stale_date = datetime.now(UTC) - timedelta(days=50)
    old_record = SourceRecord(
        source_record_id=old_record_id,
        source_id=source_id,
        source_url=f"https://example.com/bulletin_stale_{unique_suffix}.pdf",
        retrieved_via="direct",
        object_key=f"bronze/{source_id}/stale.pdf",
        content_sha256=f"sha256_stale_{unique_suffix}",
        mime_type="application/pdf",
        fetched_at=stale_date,
        parser_version="1.0.0",
        extraction_status="parsed",
    )
    db_session.add(old_record)
    db_session.commit()

    # 4. Refresh Gold materialized views (including gold.source_health)
    refresh_gold_views(db_session)
    db_session.commit()

    # 5. Query gold.source_health to verify is_stale and freshness_days
    row = db_session.execute(
        text(
            """
            SELECT source_id, freshness_sla_days, freshness_days, is_stale, last_fetched_at
            FROM gold.source_health
            WHERE source_id = :sid;
            """
        ),
        {"sid": source_id},
    ).fetchone()

    assert row is not None
    assert row[0] == source_id
    assert row[1] == 20  # freshness_sla_days
    assert row[2] >= 49  # freshness_days
    assert row[3] is True  # is_stale MUST be True for an aged source!

    # 6. Execute DQ checks battery and persist to ops.dq_result and ops.alert
    results = run_all_dq_checks(db_session, persist=True)
    db_session.commit()

    # Assert that a freshness check failed for this source
    freshness_results = [
        r for r in results if r.check_name == "freshness" and r.source_id == source_id
    ]
    assert len(freshness_results) == 1
    assert freshness_results[0].passed is False
    assert freshness_results[0].metric >= 49.0

    # Verify that ops.dq_result has persisted the failure
    dq_row = db_session.execute(
        select(DqResult).where(DqResult.source_id == source_id, DqResult.check_name == "freshness")
    ).scalar_one_or_none()
    assert dq_row is not None
    assert dq_row.passed is False
    assert dq_row.threshold == 20.0

    # Verify that an alert was generated in ops.alert with rule_code='DATA_STALE' and state='open'
    alert = db_session.execute(
        select(Alert).where(Alert.dedupe_key == f"DATA_STALE_{source_id}")
    ).scalar_one_or_none()
    assert alert is not None
    assert alert.rule_code == "DATA_STALE"
    assert alert.state == "open"
    assert "hors SLA" in alert.title
    assert alert.evidence["freshness_days"] >= 49.0

    # 7. Recovery: Insert a fresh source record (fetched right now)
    new_record_id = uuid.uuid4()
    now_date = datetime.now(UTC)
    new_record = SourceRecord(
        source_record_id=new_record_id,
        source_id=source_id,
        source_url=f"https://example.com/bulletin_fresh_{unique_suffix}.pdf",
        retrieved_via="direct",
        object_key=f"bronze/{source_id}/fresh.pdf",
        content_sha256=f"sha256_fresh_{unique_suffix}",
        mime_type="application/pdf",
        fetched_at=now_date,
        parser_version="1.0.0",
        extraction_status="parsed",
    )
    db_session.add(new_record)
    db_session.commit()

    # Refresh views again
    refresh_gold_views(db_session)
    db_session.commit()

    # Verify gold.source_health shows fresh
    fresh_row = db_session.execute(
        text(
            """
            SELECT freshness_days, is_stale
            FROM gold.source_health
            WHERE source_id = :sid;
            """
        ),
        {"sid": source_id},
    ).fetchone()
    assert fresh_row is not None
    assert fresh_row[0] <= 1  # freshness_days is 0 or 1
    assert fresh_row[1] is False  # is_stale is now False

    # Run freshness check and manage alerts
    check_freshness_and_manage_alerts(db_session, source_id=source_id)
    db_session.commit()

    # Verify that alert state transitioned to 'resolved'
    db_session.refresh(alert)
    assert alert.state == "resolved"


@pytest.mark.integration
def test_gold_dq_asset_checks_battery(db_session: Session):
    """Verify DQ battery checks: provenance_complete, parse_success_rate, and price_range_sanity."""
    wipe_silver_gold_tables(db_session)
    db_session.commit()

    unique_suffix = uuid.uuid4().hex[:6]
    product_id = uuid.uuid4()
    product = Product(
        product_id=product_id,
        product_code=f"rice_dq_{unique_suffix}",
        canonical_name_fr="Riz Test DQ",
        category="cereal",
        base_unit="kg",
        verified=True,
    )
    db_session.add(product)

    source_id = f"test_bat_{unique_suffix}"
    source = Source(
        source_id=source_id,
        spec={"name": "Battery Test Source", "priority": "P1", "freshness_sla_days": 30},
        status="active",
    )
    db_session.add(source)

    srec_id = uuid.uuid4()
    srec = SourceRecord(
        source_record_id=srec_id,
        source_id=source_id,
        source_url=f"https://example.com/test_{unique_suffix}.csv",
        retrieved_via="direct",
        object_key=f"bronze/{source_id}/test.csv",
        content_sha256=f"sha256_dq_battery_{unique_suffix}",
        mime_type="text/csv",
        fetched_at=datetime.now(UTC),
        parser_version="1.0.0",
        extraction_status="parsed",
    )
    db_session.add(srec)

    # Valid price observation
    p_obs = PriceObservation(
        observation_id=uuid.uuid4(),
        source_record_id=srec_id,
        natural_key=f"test_price_{unique_suffix}_1",
        product_id=product_id,
        product_raw="Riz test",
        actor_level="retail",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        price_raw="3200",
        price_value=3200.0,
        currency_raw="MGA",
        unit_raw="kg",
        price_mga_per_base=3200.0,
        base_unit="kg",
        conversion_status="converted",
        observed_or_imputed="observed",
        extraction_method="deterministic",
        confidence=1.0,
        review_status="accepted",
    )
    db_session.add(p_obs)
    db_session.commit()

    # Provenance check should be 100%
    prov_res = check_provenance_complete(db_session, source_id=source_id)
    assert prov_res.passed is True
    assert prov_res.metric == 100.0

    # Parse success rate check should be 100%
    parse_res = check_parse_success_rate(db_session, source_id=source_id)
    assert parse_res.passed is True
    assert parse_res.metric == 100.0

    # Price range sanity check should pass (3200 is within [100, 200000])
    price_res = check_price_range_sanity(db_session, source_id=source_id)
    assert price_res.passed is True
    assert price_res.metric == 0.0

    # Insert an insane price (< 100 or > 200000)
    insane_obs = PriceObservation(
        observation_id=uuid.uuid4(),
        source_record_id=srec_id,
        natural_key=f"test_price_insane_{unique_suffix}",
        product_id=product_id,
        product_raw="Riz test",
        actor_level="retail",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        price_raw="500000",
        price_value=500000.0,
        currency_raw="MGA",
        unit_raw="kg",
        price_mga_per_base=500000.0,
        base_unit="kg",
        conversion_status="converted",
        observed_or_imputed="observed",
        extraction_method="deterministic",
        confidence=1.0,
        review_status="accepted",
    )
    db_session.add(insane_obs)
    db_session.commit()

    price_res_fail = check_price_range_sanity(db_session, source_id=source_id)
    assert price_res_fail.passed is False
    assert price_res_fail.metric == 1.0  # 1 violation
