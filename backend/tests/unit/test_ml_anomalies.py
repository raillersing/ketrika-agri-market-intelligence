"""Unit tests for ML price anomaly detection engine (SPECS §17, §18, T9.2)."""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from ketrika.ml.anomalies import (
    PriceAnomaly,
    detect_price_anomalies,
    record_anomaly_model_run,
)


def test_detect_price_anomalies_classification() -> None:
    """Verify classification into PRICE_SPIKE, PRICE_DROP, and OUTLIER."""
    mock_session = MagicMock()

    # 1. Price spike with multi-source confirmation (high severity)
    spike_high = SimpleNamespace(
        product_id=uuid.uuid4(),
        product_code="rice_milled_local",
        product_name="Riz blanc local",
        location_id=uuid.uuid4(),
        location_pcode="MG-T",
        location_name="Analamanga",
        month=date(2026, 9, 1),
        median_price=2950.0,
        chg_1m=0.28,
        z_score_robust=3.75,
        chosen_source_id="miasa_odr",
        n_sources=2,
        sources=["miasa_odr", "wfp_hdx_mdg"],
    )

    # 2. Price spike with single source (medium severity)
    spike_med = SimpleNamespace(
        product_id=uuid.uuid4(),
        product_code="maize_grain",
        product_name="Maïs en grain",
        location_id=uuid.uuid4(),
        location_pcode="MG-U",
        location_name="Atsimo-Andrefana",
        month=date(2026, 9, 1),
        median_price=1800.0,
        chg_1m=0.20,
        z_score_robust=3.20,
        chosen_source_id="mincc_ppn",
        n_sources=1,
        sources=["mincc_ppn"],
    )

    # 3. Price drop (medium severity)
    drop_med = SimpleNamespace(
        product_id=uuid.uuid4(),
        product_code="cassava_fresh",
        product_name="Manioc frais",
        location_id=uuid.uuid4(),
        location_pcode="MG-D",
        location_name="Diana",
        month=date(2026, 9, 1),
        median_price=900.0,
        chg_1m=-0.25,
        z_score_robust=-3.40,
        chosen_source_id="mincc_ppn",
        n_sources=1,
        sources=["mincc_ppn"],
    )

    # 4. Outlier: |z| > 3 but chg_1m <= 0.15 (low severity)
    outlier_low = SimpleNamespace(
        product_id=uuid.uuid4(),
        product_code="sugar_refined",
        product_name="Sucre raffiné",
        location_id=uuid.uuid4(),
        location_pcode="MG-T",
        location_name="Analamanga",
        month=date(2026, 9, 1),
        median_price=4100.0,
        chg_1m=0.08,
        z_score_robust=3.10,
        chosen_source_id="mincc_ppn",
        n_sources=1,
        sources=["mincc_ppn"],
    )

    mock_session.execute.return_value.fetchall.return_value = [
        spike_high,
        spike_med,
        drop_med,
        outlier_low,
    ]

    anomalies = detect_price_anomalies(mock_session, z_threshold=3.0, chg_threshold=0.15)
    assert len(anomalies) == 4

    # Check spike high
    a0 = anomalies[0]
    assert a0.anomaly_type == "PRICE_SPIKE"
    assert a0.severity == "high"
    assert a0.evidence["rule"] == "PRICE_SPIKE"
    assert a0.evidence["n_sources"] == 2
    assert a0.z_score_robust == 3.75

    # Check spike med
    a1 = anomalies[1]
    assert a1.anomaly_type == "PRICE_SPIKE"
    assert a1.severity == "medium"
    assert a1.evidence["n_sources"] == 1

    # Check drop
    a2 = anomalies[2]
    assert a2.anomaly_type == "PRICE_DROP"
    assert a2.severity == "medium"
    assert a2.evidence["rule"] == "PRICE_DROP"
    assert a2.z_score_robust == -3.40

    # Check outlier
    a3 = anomalies[3]
    assert a3.anomaly_type == "OUTLIER"
    assert a3.severity == "low"


def test_record_anomaly_model_run() -> None:
    """Verify persisting anomaly run metrics into ml.model_run."""
    mock_session = MagicMock()

    anomalies = [
        PriceAnomaly(
            anomaly_type="PRICE_SPIKE",
            product_id=uuid.uuid4(),
            product_code="rice_milled_local",
            product_name="Riz blanc local",
            location_id=uuid.uuid4(),
            location_pcode="MG-T",
            location_name="Analamanga",
            month=date(2026, 9, 1),
            median_price=2900.0,
            chg_1m=0.25,
            z_score_robust=3.5,
            severity="high",
            chosen_source_id="miasa_odr",
            sources=["miasa_odr", "wfp_hdx_mdg"],
            n_sources=2,
            evidence={},
        ),
        PriceAnomaly(
            anomaly_type="PRICE_DROP",
            product_id=uuid.uuid4(),
            product_code="maize_grain",
            product_name="Maïs",
            location_id=uuid.uuid4(),
            location_pcode="MG-U",
            location_name="Atsimo-Andrefana",
            month=date(2026, 9, 1),
            median_price=1200.0,
            chg_1m=-0.22,
            z_score_robust=-3.2,
            severity="medium",
            chosen_source_id="mincc_ppn",
            sources=["mincc_ppn"],
            n_sources=1,
            evidence={},
        ),
    ]

    model_run = record_anomaly_model_run(
        mock_session,
        anomalies,
        z_threshold=3.0,
        chg_threshold=0.15,
        data_cutoff=date(2026, 9, 30),
    )

    assert model_run.task == "anomaly"
    assert model_run.model_name == "robust_zscore"
    assert model_run.data_cutoff == date(2026, 9, 30)
    assert model_run.metrics is not None
    assert model_run.params is not None
    assert model_run.metrics["total_anomalies"] == 2
    assert model_run.metrics["spikes_count"] == 1
    assert model_run.metrics["drops_count"] == 1
    assert model_run.metrics["outliers_count"] == 0
    assert model_run.params["z_threshold"] == 3.0
    mock_session.add.assert_called_once_with(model_run)
    mock_session.flush.assert_called_once()
