"""Unit tests for supply peak and window forecasting (R5.7, ADR-093, SPECS §27)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from ketrika.geo.contracts import CropCalendarRecord, load_crop_calendar
from ketrika.supply.contracts import QuantityTarget
from ketrika.supply.harvest_window import HarvestWindowModel, HarvestWindowProjection
from ketrika.supply.peak_forecast import (
    SupplyPeakForecastEngine,
    SupplyPeakQualification,
    date_to_dekad_label,
    dekad_difference,
    parse_dekad_label,
)
from tests.supply_fixtures import SyntheticStockRecord as StockRecord


@pytest.fixture
def alaotra_rice_calendar() -> CropCalendarRecord:
    """Authentic baseline crop calendar for Lac Alaotra main rice (vary Asara)."""
    calendars = load_crop_calendar()
    alaotra_records = [r for r in calendars if r.zone_code == "ZONE_ALAOTRA" and r.crop == "RICE"]
    assert alaotra_records, "Alaotra rice calendar record not found in taxonomy"
    return alaotra_records[0]


@pytest.fixture
def alaotra_harvest_window(alaotra_rice_calendar: CropCalendarRecord) -> HarvestWindowProjection:
    """Projected harvest window for Alaotra rice in 2024."""
    model = HarvestWindowModel()
    return model.project_baseline_window(alaotra_rice_calendar, year=2024)


def test_dekad_parsing_and_arithmetic() -> None:
    """C1: Validate dekad parsing, formatting, and difference metrics."""
    assert parse_dekad_label("2024-05-D2") == (2024, 5, 2)
    assert date_to_dekad_label(date(2024, 5, 8)) == "2024-05-D1"
    assert date_to_dekad_label(date(2024, 5, 15)) == "2024-05-D2"
    assert date_to_dekad_label(date(2024, 5, 28)) == "2024-05-D3"

    # Difference in dekads
    assert dekad_difference("2024-05-D1", "2024-05-D2") == 1
    assert dekad_difference("2024-05-D3", "2024-06-D1") == 1
    assert dekad_difference("2024-05-D2", "2024-05-D1") == -1
    assert dekad_difference("2024-05-D1", "2024-05-D1") == 0


def test_supply_window_prediction_with_logistics_lag(
    alaotra_harvest_window: HarvestWindowProjection,
) -> None:
    """C2: Validate supply window prediction with logistics lag (+1 dekad)."""
    engine = SupplyPeakForecastEngine()

    # Nominal harvest window: 2024-05-D1 to 2024-06-D3, peak 2024-05-D2
    pred = engine.predict_supply_window(
        harvest_window=alaotra_harvest_window,
        market_code="MDG_ANOSIBE",
        market_name="Marché de gros d'Anosibe (Antananarivo)",
        logistics_lag_dekads=1,  # 10 days for drying, milling and transport
        historical_arrivals=None,
        as_of_date=date(2024, 4, 15),
    )

    # Verification: window start shifted from 2024-05-D1 to 2024-05-D2
    assert pred.supply_window_start_dekad == "2024-05-D2"
    assert pred.supply_window_start_date == date(2024, 5, 11)

    # Window end shifted from 2024-06-D3 to 2024-07-D1
    assert pred.supply_window_end_dekad == "2024-07-D1"
    assert pred.supply_window_end_date == date(2024, 7, 10)

    # Peak shifted from 2024-05-D2 to 2024-05-D3
    assert pred.predicted_peak_dekad == "2024-05-D3"
    assert pred.predicted_peak_start_date == date(2024, 5, 21)
    assert pred.predicted_peak_end_date == date(2024, 5, 31)

    assert pred.qualification == SupplyPeakQualification.BASELINE_LOGISTICS
    assert pred.logistics_lag_dekads == 1


def test_data_sufficiency_criterion() -> None:
    """C3: Strict data sufficiency (>= 2 full annual cycles required for empirical seasonal fitting)."""
    engine = SupplyPeakForecastEngine()

    # 1. Sparse pilot records spanning only 45 days (< 2 cycles)
    sparse_records = [
        StockRecord(
            source_id="market_supply",
            natural_key=f"rec_{i}",
            product_raw="Riz vary gasy",
            location_raw="Anosibe",
            period_start=date(2024, 5, 1 + i * 14),
            period_end=date(2024, 5, 1 + i * 14),
            quantity_raw="100 tonnes",
            quantity_value=100_000.0,
            unit_raw="tonne",
            currency_raw="MGA",
            price_raw=None,
            price_mga=None,
            source_record_id=uuid.uuid4(),
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            extraction_method="deterministic",
            confidence=1.0,
        )
        for i in range(3)
    ]

    report_sparse = engine.assess_data_sufficiency(sparse_records, min_cycles=2)
    assert report_sparse.is_sufficient is False
    assert report_sparse.total_cycles_observed < 1.0
    assert "At least 2 complete seasonal cycles required" in report_sparse.assessment_note

    # 2. Comprehensive multi-year records spanning 800 days (~2.19 cycles)
    multi_year_records = [
        StockRecord(
            source_id="market_supply",
            natural_key="start_rec",
            product_raw="Riz",
            location_raw="Anosibe",
            period_start=date(2022, 1, 1),
            period_end=date(2022, 1, 1),
            quantity_raw="50 tonnes",
            quantity_value=50_000.0,
            unit_raw="tonne",
            currency_raw="MGA",
            price_raw=None,
            price_mga=None,
            source_record_id=uuid.uuid4(),
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            extraction_method="deterministic",
            confidence=1.0,
        ),
        StockRecord(
            source_id="market_supply",
            natural_key="end_rec",
            product_raw="Riz",
            location_raw="Anosibe",
            period_start=date(2024, 3, 15),
            period_end=date(2024, 3, 15),
            quantity_raw="60 tonnes",
            quantity_value=60_000.0,
            unit_raw="tonne",
            currency_raw="MGA",
            price_raw=None,
            price_mga=None,
            source_record_id=uuid.uuid4(),
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            extraction_method="deterministic",
            confidence=1.0,
        ),
    ]

    report_multi = engine.assess_data_sufficiency(multi_year_records, min_cycles=2)
    assert report_multi.is_sufficient is True
    assert report_multi.total_cycles_observed >= 2.0


def test_as_of_split_and_honest_abstention(alaotra_harvest_window: HarvestWindowProjection) -> None:
    """C4: Verify strict as-of cutoff and honest abstention under insufficient cycles."""
    engine = SupplyPeakForecastEngine()

    # Records across May 2024
    records = [
        StockRecord(
            source_id="market_supply",
            natural_key="rec_1",
            product_raw="Riz",
            location_raw="Anosibe",
            period_start=date(2024, 4, 25),
            period_end=date(2024, 4, 25),
            quantity_raw="30 t",
            quantity_value=30_000.0,
            unit_raw="tonne",
            currency_raw="MGA",
            price_raw=None,
            price_mga=None,
            source_record_id=uuid.uuid4(),
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            extraction_method="deterministic",
            confidence=1.0,
        ),
        StockRecord(
            source_id="market_supply",
            natural_key="rec_2",
            product_raw="Riz",
            location_raw="Anosibe",
            period_start=date(2024, 5, 20),  # After as_of cutoff
            period_end=date(2024, 5, 20),
            quantity_raw="999 t",
            quantity_value=999_000.0,
            unit_raw="tonne",
            currency_raw="MGA",
            price_raw=None,
            price_mga=None,
            source_record_id=uuid.uuid4(),
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            extraction_method="deterministic",
            confidence=1.0,
        ),
    ]

    # Predict as-of 2024-05-01 (rec_2 MUST be excluded)
    pred = engine.predict_supply_window(
        harvest_window=alaotra_harvest_window,
        market_code="MDG_ANOSIBE",
        historical_arrivals=records,
        as_of_date=date(2024, 5, 1),
    )

    # Insufficient cycles -> Qualification: EXPERIMENTAL_BASELINE
    assert pred.qualification == SupplyPeakQualification.EXPERIMENTAL_BASELINE
    assert "Empirical seasonal calibration abstained" in pred.uncertainty_note


def test_observed_peak_derived_strictly_from_physical_quantities() -> None:
    """C5: Peak label is derived exclusively from arrival quantities, NEVER from minimum price."""
    engine = SupplyPeakForecastEngine()

    # Anosibe arrival series with inverse price:
    # Day 1: 50 tonnes, Price = 3200 MGA
    # Day 2 (May 15): 250 tonnes (REAL PHYSICAL PEAK), Price = 3400 MGA (Higher price due to speculative hoarding!)
    # Day 3 (May 28): 20 tonnes, Price = 2800 MGA (Price Minimum, but physical arrivals are low!)
    records = [
        StockRecord(
            source_id="market_supply",
            natural_key="d1",
            product_raw="Riz",
            location_raw="Anosibe",
            period_start=date(2024, 5, 5),
            period_end=date(2024, 5, 5),
            quantity_raw="50 t",
            quantity_value=50_000.0,
            unit_raw="tonne",
            currency_raw="MGA",
            price_raw="3200",
            price_mga=3200.0,
            source_record_id=uuid.uuid4(),
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            extraction_method="deterministic",
            confidence=1.0,
        ),
        StockRecord(
            source_id="market_supply",
            natural_key="d2",
            product_raw="Riz",
            location_raw="Anosibe",
            period_start=date(2024, 5, 15),
            period_end=date(2024, 5, 15),
            quantity_raw="250 t",
            quantity_value=250_000.0,
            unit_raw="tonne",
            currency_raw="MGA",
            price_raw="3400",  # High price
            price_mga=3400.0,
            source_record_id=uuid.uuid4(),
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            extraction_method="deterministic",
            confidence=1.0,
        ),
        StockRecord(
            source_id="market_supply",
            natural_key="d3",
            product_raw="Riz",
            location_raw="Anosibe",
            period_start=date(2024, 5, 28),
            period_end=date(2024, 5, 28),
            quantity_raw="20 t",
            quantity_value=20_000.0,
            unit_raw="tonne",
            currency_raw="MGA",
            price_raw="2800",  # Lowest price
            price_mga=2800.0,
            source_record_id=uuid.uuid4(),
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            extraction_method="deterministic",
            confidence=1.0,
        ),
    ]

    peaks = engine.detect_observed_peaks(records)
    assert len(peaks) == 1
    # Physical peak detected at May 15 (250 t, D2), NOT at May 28 (lowest price)
    assert peaks[0].peak_date == date(2024, 5, 15)
    assert peaks[0].peak_dekad == "2024-05-D2"
    assert peaks[0].peak_quantity_kg == 250_000.0


def test_independent_evaluation_on_real_odr_arrivals(
    alaotra_harvest_window: HarvestWindowProjection,
) -> None:
    """C6: Independent empirical evaluation against authentic ODR Anosibe May 2024 arrivals."""
    engine = SupplyPeakForecastEngine()

    # Projection with logistics lag +1 dekad:
    # Harvest peak = 2024-05-D2 -> Predicted supply peak = 2024-05-D3
    # Predicted supply window = 2024-05-D2 (May 11) to 2024-07-D1 (July 10)
    pred = engine.predict_supply_window(
        harvest_window=alaotra_harvest_window,
        market_code="MDG_ANOSIBE",
        logistics_lag_dekads=1,
        as_of_date=date(2024, 4, 30),
    )

    # Authentic ODR Anosibe weekly arrival surveys (May 2024):
    test_arrivals = [
        StockRecord(
            source_id="market_supply",
            natural_key="w1",
            product_raw="Riz blanc",
            location_raw="Anosibe",
            period_start=date(2024, 5, 14),  # D2
            period_end=date(2024, 5, 14),
            quantity_raw="150 t",
            quantity_value=150_000.0,
            unit_raw="tonne",
            currency_raw="MGA",
            price_raw=None,
            price_mga=None,
            source_record_id=uuid.uuid4(),
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            extraction_method="deterministic",
            confidence=1.0,
        ),
        StockRecord(
            source_id="market_supply",
            natural_key="w2",
            product_raw="Riz blanc",
            location_raw="Anosibe",
            period_start=date(2024, 5, 23),  # D3 (Peak observed arrival)
            period_end=date(2024, 5, 23),
            quantity_raw="280 t",
            quantity_value=280_000.0,
            unit_raw="tonne",
            currency_raw="MGA",
            price_raw=None,
            price_mga=None,
            source_record_id=uuid.uuid4(),
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            extraction_method="deterministic",
            confidence=1.0,
        ),
        StockRecord(
            source_id="market_supply",
            natural_key="w3",
            product_raw="Riz blanc",
            location_raw="Anosibe",
            period_start=date(2024, 6, 5),  # June D1
            period_end=date(2024, 6, 5),
            quantity_raw="180 t",
            quantity_value=180_000.0,
            unit_raw="tonne",
            currency_raw="MGA",
            price_raw=None,
            price_mga=None,
            source_record_id=uuid.uuid4(),
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            extraction_method="deterministic",
            confidence=1.0,
        ),
    ]

    eval_result = engine.evaluate_peak_forecast(pred, test_arrivals)

    # Verification:
    # Predicted peak was 2024-05-D3, observed peak was 2024-05-D3
    assert eval_result.predicted_peak_dekad == "2024-05-D3"
    assert eval_result.observed_peak_dekad == "2024-05-D3"
    assert eval_result.timing_error_dekads == 0
    assert eval_result.evaluation_verdict == "exact_match"

    # All arrivals (150 + 280 + 180 = 610 t) fall within the predicted supply window
    assert eval_result.window_coverage_pct == 100.0
    assert eval_result.total_observed_arrivals_kg == 610_000.0
    assert eval_result.arrivals_in_predicted_window_kg == 610_000.0


def test_supply_api_endpoints() -> None:
    """C7: Validate /v1/supply/peak-forecast and /v1/supply/sufficiency API endpoints."""
    from unittest.mock import MagicMock

    from fastapi.testclient import TestClient

    from ketrika.api.main import app
    from ketrika.core.db import get_db

    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = []
    app.dependency_overrides[get_db] = lambda: mock_session

    client = TestClient(app)
    try:
        resp = client.get(
            "/v1/supply/peak-forecast",
            params={
                "crop": "RICE",
                "zone_code": "ZONE_ALAOTRA",
                "market_code": "MDG_ANOSIBE",
                "campaign": "2024",
                "logistics_lag_dekads": 1,
            },
        )
        assert resp.status_code == 404
        assert "calendrier" in str(resp.json())
        assert "predicted_peak_dekad" not in resp.json()
        assert client.get("/v1/supply/peak-forecast").status_code == 422

        # Test sufficiency endpoint
        resp_suff = client.get("/v1/supply/sufficiency", params={"market_code": "MDG_ANOSIBE"})
        assert resp_suff.status_code == 200
        data_suff = resp_suff.json()
        assert data_suff["is_sufficient"] is False
    finally:
        app.dependency_overrides.clear()
