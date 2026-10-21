"""Unit tests for remote sensing cropland vegetation condition (NDVI, VCI, SCL masking) (R4.8, ADR-107)."""

import pytest

from ketrika.geo.remote_sensing import (
    CLOUD_AND_OBSCURATION_SCL,
    ProhibitedYieldInferenceError,
    RemoteSensingStatus,
    Sentinel2SCLClass,
    VegetationConditionClass,
    classify_vci,
    compute_pixel_ndvi,
    compute_vci,
    evaluate_cropland_vegetation_condition,
    infer_production_tonnes_from_ndvi,
)


def test_pixel_ndvi_calculation_and_scl_cloud_masking() -> None:
    """Verify that NDVI is mathematically exact and cloud/shadow pixels are converted to None."""
    # 1. Healthy green crop: NIR = 0.60, RED = 0.10 -> (0.6 - 0.1) / (0.6 + 0.1) = 0.5 / 0.7 = 0.714
    ndvi_healthy = compute_pixel_ndvi(0.60, 0.10, scl=Sentinel2SCLClass.VEGETATION)
    assert ndvi_healthy is not None
    assert ndvi_healthy == pytest.approx(0.714, abs=1e-3)

    # 2. Water surface: NIR = 0.02, RED = 0.08 -> (0.02 - 0.08) / 0.10 = -0.60
    ndvi_water = compute_pixel_ndvi(0.02, 0.08, scl=Sentinel2SCLClass.WATER)
    assert ndvi_water is not None
    assert ndvi_water == pytest.approx(-0.60, abs=1e-3)

    # 3. Cloud obscuration: Medium cloud (SCL=8), High cloud (SCL=9), Cirrus (SCL=10), Cloud shadow (SCL=3)
    for scl_cloud in (
        Sentinel2SCLClass.CLOUD_MEDIUM_PROBABILITY,
        Sentinel2SCLClass.CLOUD_HIGH_PROBABILITY,
        Sentinel2SCLClass.THIN_CIRRUS,
        Sentinel2SCLClass.CLOUD_SHADOWS,
        Sentinel2SCLClass.NO_DATA,
        Sentinel2SCLClass.SATURATED_OR_DEFECTIVE,
    ):
        assert scl_cloud in CLOUD_AND_OBSCURATION_SCL
        # Even with valid-looking reflectance, cloud SCL must return None (never treated as dead vegetation)
        assert compute_pixel_ndvi(0.50, 0.10, scl=scl_cloud) is None

    # 4. Zero denominator edge-case
    assert compute_pixel_ndvi(0.0, 0.0, scl=Sentinel2SCLClass.VEGETATION) is None

    # 5. Unphysical or negative reflectance rejection (C022 fail-closed)
    assert compute_pixel_ndvi(-0.05, 0.10, scl=Sentinel2SCLClass.VEGETATION) is None
    assert compute_pixel_ndvi(0.50, -0.02, scl=Sentinel2SCLClass.VEGETATION) is None
    assert compute_pixel_ndvi(2.50, 0.10, scl=Sentinel2SCLClass.VEGETATION) is None
    assert compute_pixel_ndvi(float("inf"), 0.10, scl=Sentinel2SCLClass.VEGETATION) is None
    assert compute_pixel_ndvi(0.50, float("nan"), scl=Sentinel2SCLClass.VEGETATION) is None


def test_vci_calculation_and_agronomic_classification() -> None:
    """Test VCI normalization relative to historical bounds and condition classification."""
    min_ndvi = 0.20
    max_ndvi = 0.80

    # Historical min -> VCI = 0.0 (Severe drought)
    vci_min = compute_vci(0.20, min_ndvi, max_ndvi)
    assert vci_min == 0.0
    assert classify_vci(vci_min) == VegetationConditionClass.SEVERE_DROUGHT

    # Severe stress below 20
    assert classify_vci(15.0) == VegetationConditionClass.SEVERE_DROUGHT

    # Moderate stress: 20 <= VCI < 35
    assert classify_vci(28.0) == VegetationConditionClass.MODERATE_STRESS

    # Normal: 35 <= VCI <= 60
    vci_mid = compute_vci(0.50, min_ndvi, max_ndvi)  # (0.5 - 0.2)/(0.8 - 0.2) = 0.3/0.6 = 50%
    assert vci_mid == pytest.approx(50.0, abs=1e-2)
    assert classify_vci(vci_mid) == VegetationConditionClass.NORMAL

    # Favorable: 60 < VCI <= 80
    assert classify_vci(72.0) == VegetationConditionClass.FAVORABLE

    # Optimal: VCI > 80
    vci_max = compute_vci(0.80, min_ndvi, max_ndvi)
    assert vci_max == 100.0
    assert classify_vci(vci_max) == VegetationConditionClass.OPTIMAL

    # Bounded clamping beyond historical extremes
    assert compute_vci(0.95, min_ndvi, max_ndvi) == 100.0
    assert compute_vci(0.05, min_ndvi, max_ndvi) == 0.0
    assert compute_vci(None, min_ndvi, max_ndvi) is None
    assert classify_vci(None) == VegetationConditionClass.UNAVAILABLE

    # Rejection of flat or inverted historical bounds (C022: never fabricate 50.0)
    assert compute_vci(0.50, 0.50, 0.50) is None
    assert compute_vci(0.50, 0.80, 0.20) is None


def test_evaluate_cropland_vegetation_condition_nominal_clear_sky() -> None:
    """Test spatial evaluation on clear sky scene over cropland with verified STAC asset."""
    # 10 pixels: 6 cropland (mask=1), 4 non-cropland (forest/water, mask=0)
    # Cropland pixels are clear vegetation (SCL=4)
    # NIR=0.55, RED=0.15 -> NDVI = 0.40 / 0.70 = 0.571
    nir = [0.55] * 6 + [0.70] * 4
    red = [0.15] * 6 + [0.05] * 4
    cropland = [1, 1, 1, 1, 1, 1, 0, 0, 0, 0]
    scl = [int(Sentinel2SCLClass.VEGETATION)] * 10

    res = evaluate_cropland_vegetation_condition(
        nir_band=nir,
        red_band=red,
        cropland_mask=cropland,
        scl_band=scl,
        historical_ndvi_min=0.20,
        historical_ndvi_max=0.80,
        stac_item_id="S2B_MSIL2A_20231201T070219_R120_T38KRE",
    )

    assert res.status == RemoteSensingStatus.QUALIFIED
    assert res.total_pixels == 10
    assert res.cropland_pixels == 6
    assert res.cloud_pixels == 0
    assert res.valid_cropland_pixels == 6
    assert res.valid_cropland_ratio == 1.0
    assert res.ndvi_mean == pytest.approx(0.571, abs=1e-3)
    assert res.vci_mean is not None
    # VCI = 100 * (0.571 - 0.20) / (0.80 - 0.20) = 100 * 0.371 / 0.60 = 61.8% -> Favorable
    assert res.vci_mean == pytest.approx(61.9, abs=0.5)
    assert res.condition_class == VegetationConditionClass.FAVORABLE
    assert res.abstention_reason is None


def test_unverified_stac_returns_table_calculation_unverified() -> None:
    """Ensure in-memory array calculations without STAC asset provenance are distinguished (C022)."""
    res = evaluate_cropland_vegetation_condition(
        nir_band=[0.55, 0.55],
        red_band=[0.15, 0.15],
        cropland_mask=[1, 1],
        historical_ndvi_min=0.20,
        historical_ndvi_max=0.80,
        stac_item_id=None,  # No STAC item ID
    )
    assert res.status == RemoteSensingStatus.TABLE_CALCULATION_UNVERIFIED
    assert "without verified STAC item asset provenance" in (res.abstention_reason or "")


def test_invalid_historical_range_rejection() -> None:
    """Ensure flat, inverted, or missing historical NDVI ranges are rejected (C022)."""
    # Inverted range: min 0.8 > max 0.2
    res_inv = evaluate_cropland_vegetation_condition(
        nir_band=[0.55, 0.55],
        red_band=[0.15, 0.15],
        cropland_mask=[1, 1],
        historical_ndvi_min=0.80,
        historical_ndvi_max=0.20,
    )
    assert res_inv.status == RemoteSensingStatus.INVALID_HISTORICAL_RANGE
    assert "Historical NDVI bounds must be verified" in (res_inv.abstention_reason or "")

    # Flat range: min 0.5 == max 0.5
    res_flat = evaluate_cropland_vegetation_condition(
        nir_band=[0.55, 0.55],
        red_band=[0.15, 0.15],
        cropland_mask=[1, 1],
        historical_ndvi_min=0.50,
        historical_ndvi_max=0.50,
    )
    assert res_flat.status == RemoteSensingStatus.INVALID_HISTORICAL_RANGE


def test_strict_abstention_on_cloud_cover_over_70_percent() -> None:
    """Ensure ADR-107 rule: if cloud cover > 70% (valid cropland pixels < 30%), model must abstain."""
    # 10 cropland pixels: 8 obscured by clouds (SCL=9), 2 clear (SCL=4)
    # Valid cropland ratio = 2/10 = 20% < 30% threshold
    nir = [0.50] * 10
    red = [0.15] * 10
    cropland = [1] * 10
    scl = [
        int(Sentinel2SCLClass.CLOUD_HIGH_PROBABILITY),
        int(Sentinel2SCLClass.CLOUD_HIGH_PROBABILITY),
        int(Sentinel2SCLClass.CLOUD_MEDIUM_PROBABILITY),
        int(Sentinel2SCLClass.CLOUD_SHADOWS),
        int(Sentinel2SCLClass.THIN_CIRRUS),
        int(Sentinel2SCLClass.CLOUD_HIGH_PROBABILITY),
        int(Sentinel2SCLClass.CLOUD_HIGH_PROBABILITY),
        int(Sentinel2SCLClass.CLOUD_HIGH_PROBABILITY),
        int(Sentinel2SCLClass.VEGETATION),
        int(Sentinel2SCLClass.VEGETATION),
    ]

    res = evaluate_cropland_vegetation_condition(
        nir_band=nir,
        red_band=red,
        cropland_mask=cropland,
        scl_band=scl,
        historical_ndvi_min=0.20,
        historical_ndvi_max=0.80,
        min_valid_cropland_ratio=0.30,
    )

    assert res.status == RemoteSensingStatus.CLOUD_OBSCURED_UNAVAILABLE
    assert res.condition_class == VegetationConditionClass.UNAVAILABLE
    assert res.valid_cropland_pixels == 2
    assert res.valid_cropland_ratio == 0.20
    assert res.ndvi_mean is None
    assert res.vci_mean is None
    assert "Cloud cover exceeds 70%" in (res.abstention_reason or "")
    assert "Explicit abstention to prevent false drought" in (res.abstention_reason or "")


def test_insufficient_cropland_or_dimension_mismatch() -> None:
    """Test edge cases with no cropland pixels or dimension mismatches."""
    # 1. No cropland
    res_no_crop = evaluate_cropland_vegetation_condition(
        nir_band=[0.5, 0.5],
        red_band=[0.1, 0.1],
        cropland_mask=[0, 0],
        historical_ndvi_min=0.20,
        historical_ndvi_max=0.80,
    )
    assert res_no_crop.status == RemoteSensingStatus.INSUFFICIENT_CROPLAND
    assert res_no_crop.ndvi_mean is None

    # 2. Band dimension mismatch
    res_mismatch = evaluate_cropland_vegetation_condition(
        nir_band=[0.5, 0.5, 0.5],
        red_band=[0.1, 0.1],
        cropland_mask=[1, 1],
        historical_ndvi_min=0.20,
        historical_ndvi_max=0.80,
    )
    assert res_mismatch.status == RemoteSensingStatus.INVALID_BANDS
    assert res_mismatch.ndvi_mean is None


def test_missing_or_degenerate_historical_bounds_rejected() -> None:
    """C022-B: historical NDVI bounds are mandatory; no arbitrary defaults."""
    # 1. Bounds omitted entirely -> INVALID_HISTORICAL_RANGE
    res_no_bounds = evaluate_cropland_vegetation_condition(
        nir_band=[0.5, 0.4],
        red_band=[0.1, 0.1],
        cropland_mask=[1, 1],
    )
    assert res_no_bounds.status == RemoteSensingStatus.INVALID_HISTORICAL_RANGE
    assert res_no_bounds.ndvi_mean is None
    assert "Arbitrary default bounds prohibited" in (res_no_bounds.abstention_reason or "")

    # 2. Bounds too narrow (bandwidth < 0.01) -> INVALID_HISTORICAL_RANGE
    res_narrow = evaluate_cropland_vegetation_condition(
        nir_band=[0.5, 0.4],
        red_band=[0.1, 0.1],
        cropland_mask=[1, 1],
        historical_ndvi_min=0.50,
        historical_ndvi_max=0.502,
    )
    assert res_narrow.status == RemoteSensingStatus.INVALID_HISTORICAL_RANGE


def test_prohibited_production_tonnage_inference() -> None:
    """Ensure ADR-107 prohibition: inferring tonnage directly from NDVI raises ProhibitedYieldInferenceError."""
    with pytest.raises(ProhibitedYieldInferenceError) as exc_info:
        infer_production_tonnes_from_ndvi(ndvi=0.68, area_ha=5000.0)

    assert "strictly prohibited by ADR-107 and AGENTS.md" in str(exc_info.value)
