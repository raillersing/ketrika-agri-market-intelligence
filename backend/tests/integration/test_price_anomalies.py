"""Integration tests for Price Anomaly detection and Alerts integration (SPECS §17, §18, T9.2).

Acceptance criteria:
- Anomaly detection identifies |z| > 3 with directional monthly variation;
- Anomalies feed PRICE_SPIKE (z > 3 and chg_1m > 0.15) with multi-source severity;
- Anomalies feed PRICE_DROP (z < -3 and chg_1m < -0.15);
- Verified on a synthetic dataset with an injected price spike and price drop.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from ketrika.alerts.engine import evaluate_alerts
from ketrika.core.db import check_db_connection
from ketrika.core.models.db import (
    Alert,
    PriceObservation,
    SourceRecord,
)
from ketrika.core.settings import get_settings
from ketrika.gold.refresh import refresh_gold_views
from ketrika.ml.anomalies import detect_price_anomalies, record_anomaly_model_run
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.e2e_data.source_backed_synthetic import attach_new_synthetic_proof
from tests.e2e_data.synthetic_gold_dataset import (
    LOCATION_ANALAMANGA_ID,
    PRODUCT_MAIZE_ID,
    PRODUCT_RICE_ID,
    SOURCE_RECORD_ID_BASE,
    seed_synthetic_gold_data,
)


@pytest.fixture
def db_session():
    """Create a database session connected to PostgreSQL."""
    if not check_db_connection():
        pytest.skip("Database is not reachable (skipping integration tests)")
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session = Session(engine)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.integration
def test_price_anomaly_spike_and_drop_pipeline(db_session: Session) -> None:
    """Verify price spike and price drop injection on synthetic series feeds ML runs and alerts."""
    # 1. Clean slate and base synthetic dataset
    wipe_silver_gold_tables(db_session)
    db_session.execute(text("DELETE FROM ops.alert;"))
    db_session.execute(text("DELETE FROM ml.model_run WHERE task = 'anomaly';"))
    db_session.commit()

    seed_synthetic_gold_data(db_session)
    db_session.commit()

    src_rec = db_session.get(
        SourceRecord, uuid.uuid5(SOURCE_RECORD_ID_BASE, "synthetic-generator-v2:miasa_odr_0")
    )
    assert src_rec is not None
    assert src_rec.source_id == "miasa_odr"

    # Retrieve another source record for multi-source confirmation
    src_rec_second = db_session.get(
        SourceRecord, uuid.uuid5(SOURCE_RECORD_ID_BASE, "synthetic-generator-v2:wfp_hdx_mdg_0")
    )
    assert src_rec_second is not None
    assert src_rec_second.source_id == "wfp_hdx_mdg"

    # 2. Inject PRICE SPIKE for Rice (Month 2024-03)
    # Baseline was ~2800-3000 MGA. We inject 5500 MGA from 2 sources (+80% chg_1m, z > 5)
    spike_obs_1 = PriceObservation(
        observation_id=uuid.uuid5(SOURCE_RECORD_ID_BASE, "spike_rice_2024_03_src1"),
        source_record_id=src_rec.source_record_id,
        natural_key="nk_spike_rice_2024_03_src1",
        product_raw="Riz blanc",
        product_id=PRODUCT_RICE_ID,
        location_raw="Analamanga",
        location_id=LOCATION_ANALAMANGA_ID,
        actor_level="retail",
        period_start=date(2024, 3, 1),
        period_end=date(2024, 3, 31),
        price_raw="5500.0",
        price_value=Decimal("5500.0"),
        currency_raw="MGA",
        unit_raw="kg",
        price_mga_per_base=5500.0,
        base_unit="kg",
        conversion_status="exact",
        observed_or_imputed="observed",
        extraction_method="deterministic",
        confidence=1.0,
        review_status="accepted",
        superseded_by=None,
    )
    spike_obs_2 = PriceObservation(
        observation_id=uuid.uuid5(SOURCE_RECORD_ID_BASE, "spike_rice_2024_03_src2"),
        source_record_id=src_rec_second.source_record_id,
        natural_key="nk_spike_rice_2024_03_src2",
        product_raw="Riz blanc",
        product_id=PRODUCT_RICE_ID,
        location_raw="Analamanga",
        location_id=LOCATION_ANALAMANGA_ID,
        actor_level="retail",
        period_start=date(2024, 3, 1),
        period_end=date(2024, 3, 31),
        price_raw="5600.0",
        price_value=Decimal("5600.0"),
        currency_raw="MGA",
        unit_raw="kg",
        price_mga_per_base=5600.0,
        base_unit="kg",
        conversion_status="exact",
        observed_or_imputed="observed",
        extraction_method="deterministic",
        confidence=1.0,
        review_status="accepted",
        superseded_by=None,
    )
    attach_new_synthetic_proof(db_session, spike_obs_1)
    attach_new_synthetic_proof(db_session, spike_obs_2)
    db_session.add_all([spike_obs_1, spike_obs_2])

    # 3. Inject PRICE DROP for Maize:
    # First, insert 12 months of baseline maize prices with slight realistic variance (~1770-1830 MGA, MAD ~15)
    maize_base_prices = [
        1780.0,
        1820.0,
        1790.0,
        1810.0,
        1770.0,
        1830.0,
        1800.0,
        1810.0,
        1790.0,
        1820.0,
        1780.0,
        1800.0,
    ]
    for m_idx, base_p in enumerate(maize_base_prices, start=1):
        p_m = PriceObservation(
            observation_id=uuid.uuid5(SOURCE_RECORD_ID_BASE, f"hist_maize_base_{m_idx}"),
            source_record_id=src_rec.source_record_id,
            natural_key=f"nk_hist_maize_base_{m_idx}",
            product_raw="Maïs",
            product_id=PRODUCT_MAIZE_ID,
            location_raw="Analamanga",
            location_id=LOCATION_ANALAMANGA_ID,
            actor_level="retail",
            period_start=date(2023, m_idx, 1),
            period_end=date(2023, m_idx, 28),
            price_raw=str(base_p),
            price_value=Decimal(str(base_p)),
            currency_raw="MGA",
            unit_raw="kg",
            price_mga_per_base=base_p,
            base_unit="kg",
            conversion_status="exact",
            observed_or_imputed="observed",
            extraction_method="deterministic",
            confidence=1.0,
            review_status="accepted",
            superseded_by=None,
        )
        attach_new_synthetic_proof(db_session, p_m)
        db_session.add(p_m)

    # Injected sharp drop in 2024-01 for Maize (800 MGA vs 1800 baseline, -55% chg_1m, z < -3)
    drop_obs = PriceObservation(
        observation_id=uuid.uuid5(SOURCE_RECORD_ID_BASE, "drop_maize_2024_01"),
        source_record_id=src_rec.source_record_id,
        natural_key="nk_drop_maize_2024_01",
        product_raw="Maïs",
        product_id=PRODUCT_MAIZE_ID,
        location_raw="Analamanga",
        location_id=LOCATION_ANALAMANGA_ID,
        actor_level="retail",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        price_raw="800.0",
        price_value=Decimal("800.0"),
        currency_raw="MGA",
        unit_raw="kg",
        price_mga_per_base=800.0,
        base_unit="kg",
        conversion_status="exact",
        observed_or_imputed="observed",
        extraction_method="deterministic",
        confidence=1.0,
        review_status="accepted",
        superseded_by=None,
    )
    attach_new_synthetic_proof(db_session, drop_obs)
    db_session.add(drop_obs)
    db_session.commit()

    # 4. Refresh Gold materialized views
    ref_res = refresh_gold_views(db_session)
    db_session.commit()
    assert ref_res["count"] == 13
    assert ref_res["withheld_views"] == {"economic_dashboard": "macro_publication_not_qualified"}

    # 5. Detect statistical price anomalies
    anomalies = detect_price_anomalies(db_session, z_threshold=3.0, chg_threshold=0.15)
    assert len(anomalies) >= 2

    types = {a.anomaly_type for a in anomalies}
    assert "PRICE_SPIKE" in types
    assert "PRICE_DROP" in types

    # Check Rice Spike anomaly
    rice_spikes = [
        a for a in anomalies if a.anomaly_type == "PRICE_SPIKE" and a.product_id == PRODUCT_RICE_ID
    ]
    assert len(rice_spikes) >= 1
    rspike = rice_spikes[0]
    assert rspike.z_score_robust > 3.0
    assert rspike.chg_1m is not None and rspike.chg_1m > 0.15
    assert rspike.severity == "high"  # Multi-source confirmation
    assert rspike.n_sources >= 2
    assert rspike.n_independent_families >= 2

    # Check Maize Drop anomaly
    maize_drops = [
        a for a in anomalies if a.anomaly_type == "PRICE_DROP" and a.product_id == PRODUCT_MAIZE_ID
    ]
    assert len(maize_drops) >= 1
    mdrop = maize_drops[0]
    assert mdrop.z_score_robust < -3.0
    assert mdrop.chg_1m is not None and mdrop.chg_1m < -0.15
    assert mdrop.severity == "medium"

    # 6. Record anomaly ModelRun
    model_run = record_anomaly_model_run(
        db_session,
        anomalies,
        z_threshold=3.0,
        chg_threshold=0.15,
        data_cutoff=date(2024, 3, 31),
    )
    db_session.commit()

    assert model_run.model_run_id is not None
    assert model_run.task == "anomaly"
    assert model_run.metrics is not None
    assert model_run.metrics["spikes_count"] >= 1
    assert model_run.metrics["drops_count"] >= 1

    # 7. Evaluate alerts engine end-to-end
    alerts = evaluate_alerts(db_session, send_notifications=False)
    db_session.commit()

    alert_codes = {al.rule_code for al in alerts}
    assert "PRICE_SPIKE" in alert_codes
    assert "PRICE_DROP" in alert_codes

    # Verify persisted alert properties
    spike_alert = db_session.execute(
        select(Alert).where(Alert.rule_code == "PRICE_SPIKE", Alert.product_id == PRODUCT_RICE_ID)
    ).scalar_one()
    assert spike_alert.state == "open"
    assert spike_alert.severity == "high"
    assert spike_alert.evidence is not None
    assert spike_alert.evidence["z_score"] > 3.0
    assert spike_alert.evidence["chg_1m"] > 0.15
    assert "PRICE_SPIKE|rice_milled|" in spike_alert.dedupe_key

    drop_alert = db_session.execute(
        select(Alert).where(Alert.rule_code == "PRICE_DROP", Alert.product_id == PRODUCT_MAIZE_ID)
    ).scalar_one()
    assert drop_alert.state == "open"
    assert drop_alert.severity == "medium"
    assert drop_alert.evidence is not None
    assert drop_alert.evidence["z_score"] < -3.0
    assert drop_alert.evidence["chg_1m"] < -0.15
    assert "PRICE_DROP|maize|" in drop_alert.dedupe_key
