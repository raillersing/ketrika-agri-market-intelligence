"""Agro-environmental remote sensing: SCL cloud masking, NDVI, and Cropland VCI (R4.8, ADR-107, SPECS §26).

This module implements:
1. Strict Copernicus Sentinel-2 SCL (Scene Classification Layer) cloud/shadow masking.
   Cloud and cloud-shadow pixels are converted to NaN/None, never treated as dead vegetation.
2. NDVI (Normalized Difference Vegetation Index) calculation on valid surface reflectance.
3. Cropland masking restricting analysis to verified agricultural parcels.
4. VCI (Vegetation Condition Index) calculation relative to multi-year historical bounds.
5. Strict abstention rule: if valid cropland pixels < 30% (cloud cover > 70%),
   returns 'cloud_obscured_unavailable' to avoid false drought alarms.
6. Absolute prohibition of inferring harvest tonnage directly from NDVI alone.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum, StrEnum


class ProhibitedYieldInferenceError(RuntimeError):
    """Raised when an attempt is made to infer production tonnage directly from NDVI (ADR-107 prohibition)."""


class Sentinel2SCLClass(IntEnum):
    """Copernicus Sentinel-2 Scene Classification Layer (SCL) categories."""

    NO_DATA = 0
    SATURATED_OR_DEFECTIVE = 1
    DARK_AREA_PIXELS = 2
    CLOUD_SHADOWS = 3
    VEGETATION = 4
    NOT_VEGETATED = 5
    WATER = 6
    UNCLASSIFIED = 7
    CLOUD_MEDIUM_PROBABILITY = 8
    CLOUD_HIGH_PROBABILITY = 9
    THIN_CIRRUS = 10
    SNOW = 11


# Classes that obscure ground vegetation and must be strictly masked out
CLOUD_AND_OBSCURATION_SCL: frozenset[int] = frozenset({
    Sentinel2SCLClass.NO_DATA,
    Sentinel2SCLClass.SATURATED_OR_DEFECTIVE,
    Sentinel2SCLClass.CLOUD_SHADOWS,
    Sentinel2SCLClass.CLOUD_MEDIUM_PROBABILITY,
    Sentinel2SCLClass.CLOUD_HIGH_PROBABILITY,
    Sentinel2SCLClass.THIN_CIRRUS,
})


class RemoteSensingStatus(StrEnum):
    """Status of remote sensing condition evaluation."""

    QUALIFIED = "qualified"
    CLOUD_OBSCURED_UNAVAILABLE = "cloud_obscured_unavailable"
    INSUFFICIENT_CROPLAND = "insufficient_cropland"
    INVALID_BANDS = "invalid_bands"


class VegetationConditionClass(StrEnum):
    """Agronomic qualification of Vegetation Condition Index (VCI)."""

    SEVERE_DROUGHT = "severe_drought"  # VCI < 20
    MODERATE_STRESS = "moderate_stress"  # 20 <= VCI < 35
    NORMAL = "normal"  # 35 <= VCI <= 60
    FAVORABLE = "favorable"  # 60 < VCI <= 80
    OPTIMAL = "optimal"  # VCI > 80
    UNAVAILABLE = "unavailable"  # Due to cloud cover or invalid data


@dataclass(frozen=True)
class CroplandVCIResult:
    """Rigorous evaluation of cropland vegetation condition adhering to ADR-107."""

    status: RemoteSensingStatus
    condition_class: VegetationConditionClass
    total_pixels: int
    cropland_pixels: int
    cloud_pixels: int
    valid_cropland_pixels: int
    valid_cropland_ratio: float
    ndvi_mean: float | None
    vci_mean: float | None
    abstention_reason: str | None
    source_asset: str
    stac_item_id: str | None


def compute_pixel_ndvi(
    nir: float,
    red: float,
    scl: int | None = None,
) -> float | None:
    """Compute Normalized Difference Vegetation Index for a single pixel.

    Returns None if:
    - scl indicates cloud, shadow, defective pixel, or no-data
    - reflectance values are unphysical or divisor <= 0
    """
    if scl is not None and scl in CLOUD_AND_OBSCURATION_SCL:
        return None

    if math.isnan(nir) or math.isnan(red):
        return None

    denom = nir + red
    if denom <= 1e-6:
        return None

    ndvi = (nir - red) / denom
    # Clamp to physical range [-1.0, 1.0]
    return max(-1.0, min(1.0, ndvi))


def compute_vci(
    ndvi: float | None,
    ndvi_min: float,
    ndvi_max: float,
) -> float | None:
    """Compute Vegetation Condition Index (VCI) from NDVI relative to historical range.

    VCI = 100 * (NDVI - NDVI_min) / (NDVI_max - NDVI_min)
    Bounded in [0.0, 100.0].
    """
    if ndvi is None:
        return None

    delta = ndvi_max - ndvi_min
    if delta <= 1e-5:
        return 50.0  # Neutral if historical range is flat

    raw_vci = 100.0 * (ndvi - ndvi_min) / delta
    return max(0.0, min(100.0, raw_vci))


def classify_vci(vci: float | None) -> VegetationConditionClass:
    """Map numeric VCI to standard agronomic condition classification."""
    if vci is None:
        return VegetationConditionClass.UNAVAILABLE

    if vci < 20.0:
        return VegetationConditionClass.SEVERE_DROUGHT
    elif vci < 35.0:
        return VegetationConditionClass.MODERATE_STRESS
    elif vci <= 60.0:
        return VegetationConditionClass.NORMAL
    elif vci <= 80.0:
        return VegetationConditionClass.FAVORABLE
    else:
        return VegetationConditionClass.OPTIMAL


def evaluate_cropland_vegetation_condition(
    nir_band: Sequence[float],
    red_band: Sequence[float],
    cropland_mask: Sequence[int],
    scl_band: Sequence[int] | None = None,
    historical_ndvi_min: float = 0.20,
    historical_ndvi_max: float = 0.85,
    min_valid_cropland_ratio: float = 0.30,
    source_asset: str = "sentinel2_l2a_copernicus",
    stac_item_id: str | None = None,
) -> CroplandVCIResult:
    """Evaluate cropland vegetation condition over an array of pixels.

    Enforces ADR-107:
    - Excludes non-cropland pixels (cropland_mask == 0).
    - Excludes cloud and cloud-shadow pixels via SCL mask.
    - If valid cropland pixels < min_valid_cropland_ratio (default 30%, i.e. > 70% cloud cover),
      strictly returns 'cloud_obscured_unavailable'.
    """
    n_pixels = len(nir_band)
    if len(red_band) != n_pixels or len(cropland_mask) != n_pixels:
        return CroplandVCIResult(
            status=RemoteSensingStatus.INVALID_BANDS,
            condition_class=VegetationConditionClass.UNAVAILABLE,
            total_pixels=n_pixels,
            cropland_pixels=0,
            cloud_pixels=0,
            valid_cropland_pixels=0,
            valid_cropland_ratio=0.0,
            ndvi_mean=None,
            vci_mean=None,
            abstention_reason="Array dimension mismatch between NIR, RED, and cropland mask",
            source_asset=source_asset,
            stac_item_id=stac_item_id,
        )

    if scl_band is not None and len(scl_band) != n_pixels:
        return CroplandVCIResult(
            status=RemoteSensingStatus.INVALID_BANDS,
            condition_class=VegetationConditionClass.UNAVAILABLE,
            total_pixels=n_pixels,
            cropland_pixels=0,
            cloud_pixels=0,
            valid_cropland_pixels=0,
            valid_cropland_ratio=0.0,
            ndvi_mean=None,
            vci_mean=None,
            abstention_reason="Array dimension mismatch between bands and SCL mask",
            source_asset=source_asset,
            stac_item_id=stac_item_id,
        )

    cropland_count = 0
    cloud_count = 0
    valid_ndvi_cropland: list[float] = []

    for i in range(n_pixels):
        is_crop = cropland_mask[i] == 1
        scl = scl_band[i] if scl_band is not None else None

        is_cloud = scl is not None and scl in CLOUD_AND_OBSCURATION_SCL
        if is_cloud:
            cloud_count += 1

        if not is_crop:
            continue

        cropland_count += 1
        if is_cloud:
            continue

        ndvi = compute_pixel_ndvi(nir_band[i], red_band[i], scl=scl)
        if ndvi is not None:
            valid_ndvi_cropland.append(ndvi)

    if cropland_count == 0:
        return CroplandVCIResult(
            status=RemoteSensingStatus.INSUFFICIENT_CROPLAND,
            condition_class=VegetationConditionClass.UNAVAILABLE,
            total_pixels=n_pixels,
            cropland_pixels=0,
            cloud_pixels=cloud_count,
            valid_cropland_pixels=0,
            valid_cropland_ratio=0.0,
            ndvi_mean=None,
            vci_mean=None,
            abstention_reason="No pixels fall within the designated cropland mask",
            source_asset=source_asset,
            stac_item_id=stac_item_id,
        )

    valid_cropland_ratio = len(valid_ndvi_cropland) / cropland_count

    # Strict Abstention: Cloud cover > 70% (valid cropland pixels < 30%)
    if valid_cropland_ratio < min_valid_cropland_ratio:
        cloud_pct = round((1.0 - valid_cropland_ratio) * 100.0, 1)
        return CroplandVCIResult(
            status=RemoteSensingStatus.CLOUD_OBSCURED_UNAVAILABLE,
            condition_class=VegetationConditionClass.UNAVAILABLE,
            total_pixels=n_pixels,
            cropland_pixels=cropland_count,
            cloud_pixels=cloud_count,
            valid_cropland_pixels=len(valid_ndvi_cropland),
            valid_cropland_ratio=round(valid_cropland_ratio, 3),
            ndvi_mean=None,
            vci_mean=None,
            abstention_reason=(
                f"Cloud cover exceeds 70% on cropland ({cloud_pct}% obscured, "
                f"valid pixels ratio {valid_cropland_ratio:.2f} < {min_valid_cropland_ratio:.2f}). "
                "Explicit abstention to prevent false drought or crop failure alarms (ADR-107)."
            ),
            source_asset=source_asset,
            stac_item_id=stac_item_id,
        )

    mean_ndvi = sum(valid_ndvi_cropland) / len(valid_ndvi_cropland)
    mean_vci = compute_vci(mean_ndvi, historical_ndvi_min, historical_ndvi_max)
    condition_class = classify_vci(mean_vci)

    return CroplandVCIResult(
        status=RemoteSensingStatus.QUALIFIED,
        condition_class=condition_class,
        total_pixels=n_pixels,
        cropland_pixels=cropland_count,
        cloud_pixels=cloud_count,
        valid_cropland_pixels=len(valid_ndvi_cropland),
        valid_cropland_ratio=round(valid_cropland_ratio, 3),
        ndvi_mean=round(mean_ndvi, 3),
        vci_mean=round(mean_vci, 1) if mean_vci is not None else None,
        abstention_reason=None,
        source_asset=source_asset,
        stac_item_id=stac_item_id,
    )


def infer_production_tonnes_from_ndvi(ndvi: float, area_ha: float) -> None:
    """Strictly prohibited method per ADR-107.

    Harvest tonnage CANNOT be derived from NDVI alone.
    Always raises ProhibitedYieldInferenceError.
    """
    raise ProhibitedYieldInferenceError(
        "Direct inference of harvest tonnage from NDVI alone is strictly prohibited by ADR-107 and AGENTS.md. "
        "Production must be evaluated through the agronomic Area × Yield model (R5.5) with verified ground baselines."
    )
