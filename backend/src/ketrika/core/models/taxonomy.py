"""Taxonomy models for agricultural products, aliases and varieties."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProductCategory = Literal[
    "cereal",
    "root_tuber",
    "pulse",
    "pulse_oilseed",
    "oil",
    "sugar",
    "flour",
]

LanguageCode = Literal["fr", "mg", "en"]


class ProductDefinition(BaseModel):
    """Canonical commodity specification conforming to SPECS §6.1."""

    model_config = ConfigDict(extra="forbid")

    product_code: str = Field(
        ..., pattern=r"^[A-Z0-9_]+$", description="Canonical uppercase identifier"
    )
    canonical_name_fr: str = Field(..., description="Official French designation")
    category: ProductCategory = Field(..., description="Food balance category")
    base_unit: str = Field(..., description="Normalized standard unit (e.g. kg, l)")
    hs6_codes: list[str] = Field(
        default_factory=list, description="Harmonized System 6-digit classification codes"
    )
    faostat_item_codes: list[int] = Field(
        default_factory=list, description="FAOSTAT item identifiers"
    )
    verified: bool = Field(
        default=False, description="Whether HS and FAOSTAT cross-references are verified"
    )
    notes: str = Field(default="", description="Botanical, culinary or commercial notes")


class ProductAlias(BaseModel):
    """Commodity synonym, dialect or raw label mapping conforming to SPECS §6.2."""

    model_config = ConfigDict(extra="forbid")

    alias: str = Field(..., min_length=1, description="Raw label or colloquial designation")
    lang: LanguageCode = Field(default="fr", description="Language of alias (fr, mg, en)")
    product_code: str = Field(
        ..., pattern=r"^[A-Z0-9_]+$", description="Mapped canonical product code"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Mapping reliability confidence (0.0 to 1.0)"
    )
    note: str = Field(default="", description="Disambiguation or context warning")
    evidence: str = Field(default="", description="Documentary or statistical source proof")


class RiceVariety(BaseModel):
    """Rice botanical or commercial variety attribute (non-product) from ODR."""

    model_config = ConfigDict(extra="forbid")

    variety_code: str = Field(
        ..., pattern=r"^[A-Z0-9_]+$", description="Uppercase variety identifier"
    )
    name: str = Field(..., description="Local name (e.g. Makalioka, Vary mena, Tsipala)")
    rice_type: Literal["local", "imported", "paddy"] = Field(
        default="local", description="Broad rice segment"
    )
    grain_type: Literal["long", "round", "medium", "unknown"] = Field(
        default="unknown", description="Grain morphology"
    )
    notes: str = Field(default="", description="Agronomic and regional characteristics")
