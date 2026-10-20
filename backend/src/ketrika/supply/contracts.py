"""Supply, arrival flows, stock inventories and harvest volume contracts (SPECS §27, ADR-088, R5.1)."""

from __future__ import annotations

import re
import uuid
from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class QuantityTarget(StrEnum):
    """Metrological distinction between physical supply targets to prevent double-counting."""

    HARVEST_VOLUME = "harvest_volume"  # Primary agricultural harvest in production basins
    INFLOW_ARRIVAL = "inflow_arrival"  # Logistic incoming physical arrival flow on market
    STOCK_INVENTORY = "stock_inventory"  # Static stock inventory level at a given point in time
    OUTFLOW_SALES = "outflow_sales"  # Outgoing physical sales from market or depot


class QuantityMeasurementMode(StrEnum):
    """Observation provenance mode for physical quantity survey."""

    MEASURED_SCALE = "measured_scale"  # Direct measurement on calibrated scale / weighbridge
    DECLARED_TRADER = "declared_trader"  # Oral or written declaration by trader / transporter
    ESTIMATED_SURVEY = "estimated_survey"  # Surveyor visual estimation via container counting


class QuantityUnit(StrEnum):
    """Standardized and local physical measurement units."""

    KG = "kg"  # Metric kilogram (pivot = 1.0)
    TONNE = "tonne"  # Metric tonne (pivot = 1000.0)
    BAG_50KG = "bag_50kg"  # Standardized 50 kg polypropylene bag
    BAG_100KG = "bag_100kg"  # Standardized 100 kg jute bag
    GONY = "gony"  # Malagasy traditional bag (nominal 50kg for rice, 45kg maize)
    KAPOAKA = "kapoaka"  # Standard condensed milk can (300 ml, mass depends on commodity)


class MarketType(StrEnum):
    """Functional role of market in the supply corridor."""

    PRIMARY_COLLECTION = "primary_collection"  # Rural collector market in production basin
    REGIONAL_WHOLESALE = "regional_wholesale"  # Inter-regional wholesale transshipment hub
    TERMINAL_URBAN = "terminal_urban"  # Urban consumption terminal market (e.g. Anosibe)
    RETAIL_LOCAL = "retail_local"  # Neighbourhood retail point


# Forbidden personal data field names (AGENTS.md §8.3 strict ban on PII)
FORBIDDEN_PII_FIELDS: frozenset[str] = frozenset(
    {
        "trader_name",
        "name",
        "first_name",
        "last_name",
        "phone",
        "telephone",
        "tel",
        "mobile",
        "email",
        "mail",
        "driver_name",
        "driver_id",
        "driver_phone",
        "vehicle_plate",
        "plate_number",
        "immatriculation",
        "national_id",
        "cin",
        "passport",
        "nif",
        "stat",
        "address",
        "home_address",
        "contact_person",
    }
)

# Product mass density conversion factors for traditional non-metric units (kg per unit)
UNIT_CONVERSION_TABLE: dict[tuple[QuantityUnit, str], float] = {
    # KG
    (QuantityUnit.KG, "*"): 1.0,
    # TONNE
    (QuantityUnit.TONNE, "*"): 1000.0,
    # BAG 50KG
    (QuantityUnit.BAG_50KG, "*"): 50.0,
    # BAG 100KG
    (QuantityUnit.BAG_100KG, "*"): 100.0,
    # GONY (Malagasy bag)
    (QuantityUnit.GONY, "RICE_PADDY"): 48.0,
    (QuantityUnit.GONY, "RICE_MILLED"): 50.0,
    (QuantityUnit.GONY, "rice_vary_gasy"): 50.0,
    (QuantityUnit.GONY, "rice_tsipala"): 50.0,
    (QuantityUnit.GONY, "rice_makalioka"): 50.0,
    (QuantityUnit.GONY, "MAIZE_GRAIN"): 45.0,
    (QuantityUnit.GONY, "maize"): 45.0,
    (QuantityUnit.GONY, "CASSAVA_FRESH"): 50.0,
    (QuantityUnit.GONY, "cassava"): 50.0,
    (QuantityUnit.GONY, "*"): 50.0,  # Fallback default
    # KAPOAKA (300 ml can)
    (QuantityUnit.KAPOAKA, "RICE_PADDY"): 0.28,
    (QuantityUnit.KAPOAKA, "RICE_MILLED"): 0.26,
    (QuantityUnit.KAPOAKA, "rice_vary_gasy"): 0.26,
    (QuantityUnit.KAPOAKA, "rice_tsipala"): 0.26,
    (QuantityUnit.KAPOAKA, "rice_makalioka"): 0.26,
    (QuantityUnit.KAPOAKA, "MAIZE_GRAIN"): 0.24,
    (QuantityUnit.KAPOAKA, "maize"): 0.24,
    (QuantityUnit.KAPOAKA, "SUGAR_REFINED"): 0.25,
    (QuantityUnit.KAPOAKA, "sugar"): 0.25,
    (QuantityUnit.KAPOAKA, "*"): 0.25,  # Fallback default
}


def convert_quantity_to_kg(
    quantity_raw: float, unit: QuantityUnit, product_code: str = "*"
) -> float:
    """Convert raw quantity in specified unit to standard metric kilograms."""
    if quantity_raw <= 0:
        raise ValueError(f"Quantity must be strictly positive, got {quantity_raw}")

    # Lookup specific (unit, product_code)
    prod_key = product_code.strip()
    factor = UNIT_CONVERSION_TABLE.get((unit, prod_key))
    if factor is None:
        factor = UNIT_CONVERSION_TABLE.get((unit, "*"))

    if factor is None:
        raise ValueError(f"Unknown conversion factor for unit {unit} and product {product_code}")

    return round(quantity_raw * factor, 3)


def validate_payload_no_pii(payload: dict[str, Any]) -> None:
    """Inspect dictionary keys and raise ValueError if any forbidden PII field is present."""
    for key in payload:
        low_key = key.lower().replace("-", "_")
        if low_key in FORBIDDEN_PII_FIELDS:
            raise ValueError(
                f"Forbidden PII field detected in payload: '{key}'. PII is strictly prohibited."
            )
        # Sub-string match for sensitive identifiers
        if any(
            term in low_key for term in ("phone", "email", "trader_name", "driver_", "plate_number")
        ):
            raise ValueError(f"Forbidden PII keyword pattern detected in field: '{key}'.")


class SurveyMetadata(BaseModel):
    """Institutional survey protocol metadata (anonymized, zero personal data)."""

    model_config = ConfigDict(extra="forbid")

    protocol_code: str = "KETRIKA_SUPPLY_PILOT_v1.0"
    surveyor_identifier: str = Field(
        ..., description="Role-based anonymous surveyor ID (e.g. 'ENQ_01')"
    )
    institution_partner: str = Field(
        "Observatoire du Riz / Direction Régionale MinAE", description="Originating entity"
    )
    sampling_frame: str = Field(
        ..., description="Sampling method: census, systematic_sample, purposive_hub"
    )

    @field_validator("surveyor_identifier")
    @classmethod
    def validate_anonymous_surveyor(cls, v: str) -> str:
        # Surveyor identifier must be an anonymous code, never a human name
        if re.search(
            r"\b(monsieur|madame|m\.|mme|jean|pierre|rakoto|rasoa|randria)\b", v, re.IGNORECASE
        ):
            raise ValueError(
                f"Surveyor identifier '{v}' appears to contain a personal name. Use anonymous codes like 'ENQ_01'."
            )
        return v


class QuantityObservationRecord(BaseModel):
    """Physical quantity observation on markets or production basins (SPECS §27, ADR-088)."""

    model_config = ConfigDict(extra="forbid")

    observation_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source_record_id: uuid.UUID | None = None
    target: QuantityTarget
    product_code: str = Field(..., description="Canonical product code (e.g. 'rice_vary_gasy')")
    product_name: str
    market_code: str = Field(..., description="Public market code (e.g. 'MKT_ANOSIBE')")
    market_name: str
    location_pcode: str = Field(..., description="Admin location P-code (e.g. 'MDG11')")
    observed_date: date
    period_start: date | None = None
    period_end: date | None = None
    quantity_raw: float = Field(..., gt=0, description="Raw quantity observed or declared")
    unit_raw: QuantityUnit
    quantity_kg: float = Field(..., gt=0, description="Converted quantity in standard metric kg")
    measurement_mode: QuantityMeasurementMode
    market_type: MarketType
    survey_metadata: SurveyMetadata | None = None
    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def validate_no_pii_in_notes(cls, v: str | None) -> str | None:
        if v is None:
            return None
        # Check for phone numbers
        if re.search(r"(\+?261|03[23489])[\s.-]?\d{2}[\s.-]?\d{3}[\s.-]?\d{2}", v):
            raise ValueError("Forbidden phone number pattern detected in notes text.")
        # Check for emails
        if re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", v):
            raise ValueError("Forbidden email address detected in notes text.")
        return v

    @model_validator(mode="after")
    def validate_quantity_integrity(self) -> QuantityObservationRecord:
        # 1. Flow targets require period definition
        if self.target == QuantityTarget.INFLOW_ARRIVAL:
            if self.period_start is not None and self.period_end is not None:
                if self.period_start > self.period_end:
                    raise ValueError(
                        f"period_start ({self.period_start}) cannot be later than period_end ({self.period_end})"
                    )
        # 2. Stock inventory requires point-in-time observed_date
        if self.target == QuantityTarget.STOCK_INVENTORY:
            if (
                self.period_start is not None
                and self.period_end is not None
                and self.period_start != self.period_end
            ):
                raise ValueError(
                    "Stock inventory is a point-in-time stock measure and cannot span a multi-day period."
                )
        return self


def validate_no_double_counting(records: list[QuantityObservationRecord]) -> list[str]:
    """Inspect a set of quantity observations and identify illegal cross-target additions or temporal overlaps.

    Returns:
        List of warning/violation messages. Empty list means clean dataset.
    """
    violations: list[str] = []
    targets_present = {r.target for r in records}

    # Violation 1: Mixing flow (arrival) and static stock in cumulative sum
    if (
        QuantityTarget.INFLOW_ARRIVAL in targets_present
        and QuantityTarget.STOCK_INVENTORY in targets_present
    ):
        violations.append(
            "DOUBLE_COUNTING_RISK: Dataset contains both INFLOW_ARRIVAL (flow) and STOCK_INVENTORY (state). "
            "They must NEVER be summed together."
        )

    # Violation 2: Mixing harvest volume (production) and market arrivals
    if (
        QuantityTarget.HARVEST_VOLUME in targets_present
        and QuantityTarget.INFLOW_ARRIVAL in targets_present
    ):
        violations.append(
            "DOUBLE_COUNTING_RISK: Dataset contains both HARVEST_VOLUME (basin production) and INFLOW_ARRIVAL (market). "
            "Summing them causes double counting of the supply corridor."
        )

    # Violation 3: Temporal overlaps within the same market, product and target
    seen_periods: dict[tuple[str, str, QuantityTarget], list[tuple[date, date]]] = {}
    for r in records:
        key = (r.market_code, r.product_code, r.target)
        p_start = r.period_start or r.observed_date
        p_end = r.period_end or r.observed_date

        if key not in seen_periods:
            seen_periods[key] = []

        for s_start, s_end in seen_periods[key]:
            if not (p_end < s_start or p_start > s_end):
                violations.append(
                    f"TEMPORAL_OVERLAP: Duplicate or overlapping observation window for {key} "
                    f"between [{p_start}, {p_end}] and [{s_start}, {s_end}]."
                )
                break
        seen_periods[key].append((p_start, p_end))

    return violations
