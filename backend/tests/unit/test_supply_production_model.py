"""Unit tests for crop production forecasting model (Area × Yield) (R5.5, ADR-106)."""

import pytest

from ketrika.supply.production_model import (
    AreaSourceKind,
    CropProductionModel,
    ProductionForecastInput,
    ProductionForecastStatus,
)


@pytest.fixture
def model() -> CropProductionModel:
    return CropProductionModel()


def test_conversion_factors_completeness_and_sources(model: CropProductionModel) -> None:
    """Verify that all standard staple commodities have sourced conversion factors and full bibliographic metadata (C022)."""
    staples = ["RICE_PADDY", "MAIZE_COB", "CASSAVA_FRESH", "GROUNDNUT_UNSHELLED", "BEANS_PULSES"]
    for staple in staples:
        factor = model.get_conversion_factor(staple)
        assert factor is not None, f"Missing conversion factor for {staple}"
        assert 0.0 < factor.milling_ratio <= 1.0
        assert 0.0 <= factor.farm_loss_seed_rate < 0.5
        assert len(factor.source_reference.strip()) > 10, "Missing institutional citation"
        assert len(factor.issuing_institution.strip()) > 0, "Missing issuing institution"
        assert len(factor.document_title.strip()) > 0, "Missing document title"
        assert factor.publication_year >= 2020, f"Outdated or missing publication year for {staple}"
        assert len(factor.page_or_table.strip()) > 0, "Missing page/table citation"

    # Specific check for Malagasy rice standard (ODR / FAOSTAT: 0.667 milling, 10% on-farm loss/seed)
    paddy_conv = model.get_conversion_factor("RICE_PADDY")
    assert paddy_conv is not None
    assert paddy_conv.milling_ratio == 0.667
    assert paddy_conv.farm_loss_seed_rate == 0.10


def test_mathematical_identity_production_area_yield(model: CropProductionModel) -> None:
    """Test strict mathematical identity Production = Area × Yield and audited status distinction (C022)."""
    # 1. Experimental unverified estimate (default)
    payload_unaudited = ProductionForecastInput(
        crop_code="RICE_PADDY",
        region_id="MG-U",
        harvest_campaign=2024,
        harvested_area_ha=1000.0,
        area_source_kind=AreaSourceKind.OFFICIAL_CADASTRE_SURVEY,
        water_stress_anomaly=0.0,  # Neutral weather
        is_field_survey_audited=False,
    )
    result_unaudited = model.evaluate(payload_unaudited)
    assert result_unaudited.status == ProductionForecastStatus.EXPERIMENTAL_ESTIMATE
    assert "experimental software estimate" in result_unaudited.methodology

    # 2. Audited ground truth forecast
    payload = ProductionForecastInput(
        crop_code="RICE_PADDY",
        region_id="MG-U",
        harvest_campaign=2024,
        harvested_area_ha=1000.0,
        area_source_kind=AreaSourceKind.OFFICIAL_CADASTRE_SURVEY,
        water_stress_anomaly=0.0,  # Neutral weather
        is_field_survey_audited=True,
    )

    result = model.evaluate(payload)

    assert result.status == ProductionForecastStatus.QUALIFIED_FORECAST
    assert result.harvested_area_ha == 1000.0
    assert result.estimated_yield_t_ha == 3.20
    assert result.gross_harvest_tonnes == 3200.0
    assert result.identity_verified is True

    # Net marketable after 10% loss & seed deduction = 3200 * 0.90 = 2880.0
    assert result.net_marketable_tonnes == 2880.0
    # Milled white rice equivalent = 2880 * 0.667 = 1920.96
    assert result.milled_processed_tonnes == pytest.approx(1920.96, rel=1e-4)
    assert result.uncertainty_range_gross == (2000.0, 4500.0)
    assert result.confidence_score >= 0.80


def test_agroclimatic_yield_adjustment_bounds(model: CropProductionModel) -> None:
    """Test that yield adjusts with rainfall anomaly and stays within physiological limits."""
    # 1. Drought scenario (anomaly = -2.0 sigma) in Alaotra (base 3.2, min 2.0, max 4.5)
    # Expected adjusted = 3.2 * (1 - 0.12 * 2.0) = 3.2 * 0.76 = 2.432 t/ha
    drought_payload = ProductionForecastInput(
        crop_code="RICE_PADDY",
        region_id="MG-U",
        harvest_campaign=2024,
        harvested_area_ha=500.0,
        area_source_kind=AreaSourceKind.REMOTE_SENSING_CROPLAND,
        water_stress_anomaly=-2.0,
        is_field_survey_audited=True,
    )
    drought_res = model.evaluate(drought_payload)
    assert drought_res.status == ProductionForecastStatus.QUALIFIED_FORECAST
    assert drought_res.estimated_yield_t_ha == pytest.approx(2.432, abs=0.01)
    assert drought_res.gross_harvest_tonnes == pytest.approx(500.0 * 2.432, abs=0.5)

    # 2. Extreme catastrophic drought (anomaly = -5.0 sigma) -> bounded at min_yield (2.0 t/ha)
    catastrophic_payload = ProductionForecastInput(
        crop_code="RICE_PADDY",
        region_id="MG-U",
        harvest_campaign=2024,
        harvested_area_ha=500.0,
        area_source_kind=AreaSourceKind.OFFICIAL_CADASTRE_SURVEY,
        water_stress_anomaly=-5.0,
        is_field_survey_audited=True,
    )
    catastrophic_res = model.evaluate(catastrophic_payload)
    assert catastrophic_res.estimated_yield_t_ha == 2.00
    assert catastrophic_res.gross_harvest_tonnes == 1000.0

    # 3. Super-optimal season (anomaly = +4.0 sigma) -> bounded at max_yield (4.5 t/ha)
    excess_payload = ProductionForecastInput(
        crop_code="RICE_PADDY",
        region_id="MG-U",
        harvest_campaign=2024,
        harvested_area_ha=500.0,
        area_source_kind=AreaSourceKind.OFFICIAL_CADASTRE_SURVEY,
        water_stress_anomaly=4.0,
        is_field_survey_audited=True,
    )
    excess_res = model.evaluate(excess_payload)
    assert excess_res.estimated_yield_t_ha == 4.50
    assert excess_res.gross_harvest_tonnes == 2250.0


def test_strict_abstention_on_unverified_national_area(model: CropProductionModel) -> None:
    """Ensure ADR-106 rule: FAOSTAT top-down unverified national area cannot be used for local production."""
    payload = ProductionForecastInput(
        crop_code="RICE_PADDY",
        region_id="MG-U",
        harvest_campaign=2024,
        harvested_area_ha=50000.0,
        area_source_kind=AreaSourceKind.NATIONAL_UNVERIFIED,
    )
    res = model.evaluate(payload)

    assert res.status == ProductionForecastStatus.ABSTAINED_UNVERIFIED_AREA
    assert res.gross_harvest_tonnes is None
    assert res.net_marketable_tonnes is None
    assert res.milled_processed_tonnes is None
    assert res.identity_verified is False
    assert "FAOSTAT national top-down area" in (res.abstention_reason or "")


def test_strict_abstention_on_insufficient_campaign_history(model: CropProductionModel) -> None:
    """Ensure ADR-106 rule: less than 2 recorded historical campaigns requires explicit abstention."""
    # 1. Unrecorded region/crop baseline
    unknown_payload = ProductionForecastInput(
        crop_code="RICE_PADDY",
        region_id="UNKNOWN_REGION",
        harvest_campaign=2024,
        harvested_area_ha=100.0,
        area_source_kind=AreaSourceKind.OFFICIAL_CADASTRE_SURVEY,
    )
    unknown_res = model.evaluate(unknown_payload)
    assert unknown_res.status == ProductionForecastStatus.ABSTAINED_INSUFFICIENT_HISTORY
    assert unknown_res.gross_harvest_tonnes is None
    assert "Insufficient campaign history" in (unknown_res.abstention_reason or "")

    # 2. Recorded baseline but historical count explicitly less than 2
    insufficient_payload = ProductionForecastInput(
        crop_code="RICE_PADDY",
        region_id="MG-U",
        harvest_campaign=2024,
        harvested_area_ha=100.0,
        area_source_kind=AreaSourceKind.OFFICIAL_CADASTRE_SURVEY,
        historical_campaigns_count=1,  # Only 1 campaign
    )
    insufficient_res = model.evaluate(insufficient_payload)
    assert insufficient_res.status == ProductionForecastStatus.ABSTAINED_INSUFFICIENT_HISTORY
    assert insufficient_res.gross_harvest_tonnes is None


def test_invalid_negative_or_zero_area(model: CropProductionModel) -> None:
    """Ensure non-positive harvested area is rejected."""
    payload = ProductionForecastInput(
        crop_code="RICE_PADDY",
        region_id="MG-U",
        harvest_campaign=2024,
        harvested_area_ha=-10.0,
        area_source_kind=AreaSourceKind.OFFICIAL_CADASTRE_SURVEY,
    )
    res = model.evaluate(payload)
    assert res.status == ProductionForecastStatus.INVALID_INPUT
    assert res.gross_harvest_tonnes is None


def test_batch_evaluation_and_cassava_maize_conversions(model: CropProductionModel) -> None:
    """Test batch evaluation covering maize and cassava agro-industrial processing."""
    inputs = [
        # Atsimo-Andrefana Maize (Audited)
        ProductionForecastInput(
            crop_code="MAIZE_COB",
            region_id="MG-H",
            harvest_campaign=2024,
            harvested_area_ha=200.0,
            area_source_kind=AreaSourceKind.OFFICIAL_CADASTRE_SURVEY,
            water_stress_anomaly=-0.5,
            is_field_survey_audited=True,
        ),
        # Atsinanana Cassava (Unaudited remote sensing estimate)
        ProductionForecastInput(
            crop_code="CASSAVA_FRESH",
            region_id="MG-O",
            harvest_campaign=2024,
            harvested_area_ha=100.0,
            area_source_kind=AreaSourceKind.REMOTE_SENSING_CROPLAND,
            water_stress_anomaly=0.5,
            is_field_survey_audited=False,
        ),
    ]

    results = model.batch_evaluate(inputs)
    assert len(results) == 2

    # Check maize
    maize_res = results[0]
    assert maize_res.status == ProductionForecastStatus.QUALIFIED_FORECAST
    assert maize_res.gross_harvest_tonnes is not None
    assert maize_res.net_marketable_tonnes is not None
    assert maize_res.milled_processed_tonnes is not None
    assert maize_res.conversion_factor is not None
    assert maize_res.conversion_factor.processed_commodity == "MAIZE_GRAIN"

    # Check cassava
    cassava_res = results[1]
    assert cassava_res.status == ProductionForecastStatus.EXPERIMENTAL_ESTIMATE
    assert cassava_res.gross_harvest_tonnes is not None
    assert cassava_res.milled_processed_tonnes is not None
    assert cassava_res.conversion_factor is not None
    assert cassava_res.conversion_factor.processed_commodity == "CASSAVA_DRIED"
    assert cassava_res.milled_processed_tonnes < cassava_res.gross_harvest_tonnes
