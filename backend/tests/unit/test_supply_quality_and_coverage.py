"""Unit tests for supply data quality, coverage matrices and temporal non-double-counting (R5.3, ADR-090, SPECS §27)."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import pytest

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.market_supply import MarketSupplyConnector
from ketrika.connectors.records import StockRecord
from ketrika.supply.contracts import (
    QuantityMeasurementMode,
    QuantityTarget,
)
from ketrika.supply.quality import (
    ObservationPresence,
    SupplyQualityChecker,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "market_supply"


class DummyBronzeStore:
    def __init__(self, data: bytes):
        self._data = data

    def get(self, object_key: str) -> bytes | None:
        return self._data


def test_market_period_matrix_surveyed_vs_unmonitored():
    """Verify market x period matrix distinguishes surveyed days from unmonitored days without zero-imputation."""
    checker = SupplyQualityChecker()

    # Create 3 sparse daily observations over a 5-day interval (2024-05-01 to 2024-05-05)
    records = [
        StockRecord(
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            measurement_mode=QuantityMeasurementMode.MEASURED_SCALE.value,
            market_type="terminal_wholesale",
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="rice_vary_gasy",
            period_start=date(2024, 5, 1),
            period_end=date(2024, 5, 1),
            quantity_raw="120",
            quantity_value=120_000.0,
            unit_raw="tonne",
            stock_status="sufficient",
            extraction_method="deterministic",
            confidence=1.0,
        ),
        StockRecord(
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            measurement_mode=QuantityMeasurementMode.DECLARED_TRADER.value,
            market_type="terminal_wholesale",
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="rice_vary_gasy",
            period_start=date(2024, 5, 3),
            period_end=date(2024, 5, 3),
            quantity_raw="95",
            quantity_value=95_000.0,
            unit_raw="tonne",
            stock_status="sufficient",
            extraction_method="deterministic",
            confidence=1.0,
        ),
        StockRecord(
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            measurement_mode=QuantityMeasurementMode.MEASURED_SCALE.value,
            market_type="terminal_wholesale",
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="rice_vary_gasy",
            period_start=date(2024, 5, 5),
            period_end=date(2024, 5, 5),
            quantity_raw="140",
            quantity_value=140_000.0,
            unit_raw="tonne",
            stock_status="sufficient",
            extraction_method="deterministic",
            confidence=1.0,
        ),
    ]

    start_date = date(2024, 5, 1)
    end_date = date(2024, 5, 5)
    matrix = checker.build_market_period_matrix(records, start_date, end_date)

    assert len(matrix) == 5

    # Day 1: Surveyed
    d1 = matrix[("MKT_ANOSIBE", "rice_vary_gasy", date(2024, 5, 1))]
    assert d1.presence == ObservationPresence.OBSERVED_ARRIVAL
    assert d1.quantity_kg == 120_000.0
    assert d1.measurement_mode == QuantityMeasurementMode.MEASURED_SCALE.value
    assert not d1.is_missing

    # Day 2: NOT surveyed -> STRICT: quantity_kg must be None, NOT 0.0 !
    d2 = matrix[("MKT_ANOSIBE", "rice_vary_gasy", date(2024, 5, 2))]
    assert d2.presence == ObservationPresence.MISSING_SURVEY
    assert d2.quantity_kg is None
    assert d2.is_missing
    assert not d2.is_zero

    # Day 3: Surveyed
    d3 = matrix[("MKT_ANOSIBE", "rice_vary_gasy", date(2024, 5, 3))]
    assert d3.presence == ObservationPresence.OBSERVED_ARRIVAL
    assert d3.quantity_kg == 95_000.0

    # Day 4: NOT surveyed -> None
    d4 = matrix[("MKT_ANOSIBE", "rice_vary_gasy", date(2024, 5, 4))]
    assert d4.presence == ObservationPresence.MISSING_SURVEY
    assert d4.quantity_kg is None
    assert d4.is_missing

    # Day 5: Surveyed
    d5 = matrix[("MKT_ANOSIBE", "rice_vary_gasy", date(2024, 5, 5))]
    assert d5.presence == ObservationPresence.OBSERVED_ARRIVAL
    assert d5.quantity_kg == 140_000.0


def test_verified_zero_arrival_vs_missing_survey():
    """Verify distinct representation of verified zero arrival vs unmonitored day."""
    checker = SupplyQualityChecker()

    records = [
        # Explicit zero arrival recorded on cyclone closure day
        StockRecord(
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            measurement_mode=QuantityMeasurementMode.MEASURED_SCALE.value,
            market_type="terminal_wholesale",
            market_code="MKT_TOAMASINA",
            location_raw="Bazar Be Toamasina",
            product_raw="rice_vary_gasy",
            period_start=date(2024, 2, 10),
            period_end=date(2024, 2, 10),
            quantity_raw="0",
            quantity_value=0.0,
            unit_raw="tonne",
            stock_status="depleted",
            extraction_method="deterministic",
            confidence=1.0,
        ),
    ]

    start_date = date(2024, 2, 10)
    end_date = date(2024, 2, 11)
    matrix = checker.build_market_period_matrix(records, start_date, end_date)

    zero_day = matrix[("MKT_TOAMASINA", "rice_vary_gasy", date(2024, 2, 10))]
    assert zero_day.presence == ObservationPresence.ZERO_ARRIVAL_VERIFIED
    assert zero_day.is_zero
    assert not zero_day.is_missing
    assert zero_day.quantity_kg == 0.0

    unmonitored_day = matrix[("MKT_TOAMASINA", "rice_vary_gasy", date(2024, 2, 11))]
    assert unmonitored_day.presence == ObservationPresence.MISSING_SURVEY
    assert not unmonitored_day.is_zero
    assert unmonitored_day.is_missing
    assert unmonitored_day.quantity_kg is None  # Fundamental: absence != zero


def test_sampling_coverage_rate_and_metrological_ratio():
    """Verify calculation of sampling coverage rate and certified scale vs declared trader ratios."""
    checker = SupplyQualityChecker()

    # 10 calendar days: 2024-06-01 to 2024-06-10
    # 6 surveyed days: 4 scale-measured, 2 trader-declared
    records = []
    for day_idx in range(1, 7):
        mode = (
            QuantityMeasurementMode.MEASURED_SCALE.value
            if day_idx <= 4
            else QuantityMeasurementMode.DECLARED_TRADER.value
        )
        records.append(
            StockRecord(
                target=QuantityTarget.INFLOW_ARRIVAL.value,
                measurement_mode=mode,
                market_type="terminal_wholesale",
                market_code="MKT_ANOSIBE",
                location_raw="Marché d'Anosibe",
                product_raw="maize",
                period_start=date(2024, 6, day_idx),
                period_end=date(2024, 6, day_idx),
                quantity_raw="20",
                quantity_value=20_000.0,
                unit_raw="tonne",
                stock_status="sufficient",
                extraction_method="deterministic",
                confidence=1.0,
            )
        )

    start_date = date(2024, 6, 1)
    end_date = date(2024, 6, 10)

    stats = checker.calculate_market_coverage(records, start_date, end_date)
    assert len(stats) == 1
    s = stats[0]

    assert s.total_calendar_days == 10
    assert s.surveyed_days == 6
    assert s.unmonitored_days == 4
    assert s.sampling_coverage_rate == 0.6  # 6 / 10
    assert s.total_observed_quantity_kg == 120_000.0  # 6 * 20,000 kg
    assert s.measured_scale_count == 4
    assert s.declared_trader_count == 2
    assert s.estimated_survey_count == 0
    assert pytest.approx(s.certified_measurement_ratio, rel=1e-3) == 0.6667  # 4 / 6


def test_temporal_double_count_detection_on_subsumed_intervals():
    """Verify detection of temporal overlap double counting (monthly aggregate + daily records)."""
    checker = SupplyQualityChecker()

    records = [
        # Monthly aggregate row: May 1 to May 31, 2024
        StockRecord(
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            measurement_mode=QuantityMeasurementMode.DECLARED_TRADER.value,
            market_type="terminal_wholesale",
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="rice_vary_gasy",
            period_start=date(2024, 5, 1),
            period_end=date(2024, 5, 31),
            quantity_raw="5000",
            quantity_value=5_000_000.0,
            unit_raw="tonne",
            stock_status="sufficient",
            extraction_method="deterministic",
            confidence=1.0,
        ),
        # Daily row 1 inside May
        StockRecord(
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            measurement_mode=QuantityMeasurementMode.MEASURED_SCALE.value,
            market_type="terminal_wholesale",
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="rice_vary_gasy",
            period_start=date(2024, 5, 2),
            period_end=date(2024, 5, 2),
            quantity_raw="180",
            quantity_value=180_000.0,
            unit_raw="tonne",
            stock_status="sufficient",
            extraction_method="deterministic",
            confidence=1.0,
        ),
        # Daily row 2 inside May
        StockRecord(
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            measurement_mode=QuantityMeasurementMode.MEASURED_SCALE.value,
            market_type="terminal_wholesale",
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="rice_vary_gasy",
            period_start=date(2024, 5, 3),
            period_end=date(2024, 5, 3),
            quantity_raw="210",
            quantity_value=210_000.0,
            unit_raw="tonne",
            stock_status="sufficient",
            extraction_method="deterministic",
            confidence=1.0,
        ),
    ]

    violations = checker.detect_temporal_overlap_double_counting(records)
    assert len(violations) == 1
    v = violations[0]
    assert v.market_code == "MKT_ANOSIBE"
    assert v.product_raw == "rice_vary_gasy"
    assert v.violation_type == "subsumed_interval_double_count"
    assert v.parent_period == (date(2024, 5, 1), date(2024, 5, 31))
    assert len(v.child_periods) == 2
    assert v.child_sum_quantity_kg == 390_000.0


def test_physical_unit_conversion_auditing():
    """Verify auditing of standardized physical unit conversions and rejection of arbitrary factors."""
    checker = SupplyQualityChecker()

    valid_records = [
        # 180 tonnes rice = 180,000 kg
        StockRecord(
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="rice_vary_gasy",
            period_start=date(2024, 5, 1),
            period_end=date(2024, 5, 1),
            quantity_raw="180",
            quantity_value=180_000.0,
            unit_raw="tonne",
            extraction_method="deterministic",
            confidence=1.0,
        ),
        # 600 bags 50kg maize = 30,000 kg
        StockRecord(
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="maize",
            period_start=date(2024, 5, 2),
            period_end=date(2024, 5, 2),
            quantity_raw="600",
            quantity_value=30_000.0,
            unit_raw="bag_50kg",
            extraction_method="deterministic",
            confidence=1.0,
        ),
    ]

    audits = checker.audit_unit_conversions(valid_records)
    assert len(audits) == 2
    assert all(a.is_valid for a in audits)

    # Corrupted conversion record: 10 tonnes erroneously recorded as 5,000 kg instead of 10,000 kg
    corrupted_record = StockRecord(
        target=QuantityTarget.INFLOW_ARRIVAL.value,
        market_code="MKT_ANOSIBE",
        location_raw="Marché d'Anosibe",
        product_raw="sugar",
        period_start=date(2024, 5, 3),
        period_end=date(2024, 5, 3),
        quantity_raw="10",
        quantity_value=5_000.0,  # Arbitrary half value!
        unit_raw="tonne",
        extraction_method="deterministic",
        confidence=1.0,
    )

    bad_audits = checker.audit_unit_conversions([corrupted_record])
    assert len(bad_audits) == 1
    assert not bad_audits[0].is_valid
    assert "Discrepancy" in str(bad_audits[0].discrepancy_reason)


def test_full_quality_audit_on_authentic_odr_fixtures():
    """Verify complete DQ audit on authentic ODR market supply dataset."""
    fixture_path = FIXTURES_DIR / "odr_approvisionnement_anosibe_2024.csv"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = MarketSupplyConnector()
    ctx = RunContext(
        source_id="market_supply",
        run_id="run-audit-odr",
        bronze_store=DummyBronzeStore(payload),
        metadata={},
    )
    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="file:///workspace/data/supply/odr_suivi_approvisionnement_anosibe_2024.csv",
        object_key="raw/market_supply/anosibe_2024.csv",
        mime_type="text/csv",
        content_sha256="mockshaaudit",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.issues) == 0
    assert len(result.records) == 7

    checker = SupplyQualityChecker()
    start_date = date(2024, 5, 1)
    end_date = date(2024, 5, 7)

    report = checker.run_full_quality_audit(
        result.records,
        start_date=start_date,
        end_date=end_date,
        target=QuantityTarget.INFLOW_ARRIVAL.value,
    )

    # Check overall validity
    assert report.is_valid
    assert report.missing_vs_zero_strictly_respected
    assert len(report.double_counting_violations) == 0
    assert len(report.conversion_audit_issues) == 0
    assert "MKT_ANOSIBE" in report.markets_analyzed
    assert len(report.coverage_by_market) >= 2  # Rice and Maize covered
