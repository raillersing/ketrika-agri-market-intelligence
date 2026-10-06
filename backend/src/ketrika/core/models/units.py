"""Data models for measurement units and conversion factors."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UnitKind = Literal["mass", "volume", "package", "local", "count"]
ConversionStatus = Literal["exact", "confident", "uncertain"]


class ProductConversion(BaseModel):
    """Specific conversion factor for a given product and local unit."""

    model_config = ConfigDict(extra="forbid")

    factor: float = Field(..., gt=0.0, description="Multiplier to reach standard base unit")
    target_unit: str = Field(default="kg", description="Target base unit (kg or l)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Conversion confidence (0.0 to 1.0)")
    evidence: str = Field(default="", description="Documentary source or measurement reference")
    verified: bool = Field(default=False, description="Whether empirically verified")


class UnitDefinition(BaseModel):
    """Unit definition conforming to SPECS §7."""

    model_config = ConfigDict(extra="forbid")

    unit_code: str = Field(
        ..., min_length=1, description="Unique unit identifier (e.g. kg, t, kapoaka)"
    )
    name_fr: str = Field(..., description="French designation")
    kind: UnitKind = Field(..., description="Physical or commercial kind")
    target_unit: str | None = Field(
        default=None, description="Standard base unit (kg or l) if generic"
    )
    factor: float | None = Field(
        default=None, gt=0.0, description="Generic multiplier to target_unit"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Generic conversion reliability"
    )
    evidence: str = Field(default="", description="Documentary source or measurement study")
    product_specific: dict[str, ProductConversion] = Field(
        default_factory=dict, description="Product-specific conversion overrides"
    )
    notes: str = Field(default="", description="Usage caveats or packaging context")
