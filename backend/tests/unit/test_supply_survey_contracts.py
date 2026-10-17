"""Unit tests for supply, arrival flows, stocks, anti-PII contracts and double-counting prevention (R5.1, ADR-088, SPECS §27)."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ketrika.supply.contracts import (
    MarketType,
    QuantityMeasurementMode,
    QuantityObservationRecord,
    QuantityTarget,
    QuantityUnit,
    SurveyMetadata,
    convert_quantity_to_kg,
    validate_no_double_counting,
    validate_payload_no_pii,
)


def test_quantity_observation_record_valid_targets():
    """Verify clean instantiation of all valid quantity targets without extra fields."""
    # 1. Harvest volume in production basin
    harvest_rec = QuantityObservationRecord(
        target=QuantityTarget.HARVEST_VOLUME,
        product_code="rice_paddy",
        product_name="Riz paddy",
        market_code="BASIN_ALAOTRA",
        market_name="Plaine d'Ambatondrazaka",
        location_pcode="MDG32",
        observed_date=date(2024, 5, 15),
        period_start=date(2024, 4, 1),
        period_end=date(2024, 5, 31),
        quantity_raw=450.0,
        unit_raw=QuantityUnit.TONNE,
        quantity_kg=450_000.0,
        measurement_mode=QuantityMeasurementMode.ESTIMATED_SURVEY,
        market_type=MarketType.PRIMARY_COLLECTION,
    )
    assert harvest_rec.target == QuantityTarget.HARVEST_VOLUME
    assert harvest_rec.quantity_kg == 450_000.0

    # 2. Inflow arrival on wholesale market
    arrival_rec = QuantityObservationRecord(
        target=QuantityTarget.INFLOW_ARRIVAL,
        product_code="rice_vary_gasy",
        product_name="Riz blanc Vary Gasy",
        market_code="MKT_ANOSIBE",
        market_name="Marché de gros Anosibe",
        location_pcode="MDG11",
        observed_date=date(2024, 5, 10),
        period_start=date(2024, 5, 10),
        period_end=date(2024, 5, 10),
        quantity_raw=120.0,
        unit_raw=QuantityUnit.BAG_50KG,
        quantity_kg=6000.0,
        measurement_mode=QuantityMeasurementMode.MEASURED_SCALE,
        market_type=MarketType.TERMINAL_URBAN,
    )
    assert arrival_rec.target == QuantityTarget.INFLOW_ARRIVAL
    assert arrival_rec.quantity_kg == 6000.0

    # 3. Stock inventory at point in time
    stock_rec = QuantityObservationRecord(
        target=QuantityTarget.STOCK_INVENTORY,
        product_code="maize",
        product_name="Maïs grain sec",
        market_code="MKT_MAROVOAY",
        market_name="Marché de collecte Marovoay",
        location_pcode="MDG41",
        observed_date=date(2024, 5, 1),
        period_start=date(2024, 5, 1),
        period_end=date(2024, 5, 1),
        quantity_raw=25.0,
        unit_raw=QuantityUnit.TONNE,
        quantity_kg=25_000.0,
        measurement_mode=QuantityMeasurementMode.DECLARED_TRADER,
        market_type=MarketType.REGIONAL_WHOLESALE,
    )
    assert stock_rec.target == QuantityTarget.STOCK_INVENTORY
    assert stock_rec.quantity_kg == 25_000.0


def test_rejection_of_forbidden_pii_fields_extra_forbid():
    """Verify strict rejection of any PII field (trader_name, phone, driver_id, vehicle_plate)."""
    with pytest.raises(ValidationError) as exc_info:
        QuantityObservationRecord(
            target=QuantityTarget.INFLOW_ARRIVAL,
            product_code="rice_vary_gasy",
            product_name="Riz blanc Vary Gasy",
            market_code="MKT_ANOSIBE",
            market_name="Marché Anosibe",
            location_pcode="MDG11",
            observed_date=date(2024, 5, 10),
            quantity_raw=100.0,
            unit_raw=QuantityUnit.KG,
            quantity_kg=100.0,
            measurement_mode=QuantityMeasurementMode.MEASURED_SCALE,
            market_type=MarketType.TERMINAL_URBAN,
            trader_name="Rakoto Jean",  # FORBIDDEN: PII
        )
    assert "extra_forbidden" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info2:
        QuantityObservationRecord(
            target=QuantityTarget.INFLOW_ARRIVAL,
            product_code="rice_vary_gasy",
            product_name="Riz blanc Vary Gasy",
            market_code="MKT_ANOSIBE",
            market_name="Marché Anosibe",
            location_pcode="MDG11",
            observed_date=date(2024, 5, 10),
            quantity_raw=100.0,
            unit_raw=QuantityUnit.KG,
            quantity_kg=100.0,
            measurement_mode=QuantityMeasurementMode.MEASURED_SCALE,
            market_type=MarketType.TERMINAL_URBAN,
            phone="0341234567",  # FORBIDDEN: Phone
        )
    assert "extra_forbidden" in str(exc_info2.value)


def test_rejection_of_pii_patterns_in_notes():
    """Verify rejection of embedded personal phone numbers or emails in notes."""
    # Phone number in notes
    with pytest.raises(ValidationError) as exc_phone:
        QuantityObservationRecord(
            target=QuantityTarget.INFLOW_ARRIVAL,
            product_code="rice_vary_gasy",
            product_name="Riz blanc Vary Gasy",
            market_code="MKT_ANOSIBE",
            market_name="Marché Anosibe",
            location_pcode="MDG11",
            observed_date=date(2024, 5, 10),
            quantity_raw=100.0,
            unit_raw=QuantityUnit.KG,
            quantity_kg=100.0,
            measurement_mode=QuantityMeasurementMode.MEASURED_SCALE,
            market_type=MarketType.TERMINAL_URBAN,
            notes="Contact du grossiste: 034 11 222 33 pour suivi",
        )
    assert "Forbidden phone number pattern" in str(exc_phone.value)

    # Email in notes
    with pytest.raises(ValidationError) as exc_mail:
        QuantityObservationRecord(
            target=QuantityTarget.INFLOW_ARRIVAL,
            product_code="rice_vary_gasy",
            product_name="Riz blanc Vary Gasy",
            market_code="MKT_ANOSIBE",
            market_name="Marché Anosibe",
            location_pcode="MDG11",
            observed_date=date(2024, 5, 10),
            quantity_raw=100.0,
            unit_raw=QuantityUnit.KG,
            quantity_kg=100.0,
            measurement_mode=QuantityMeasurementMode.MEASURED_SCALE,
            market_type=MarketType.TERMINAL_URBAN,
            notes="Envoyer le bon à commercant@gmail.com",
        )
    assert "Forbidden email address" in str(exc_mail.value)


def test_rejection_of_human_names_in_surveyor_identifier():
    """Verify surveyor_identifier must be an anonymous role code and reject human names."""
    # Valid anonymous code
    meta = SurveyMetadata(
        surveyor_identifier="ENQ_ANOSIBE_02",
        sampling_frame="systematic_sample",
    )
    assert meta.surveyor_identifier == "ENQ_ANOSIBE_02"

    # Invalid human name
    with pytest.raises(ValidationError) as exc:
        SurveyMetadata(
            surveyor_identifier="Monsieur Rakoto Jean",
            sampling_frame="systematic_sample",
        )
    assert "personal name" in str(exc.value)


def test_validate_payload_no_pii_function():
    """Verify raw dictionary inspector stops ingestion if sensitive keys are found."""
    clean_payload = {
        "market_code": "MKT_01",
        "product_code": "rice_vary_gasy",
        "quantity_raw": 500.0,
        "unit_raw": "kg",
    }
    # Should not raise
    validate_payload_no_pii(clean_payload)

    # Payload with trader_name
    with pytest.raises(ValueError) as exc1:
        validate_payload_no_pii({**clean_payload, "trader_name": "Soa"})
    assert "Forbidden PII field" in str(exc1.value)

    # Payload with vehicle_plate
    with pytest.raises(ValueError) as exc2:
        validate_payload_no_pii({**clean_payload, "vehicle_plate": "1234TAB"})
    assert "Forbidden PII field" in str(exc2.value)


def test_standardized_unit_conversions():
    """Verify accurate metric kg conversion across standard and Malagasy traditional units."""
    # 1. Metric kg & tonne
    assert convert_quantity_to_kg(150.0, QuantityUnit.KG) == 150.0
    assert convert_quantity_to_kg(2.5, QuantityUnit.TONNE) == 2500.0

    # 2. Standardized bags
    assert convert_quantity_to_kg(10.0, QuantityUnit.BAG_50KG) == 500.0
    assert convert_quantity_to_kg(10.0, QuantityUnit.BAG_100KG) == 1000.0

    # 3. Traditional Gony with commodity density
    # Rice milled gony = 50 kg
    assert convert_quantity_to_kg(20.0, QuantityUnit.GONY, product_code="RICE_MILLED") == 1000.0
    # Rice paddy gony = 48 kg
    assert convert_quantity_to_kg(20.0, QuantityUnit.GONY, product_code="RICE_PADDY") == 960.0
    # Maize gony = 45 kg
    assert convert_quantity_to_kg(20.0, QuantityUnit.GONY, product_code="MAIZE_GRAIN") == 900.0

    # 4. Traditional Kapoaka (300 ml can)
    # Rice milled kapoaka = 0.26 kg
    assert convert_quantity_to_kg(100.0, QuantityUnit.KAPOAKA, product_code="RICE_MILLED") == 26.0
    # Rice paddy kapoaka = 0.28 kg
    assert convert_quantity_to_kg(100.0, QuantityUnit.KAPOAKA, product_code="RICE_PADDY") == 28.0
    # Sugar kapoaka = 0.25 kg
    assert convert_quantity_to_kg(100.0, QuantityUnit.KAPOAKA, product_code="SUGAR_REFINED") == 25.0

    # 5. Invalid negative quantity raises ValueError
    with pytest.raises(ValueError):
        convert_quantity_to_kg(-5.0, QuantityUnit.KG)


def test_validate_no_double_counting_rules():
    """Verify prevention of cross-target additions (flow vs state) and temporal overlaps."""
    rec_arrival = QuantityObservationRecord(
        target=QuantityTarget.INFLOW_ARRIVAL,
        product_code="rice_vary_gasy",
        product_name="Riz blanc",
        market_code="MKT_ANOSIBE",
        market_name="Anosibe",
        location_pcode="MDG11",
        observed_date=date(2024, 5, 10),
        period_start=date(2024, 5, 10),
        period_end=date(2024, 5, 10),
        quantity_raw=50.0,
        unit_raw=QuantityUnit.TONNE,
        quantity_kg=50_000.0,
        measurement_mode=QuantityMeasurementMode.MEASURED_SCALE,
        market_type=MarketType.TERMINAL_URBAN,
    )

    rec_stock = QuantityObservationRecord(
        target=QuantityTarget.STOCK_INVENTORY,
        product_code="rice_vary_gasy",
        product_name="Riz blanc",
        market_code="MKT_ANOSIBE",
        market_name="Anosibe",
        location_pcode="MDG11",
        observed_date=date(2024, 5, 10),
        period_start=date(2024, 5, 10),
        period_end=date(2024, 5, 10),
        quantity_raw=200.0,
        unit_raw=QuantityUnit.TONNE,
        quantity_kg=200_000.0,
        measurement_mode=QuantityMeasurementMode.DECLARED_TRADER,
        market_type=MarketType.TERMINAL_URBAN,
    )

    # 1. Mixing flow and stock triggers double counting risk warning
    violations = validate_no_double_counting([rec_arrival, rec_stock])
    assert len(violations) >= 1
    assert any("DOUBLE_COUNTING_RISK" in v for v in violations)
    assert any("INFLOW_ARRIVAL" in v and "STOCK_INVENTORY" in v for v in violations)

    # 2. Overlapping windows within same target triggers overlap warning
    rec_arrival_overlap = QuantityObservationRecord(
        target=QuantityTarget.INFLOW_ARRIVAL,
        product_code="rice_vary_gasy",
        product_name="Riz blanc",
        market_code="MKT_ANOSIBE",
        market_name="Anosibe",
        location_pcode="MDG11",
        observed_date=date(2024, 5, 10),
        period_start=date(2024, 5, 8),
        period_end=date(2024, 5, 12),
        quantity_raw=80.0,
        unit_raw=QuantityUnit.TONNE,
        quantity_kg=80_000.0,
        measurement_mode=QuantityMeasurementMode.MEASURED_SCALE,
        market_type=MarketType.TERMINAL_URBAN,
    )
    violations_overlap = validate_no_double_counting([rec_arrival, rec_arrival_overlap])
    assert any("TEMPORAL_OVERLAP" in v for v in violations_overlap)

    # 3. Disjoint temporal flow records have zero violations
    rec_arrival_day2 = QuantityObservationRecord(
        target=QuantityTarget.INFLOW_ARRIVAL,
        product_code="rice_vary_gasy",
        product_name="Riz blanc",
        market_code="MKT_ANOSIBE",
        market_name="Anosibe",
        location_pcode="MDG11",
        observed_date=date(2024, 5, 11),
        period_start=date(2024, 5, 11),
        period_end=date(2024, 5, 11),
        quantity_raw=40.0,
        unit_raw=QuantityUnit.TONNE,
        quantity_kg=40_000.0,
        measurement_mode=QuantityMeasurementMode.MEASURED_SCALE,
        market_type=MarketType.TERMINAL_URBAN,
    )
    clean_violations = validate_no_double_counting([rec_arrival, rec_arrival_day2])
    assert len(clean_violations) == 0
