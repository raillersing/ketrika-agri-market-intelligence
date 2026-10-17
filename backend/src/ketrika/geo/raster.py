"""Raster processing, clipping and zonal aggregation utilities (ADR-080, SPECS §26, R4.1)."""

import math
from typing import NamedTuple

from ketrika.geo.contracts import (
    BBOX_MADAGASCAR,
    AggregationMethod,
)


class ZonalAggregationResult(NamedTuple):
    """Result of zonal aggregation over a geographical unit."""

    value: float | None
    effective_method: AggregationMethod
    valid_cell_count: int
    coverage_ratio: float
    is_fallback: bool
    fallback_reason: str | None = None


def is_within_madagascar_bbox(lon: float, lat: float) -> bool:
    """Check if point coordinates fall within the official Madagascar bounding box."""
    min_lon, min_lat, max_lon, max_lat = BBOX_MADAGASCAR
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def validate_bbox(bbox: tuple[float, float, float, float]) -> bool:
    """Validate that a 4-tuple is a valid geographic bounding box [min_lon, min_lat, max_lon, max_lat]."""
    if len(bbox) != 4:
        return False
    min_lon, min_lat, max_lon, max_lat = bbox
    if not (-180.0 <= min_lon <= 180.0 and -180.0 <= max_lon <= 180.0):
        return False
    if not (-90.0 <= min_lat <= 90.0 and -90.0 <= max_lat <= 90.0):
        return False
    if min_lon >= max_lon or min_lat >= max_lat:
        return False
    return True


def clip_raster_bbox(
    source_bbox: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Clip a source bounding box to the Madagascar bounding box to prevent oversized ingestion."""
    if not validate_bbox(source_bbox):
        raise ValueError(f"Invalid bounding box: {source_bbox}")

    s_min_lon, s_min_lat, s_max_lon, s_max_lat = source_bbox
    m_min_lon, m_min_lat, m_max_lon, m_max_lat = BBOX_MADAGASCAR

    c_min_lon = max(s_min_lon, m_min_lon)
    c_min_lat = max(s_min_lat, m_min_lat)
    c_max_lon = min(s_max_lon, m_max_lon)
    c_max_lat = min(s_max_lat, m_max_lat)

    if c_min_lon >= c_max_lon or c_min_lat >= c_max_lat:
        raise ValueError("Source bounding box does not intersect Madagascar bounding box")

    return (c_min_lon, c_min_lat, c_max_lon, c_max_lat)


def aggregate_zonal(
    values: list[float],
    weights: list[float] | None = None,
    method: AggregationMethod = AggregationMethod.ZONAL_MEAN,
    cropland_mask_available: bool = False,
    nodata_value: float = -9999.0,
) -> ZonalAggregationResult:
    """Perform zonal aggregation with strict adherence to ADR-080 veracity rules.

    If cropland_weighted_mean is requested without a verified cropland_mask,
    the method strictly falls back to zonal_mean to prevent false agronomic precision.
    """
    total_cells = len(values)
    if total_cells == 0:
        return ZonalAggregationResult(
            value=None,
            effective_method=method,
            valid_cell_count=0,
            coverage_ratio=0.0,
            is_fallback=False,
        )

    # Filter out nodata and non-finite values
    valid_pairs: list[tuple[float, float]] = []
    for idx, val in enumerate(values):
        if math.isnan(val) or math.isinf(val) or val == nodata_value:
            continue
        weight = 1.0
        if weights is not None and idx < len(weights):
            w = weights[idx]
            if not math.isnan(w) and not math.isinf(w) and w >= 0.0:
                weight = w
        valid_pairs.append((val, weight))

    valid_count = len(valid_pairs)
    coverage_ratio = valid_count / total_cells if total_cells > 0 else 0.0

    if valid_count == 0:
        return ZonalAggregationResult(
            value=None,
            effective_method=method,
            valid_cell_count=0,
            coverage_ratio=0.0,
            is_fallback=False,
        )

    # Enforce ADR-080: cropland_weighted_mean requires verified mask
    effective_method = method
    is_fallback = False
    fallback_reason: str | None = None

    if method == AggregationMethod.CROPLAND_WEIGHTED_MEAN:
        if not cropland_mask_available:
            effective_method = AggregationMethod.ZONAL_MEAN
            is_fallback = True
            fallback_reason = "cropland_mask_unavailable_strict_fallback_to_zonal_mean"

    if effective_method == AggregationMethod.CROPLAND_WEIGHTED_MEAN and weights is not None:
        total_weight = sum(w for _, w in valid_pairs)
        if total_weight > 0.0:
            weighted_val = sum(v * w for v, w in valid_pairs) / total_weight
            return ZonalAggregationResult(
                value=round(weighted_val, 4),
                effective_method=AggregationMethod.CROPLAND_WEIGHTED_MEAN,
                valid_cell_count=valid_count,
                coverage_ratio=round(coverage_ratio, 4),
                is_fallback=False,
            )
        # If total weight is zero, fallback to simple mean
        effective_method = AggregationMethod.ZONAL_MEAN
        is_fallback = True
        fallback_reason = "zero_cropland_weights_fallback_to_zonal_mean"

    # Default: zonal mean (unweighted mean of valid cells)
    simple_mean = sum(v for v, _ in valid_pairs) / valid_count
    return ZonalAggregationResult(
        value=round(simple_mean, 4),
        effective_method=effective_method,
        valid_cell_count=valid_count,
        coverage_ratio=round(coverage_ratio, 4),
        is_fallback=is_fallback,
        fallback_reason=fallback_reason,
    )


def compute_dry_spells(precip_daily: list[float], threshold_mm: float = 1.0) -> list[int]:
    """Compute the duration (in days) of dry spells where precipitation < threshold_mm."""
    spells: list[int] = []
    current_spell = 0

    for p in precip_daily:
        if math.isnan(p) or p < threshold_mm:
            current_spell += 1
        else:
            if current_spell > 0:
                spells.append(current_spell)
                current_spell = 0

    if current_spell > 0:
        spells.append(current_spell)

    return spells
