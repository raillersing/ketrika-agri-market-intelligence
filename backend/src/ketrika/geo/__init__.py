"""Geospatial, agroclimate and crop calendar package for Ketrika (ADR-080, SPECS §26, R4.1)."""

from ketrika.geo.contracts import (
    BBOX_MADAGASCAR,
    CRS_WGS84,
    MAX_RASTER_FILE_SIZE_BYTES,
    AggregationMethod,
    CropCalendarRecord,
    CropRegime,
    GeoBoundingBox,
    RasterMetadata,
    SpatialResolution,
    WeatherForecastRecord,
    WeatherStage,
    WeatherVariable,
    load_crop_calendar,
)
from ketrika.geo.raster import (
    aggregate_zonal,
    compute_dry_spells,
    is_within_madagascar_bbox,
    validate_bbox,
)

__all__ = [
    "CRS_WGS84",
    "BBOX_MADAGASCAR",
    "MAX_RASTER_FILE_SIZE_BYTES",
    "AggregationMethod",
    "WeatherStage",
    "WeatherVariable",
    "SpatialResolution",
    "CropRegime",
    "GeoBoundingBox",
    "WeatherForecastRecord",
    "CropCalendarRecord",
    "RasterMetadata",
    "load_crop_calendar",
    "is_within_madagascar_bbox",
    "validate_bbox",
    "aggregate_zonal",
    "compute_dry_spells",
]
