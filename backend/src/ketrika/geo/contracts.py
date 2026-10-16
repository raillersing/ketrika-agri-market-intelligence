"""Geospatial and agroclimatic contracts, enums and schemas (ADR-080, SPECS §26, R4.1)."""

import uuid
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ketrika.core.registry import find_repo_root

# Standard reference coordinate system and bounds
CRS_WGS84: str = "EPSG:4326"

# Madagascar bounding box: [min_lon, min_lat, max_lon, max_lat]
BBOX_MADAGASCAR: tuple[float, float, float, float] = (43.0, -25.8, 50.8, -11.8)

# Maximum monthly Bronze raster storage budget (50 MB)
MAX_RASTER_FILE_SIZE_BYTES: int = 50 * 1024 * 1024


class AggregationMethod(StrEnum):
    """Zonal aggregation method for converting gridded rasters to admin boundaries."""

    POINT_CENTROID = "point_centroid"
    ZONAL_MEAN = "zonal_mean"
    CROPLAND_WEIGHTED_MEAN = "cropland_weighted_mean"


class WeatherStage(StrEnum):
    """Temporal lifecycle stage of weather observations (C2/C4 double-versioning)."""

    PRELIMINARY = "preliminary"
    FINAL = "final"


class WeatherVariable(StrEnum):
    """Canonical agro-climatic and weather variables."""

    PRECIP_MM = "precip_mm"
    T2M_C = "t2m_c"
    T2M_MAX_C = "t2m_max_c"
    T2M_MIN_C = "t2m_min_c"
    RH2M_PCT = "rh2m_pct"
    WIND_SPEED_MS = "wind_speed_ms"


class SpatialResolution(StrEnum):
    """Native gridded spatial resolution."""

    CHIRPS_005 = "0.05_deg"
    ERA5_010 = "0.1_deg"
    NASA_POWER_050 = "0.5_deg"


class CropRegime(StrEnum):
    """Agricultural water regime for cropping cycles in Madagascar."""

    RAINFED = "rainfed"
    IRRIGATED = "irrigated"
    LOWLAND = "lowland"


class CalendarType(StrEnum):
    """Typology of crop calendars (traditional baseline vs seasonal recommendation)."""

    TRADITIONAL_BASELINE = "traditional_baseline"
    SEASONAL_RECOMMENDATION = "seasonal_recommendation"


class MarketLinkProofStatus(StrEnum):
    """Verification proof status for trade corridors connecting production basin to markets."""

    DOCUMENTED_TRADE_CORRIDOR = "documented_trade_corridor"
    OFFICIAL_SUPPLY_BASIN = "official_supply_basin"
    UNVERIFIED_ASSUMPTION = "unverified_assumption"


class MarketLink(BaseModel):
    """Documented trade flow connection between a production basin and a consumer market."""

    location_code: str
    location_name: str
    flow_role: str = "primary_supply"  # primary_supply | secondary_supply
    proof_status: MarketLinkProofStatus = MarketLinkProofStatus.DOCUMENTED_TRADE_CORRIDOR
    source_evidence: str


class AgroClimateRiskLevel(StrEnum):
    """Categorical risk level for agro-climatic anomalies and shocks."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ClimateAnomalyMethod(StrEnum):
    """Method used for climate anomaly computation."""

    PERCENT_OF_NORMAL = "percent_of_normal"
    ABSOLUTE_DELTA = "absolute_delta"
    STANDARDIZED_ZSCORE = "standardized_zscore"


class GeoBoundingBox(BaseModel):
    """Geographical bounding box in EPSG:4326 coordinates."""

    min_lon: float = Field(..., ge=-180.0, le=180.0)
    min_lat: float = Field(..., ge=-90.0, le=90.0)
    max_lon: float = Field(..., ge=-180.0, le=180.0)
    max_lat: float = Field(..., ge=-90.0, le=90.0)

    @field_validator("max_lon")
    @classmethod
    def validate_longitude_order(cls, v: float, info: Any) -> float:
        min_lon = info.data.get("min_lon")
        if min_lon is not None and v <= min_lon:
            raise ValueError(f"max_lon ({v}) must be greater than min_lon ({min_lon})")
        return v

    @field_validator("max_lat")
    @classmethod
    def validate_latitude_order(cls, v: float, info: Any) -> float:
        min_lat = info.data.get("min_lat")
        if min_lat is not None and v <= min_lat:
            raise ValueError(f"max_lat ({v}) must be greater than min_lat ({min_lat})")
        return v

    def intersects_madagascar(self) -> bool:
        """Check if this bounding box intersects Madagascar territory."""
        mdg_min_lon, mdg_min_lat, mdg_max_lon, mdg_max_lat = BBOX_MADAGASCAR
        return not (
            self.max_lon < mdg_min_lon
            or self.min_lon > mdg_max_lon
            or self.max_lat < mdg_min_lat
            or self.min_lat > mdg_max_lat
        )


class WeatherForecastRecord(BaseModel):
    """Contract for numerical weather forecasts (strictly separated from observations)."""

    source_record_id: uuid.UUID
    location_id: uuid.UUID
    issued_at: datetime
    valid_from: datetime
    valid_to: datetime
    horizon_hours: int = Field(..., ge=0)
    variable: WeatherVariable
    model_name: str
    predicted_value: float | None = None
    predicted_p10: float | None = None
    predicted_p90: float | None = None
    method: AggregationMethod
    spatial_resolution: SpatialResolution | str | None = None
    unit: str
    evidence: dict[str, Any] | None = None
    raw_payload: dict[str, Any] | None = None

    @field_validator("valid_to")
    @classmethod
    def validate_validity_window(cls, v: datetime, info: Any) -> datetime:
        valid_from = info.data.get("valid_from")
        if valid_from is not None and v < valid_from:
            raise ValueError(f"valid_to ({v}) cannot be earlier than valid_from ({valid_from})")
        return v

    @field_validator("predicted_p90")
    @classmethod
    def validate_quantiles(cls, v: float | None, info: Any) -> float | None:
        p10 = info.data.get("predicted_p10")
        if p10 is not None and v is not None and v < p10:
            raise ValueError(f"predicted_p90 ({v}) cannot be less than predicted_p10 ({p10})")
        return v


class CropCalendarRecord(BaseModel):
    """Crop calendar cycle specification for Madagascar commodities (ADR-086, SPECS §26)."""

    model_config = ConfigDict(extra="forbid")

    zone_code: str
    zone_name: str
    crop: str
    product_code: str
    crop_cycle: str | None = None
    season_name: str
    crop_regime: CropRegime
    calendar_version: str = "v1.0"
    calendar_type: CalendarType = CalendarType.TRADITIONAL_BASELINE
    campaign: str = "baseline_permanent"
    variety: str | None = None
    planting_months: list[int] = Field(default_factory=list)
    planting_start_month: int = Field(..., ge=1, le=12)
    planting_end_month: int = Field(..., ge=1, le=12)
    growing_start_month: int = Field(..., ge=1, le=12)
    growing_end_month: int = Field(..., ge=1, le=12)
    harvest_months: list[int] = Field(default_factory=list)
    harvest_start_month: int = Field(..., ge=1, le=12)
    harvest_end_month: int = Field(..., ge=1, le=12)
    peak_harvest_month: int | None = Field(None, ge=1, le=12)
    water_sensitivity_profile: dict[str, str] = Field(default_factory=dict)
    source: str | None = None
    source_reference: str
    verified: bool = True
    eligible_for_alerts: bool = True
    is_active: bool = True
    superseded_by: uuid.UUID | None = None
    market_links: list[MarketLink] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_crop_calendar_integrity(self) -> "CropCalendarRecord":
        # Disallow invented tonnage or price projections
        for prohibited in ("tonnage", "yield_projection", "price_forecast", "market_price_peak"):
            if hasattr(self, prohibited):
                raise ValueError(f"Crop calendar cannot contain economic projection field '{prohibited}' (ADR-086)")

        # Entries without authentic source or marked unverified cannot be eligible for alerts
        if not self.verified or not self.source_reference.strip():
            self.eligible_for_alerts = False

        # Populate month lists if empty
        if not self.planting_months:
            if self.planting_start_month <= self.planting_end_month:
                self.planting_months = list(range(self.planting_start_month, self.planting_end_month + 1))
            else:
                self.planting_months = list(range(self.planting_start_month, 13)) + list(
                    range(1, self.planting_end_month + 1)
                )

        if not self.harvest_months:
            if self.harvest_start_month <= self.harvest_end_month:
                self.harvest_months = list(range(self.harvest_start_month, self.harvest_end_month + 1))
            else:
                self.harvest_months = list(range(self.harvest_start_month, 13)) + list(
                    range(1, self.harvest_end_month + 1)
                )

        return self


class RasterMetadata(BaseModel):
    """Metadata descriptor for Bronze raster objects."""

    source_id: str
    variable: WeatherVariable
    stage: WeatherStage
    period_start: datetime
    period_end: datetime
    crs: str = CRS_WGS84
    spatial_resolution: SpatialResolution
    bbox: GeoBoundingBox
    file_size_bytes: int = Field(..., le=MAX_RASTER_FILE_SIZE_BYTES)
    is_clipped: bool = True
    sha256: str


def load_crop_calendar(file_path: Path | str | None = None) -> list[CropCalendarRecord]:
    """Load and validate the crop calendar taxonomy."""
    if file_path is None:
        file_path = find_repo_root() / "taxonomy" / "crop_calendar.yaml"
    else:
        file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Crop calendar taxonomy not found at {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        raw_items = yaml.safe_load(f)

    if not isinstance(raw_items, list):
        raise ValueError(f"Expected a list of calendar entries in {file_path}")

    records: list[CropCalendarRecord] = []
    for item in raw_items:
        records.append(CropCalendarRecord(**item))
    return records
