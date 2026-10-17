"""Unit tests for verifiable harvest window projections and agroclimatic adjustments (R5.4, ADR-091, SPECS §26-27)."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.market_supply import MarketSupplyConnector
from ketrika.geo.contracts import (
    CropRegime,
    load_crop_calendar,
)
from ketrika.supply.harvest_window import (
    HarvestWindowModel,
    ValidationLevel,
    get_dekad_bounds,
    shift_dekad,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "market_supply"


class DummyBronzeStore:
    def __init__(self, data: bytes):
        self._data = data

    def get(self, object_key: str) -> bytes | None:
        return self._data


def test_dekad_bounds_and_shifts():
    """Verify dekadal bounds calculation for standard calendar months."""
    # May has 31 days
    d1_start, d1_end = get_dekad_bounds(2024, 5, 1)
    assert d1_start == date(2024, 5, 1)
    assert d1_end == date(2024, 5, 10)

    d2_start, d2_end = get_dekad_bounds(2024, 5, 2)
    assert d2_start == date(2024, 5, 11)
    assert d2_end == date(2024, 5, 20)

    d3_start, d3_end = get_dekad_bounds(2024, 5, 3)
    assert d3_start == date(2024, 5, 21)
    assert d3_end == date(2024, 5, 31)

    # Shift dekad forward
    y, m, d = shift_dekad(2024, 5, 2, 2)  # May D2 + 2 dekads -> June D1
    assert (y, m, d) == (2024, 6, 1)


def test_baseline_window_reproduction_from_official_calendar():
    """Verify that baseline projection reproduces official crop calendar harvest window exactly."""
    calendars = load_crop_calendar()
    # Find Alaotra rice cycle
    alaotra_records = [
        r for r in calendars
        if r.zone_code == "ZONE_ALAOTRA" and r.crop == "RICE"
    ]
    assert len(alaotra_records) >= 1
    record = alaotra_records[0]

    model = HarvestWindowModel()
    window = model.project_baseline_window(record, year=2024)

    assert window.zone_code == "ZONE_ALAOTRA"
    assert window.crop == "RICE"
    assert window.shift_dekads == 0
    assert window.validation_level == ValidationLevel.BASELINE_REFERENCE
    assert window.confidence_score >= 0.85

    # Harvest months in official calendar are May-June (months 5 and 6)
    assert window.baseline_harvest_start_month == 5
    assert window.baseline_harvest_end_month == 6
    assert window.window_start_dekad == "2024-05-D1"
    assert window.window_end_dekad == "2024-06-D3"
    assert window.peak_harvest_dekad == "2024-05-D2"
    assert window.window_start_date == date(2024, 5, 1)
    assert window.window_end_date == date(2024, 6, 30)


def test_irrigated_regime_buffers_moderate_rainfall_deficit():
    """Verify that irrigated perimeters with water control buffer moderate rainfall delays."""
    calendars = load_crop_calendar()
    alaotra_irrigated = [
        r for r in calendars
        if r.zone_code == "ZONE_ALAOTRA" and r.crop_regime == CropRegime.IRRIGATED
    ][0]

    model = HarvestWindowModel()
    # Moderate deficit of -25%
    window = model.project_adjusted_window(
        alaotra_irrigated,
        year=2024,
        rainfall_early_anomaly_pct=-25.0,
    )

    # Shift must remain 0 because irrigation buffers moderate deficits
    assert window.shift_dekads == 0
    assert window.validation_level == ValidationLevel.BASELINE_REFERENCE
    assert "Irrigated regime with hydraulic control buffers" in str(window.shift_reason)


def test_rainfed_crop_shifted_under_severe_early_drought_scenario():
    """Verify that authentic rainfed crops undergo an agronomically grounded 2-dekad shift under severe drought."""
    calendars = load_crop_calendar()
    # Find real rainfed maize in official calendar (e.g. ZONE_SUD or ZONE_CENTRE)
    rainfed_maize_records = [
        r for r in calendars
        if r.crop == "MAIZE" and r.crop_regime == CropRegime.RAINFED
    ]
    assert len(rainfed_maize_records) >= 1
    rainfed_maize = rainfed_maize_records[0]

    model = HarvestWindowModel()
    # Scenario: severe early drought (-38% rainfall)
    adjusted = model.project_adjusted_window(
        rainfed_maize,
        year=2024,
        rainfall_early_anomaly_pct=-38.0,
    )

    assert adjusted.shift_dekads == 2
    assert adjusted.validation_level == ValidationLevel.ADJUSTED_CAMPAIGN_RULE
    assert adjusted.window_start_dekad == "2024-03-D3"  # Shifted from March D1 to March D3
    assert adjusted.peak_harvest_dekad == "2024-05-D1"  # Shifted from April D2 to May D1
    assert "Severe early rainfall deficit (-38.0%) delayed planting" in str(adjusted.shift_reason)
    assert adjusted.window_start_date == date(2024, 3, 21)


def test_independent_empirical_confrontation_with_odr_market_arrivals():
    """Verify independent empirical confrontation against authentic ODR market arrival records."""
    # 1. Parse authentic Anosibe market supply dataset
    fixture_path = FIXTURES_DIR / "odr_approvisionnement_anosibe_2024.csv"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = MarketSupplyConnector()
    ctx = RunContext(
        source_id="market_supply",
        run_id="run-confrontation",
        bronze_store=DummyBronzeStore(payload),
        metadata={},
    )
    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="file:///workspace/data/supply/odr_suivi_approvisionnement_anosibe_2024.csv",
        object_key="raw/market_supply/anosibe_2024.csv",
        mime_type="text/csv",
        content_sha256="mockshaeval",
        is_new=True,
    )
    result = connector.parse(artifact, ctx)
    assert len(result.records) == 7

    # 2. Project Alaotra / Hauts Plateaux rice harvest window for May 2024
    calendars = load_crop_calendar()
    rice_record = [r for r in calendars if r.zone_code == "ZONE_ALAOTRA" and r.crop == "RICE"][0]

    model = HarvestWindowModel()
    window = model.project_baseline_window(rice_record, year=2024)

    # 3. Confront against authentic market arrivals
    confrontation = model.evaluate_against_market_arrivals(window, result.records)

    assert confrontation.total_records_tested >= 2
    assert confrontation.arrivals_within_harvest_window_kg >= 180_000.0  # Anosibe rice arrivals in May 2024
    assert confrontation.temporal_alignment_ratio >= 0.70
    assert confrontation.peak_inside_window
    assert confrontation.evaluation_verdict == "consistent"
    assert "within the projected window" in confrontation.confrontation_details


def test_experimental_uncertainty_note_integrity():
    """Verify that projections explicitly report qualitative uncertainty and never promise false certainty."""
    calendars = load_crop_calendar()
    record = calendars[0]

    model = HarvestWindowModel()
    # Explicit drought simulation
    proj = model.project_adjusted_window(record, year=2024, is_drought_scenario=True)

    assert proj.validation_level == ValidationLevel.ADJUSTED_CAMPAIGN_RULE
    assert "Experimental model qualification" in proj.uncertainty_note
    # Must NOT claim guaranteed precision
    assert "garantie" not in proj.uncertainty_note.lower()
    assert "precision" not in proj.uncertainty_note.lower()
