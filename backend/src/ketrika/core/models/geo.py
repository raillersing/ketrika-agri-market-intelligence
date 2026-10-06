"""Data models for geographic reference, locations, and crop calendars."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AdminLevel = Literal["admin0", "admin1", "admin2", "admin3", "market"]


class GeographicEntity(BaseModel):
    """Administrative or market spatial entity."""

    model_config = ConfigDict(extra="forbid")

    pcode: str = Field(..., description="Standardized OCHA P-Code (e.g. MDG, MDG11, MDG1101)")
    name_fr: str = Field(..., description="Canonical French denomination")
    name_mg: str | None = Field(default=None, description="Malagasy denomination")
    admin_level: AdminLevel = Field(..., description="Administrative division level")
    parent_pcode: str | None = Field(
        default=None, description="P-Code of parent administrative boundary"
    )
    latitude: float | None = Field(
        default=None, ge=-90.0, le=90.0, description="Centroid or point latitude"
    )
    longitude: float | None = Field(
        default=None, ge=-180.0, le=180.0, description="Centroid or point longitude"
    )


class LocationAlias(BaseModel):
    """Spelling variant or colloquial market/town denomination."""

    model_config = ConfigDict(extra="forbid")

    alias: str = Field(..., min_length=1, description="Raw label or colloquial designation")
    pcode: str = Field(..., description="Target standardized P-Code or market code")
    admin_level: AdminLevel = Field(..., description="Target administrative level")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Resolution reliability")
    note: str = Field(default="", description="Disambiguation rationale")


class CropCalendarEntry(BaseModel):
    """Agro-ecological seasonal crop calendar entry."""

    model_config = ConfigDict(extra="forbid")

    zone_code: str = Field(..., description="Agro-climatic zone code (e.g. ZONE_CENTRE, ZONE_EST)")
    zone_name: str = Field(..., description="Canonical zone description")
    crop: str = Field(..., description="Target crop (RICE, MAIZE)")
    crop_cycle: str = Field(..., description="Seasonal cycle name (asara, hosy, vakiambiaty)")
    planting_months: list[int] = Field(
        ..., min_length=1, description="Planting / sowing month integers (1-12)"
    )
    harvest_months: list[int] = Field(
        ..., min_length=1, description="Harvest month integers (1-12)"
    )
    source: str = Field(..., description="Documentary source (FAO GIEWS, FEWS NET, ODR)")
    verified: bool = Field(
        default=True, description="Whether verified against official publications"
    )
