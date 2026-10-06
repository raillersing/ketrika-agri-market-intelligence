"""Units of measurement loader, conversion engine and validator."""

from pathlib import Path
from typing import Any

import yaml

from ketrika.core.models.units import (
    ConversionStatus,
    UnitDefinition,
)
from ketrika.core.registry import find_repo_root

UNIT_ALIASES = {
    "kg": "kg",
    "kilo": "kg",
    "kilogramme": "kg",
    "kilogram": "kg",
    "t": "t",
    "tonne": "t",
    "tonnes": "t",
    "ton": "t",
    "tons": "t",
    "qx": "qx",
    "quintal": "qx",
    "l": "l",
    "litre": "l",
    "litres": "l",
    "liter": "l",
    "liters": "l",
    "ml": "ml",
    "g": "g",
    "gramme": "g",
    "sac_50kg": "sac_50kg",
    "sac_25kg": "sac_25kg",
    "bouteille_1l": "bouteille_1l",
    "kapoaka": "kapoaka",
    "daba": "daba",
    "gony": "gony",
}


def get_default_units_path() -> Path:
    """Return default path to taxonomy/units.yaml."""
    root = find_repo_root()
    return root / "taxonomy" / "units.yaml"


def normalize_unit_code(raw_code: str) -> str:
    """Normalize raw unit code string to canonical unit_code."""
    cleaned = raw_code.strip().lower()
    return UNIT_ALIASES.get(cleaned, cleaned)


def load_units(units_path: Path | str | None = None) -> list[UnitDefinition]:
    """Load and validate all unit definitions from taxonomy/units.yaml."""
    path = Path(units_path) if units_path else get_default_units_path()
    if not path.exists():
        raise FileNotFoundError(f"Units definition file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected YAML list in {path}, got {type(data).__name__}")

    return [UnitDefinition.model_validate(item) for item in data]


def get_unit(unit_code: str, units_path: Path | str | None = None) -> UnitDefinition:
    """Retrieve unit definition by code."""
    canon = normalize_unit_code(unit_code)
    units = load_units(units_path)
    for u in units:
        if u.unit_code == canon:
            return u
    raise KeyError(f"Unit '{unit_code}' (normalized '{canon}') not found in taxonomy")


def convert_to_base(
    value: float,
    unit_code: str,
    product_code: str | None = None,
    units: list[UnitDefinition] | None = None,
) -> tuple[float | None, str, float, ConversionStatus]:
    """Convert a physical quantity to standard base unit (kg or l).

    Returns (converted_value, base_unit, confidence, conversion_status).
    If confidence < 0.8, converted_value is None and status is 'uncertain'.
    """
    canon = normalize_unit_code(unit_code)
    all_units = units if units is not None else load_units()

    target_unit_def: UnitDefinition | None = None
    for u in all_units:
        if u.unit_code == canon:
            target_unit_def = u
            break

    if target_unit_def is None:
        raise KeyError(f"Unknown unit code: '{unit_code}'")

    # Check product-specific override first
    if product_code and product_code in target_unit_def.product_specific:
        spec = target_unit_def.product_specific[product_code]
        factor = spec.factor
        target_unit = spec.target_unit
        confidence = spec.confidence
    elif target_unit_def.factor is not None and target_unit_def.target_unit is not None:
        factor = target_unit_def.factor
        target_unit = target_unit_def.target_unit
        confidence = target_unit_def.confidence
    else:
        # Cannot convert generic packaging or local unit without product or declared tare
        return None, target_unit_def.target_unit or "kg", target_unit_def.confidence, "uncertain"

    if confidence >= 0.99:
        status: ConversionStatus = "exact"
    elif confidence >= 0.80:
        status = "confident"
    else:
        status = "uncertain"

    if status == "uncertain":
        return None, target_unit, confidence, status

    converted = value * factor
    return converted, target_unit, confidence, status


def convert_from_base(
    base_value: float,
    unit_code: str,
    product_code: str | None = None,
    units: list[UnitDefinition] | None = None,
) -> tuple[float | None, float, ConversionStatus]:
    """Perform inverse conversion from base unit (kg or l) back to original unit."""
    canon = normalize_unit_code(unit_code)
    all_units = units if units is not None else load_units()

    target_unit_def: UnitDefinition | None = None
    for u in all_units:
        if u.unit_code == canon:
            target_unit_def = u
            break

    if target_unit_def is None:
        raise KeyError(f"Unknown unit code: '{unit_code}'")

    if product_code and product_code in target_unit_def.product_specific:
        spec = target_unit_def.product_specific[product_code]
        factor = spec.factor
        confidence = spec.confidence
    elif target_unit_def.factor is not None:
        factor = target_unit_def.factor
        confidence = target_unit_def.confidence
    else:
        return None, target_unit_def.confidence, "uncertain"

    if confidence >= 0.99:
        status: ConversionStatus = "exact"
    elif confidence >= 0.80:
        status = "confident"
    else:
        status = "uncertain"

    if status == "uncertain" or factor <= 0.0:
        return None, confidence, status

    original = base_value / factor
    return original, confidence, status


def validate_units(units_path: Path | str | None = None) -> list[str]:
    """Validate completeness, uniqueness, and evidence requirements of units."""
    errors: list[str] = []

    try:
        units = load_units(units_path)
    except Exception as e:
        return [f"Failed to load units: {e}"]

    unit_codes: set[str] = set()
    for u in units:
        if u.unit_code in unit_codes:
            errors.append(f"Duplicate unit_code in units.yaml: '{u.unit_code}'")
        unit_codes.add(u.unit_code)

        # Rule: No conversion of confidence >= 0.8 without evidence
        if u.factor is not None and u.confidence >= 0.8:
            if not u.evidence.strip():
                errors.append(
                    f"Unit '{u.unit_code}' has confidence {u.confidence} >= 0.8 but missing evidence"
                )

        for prod, spec in u.product_specific.items():
            if spec.confidence >= 0.8 and not spec.evidence.strip():
                errors.append(
                    f"Unit '{u.unit_code}' override for '{prod}' has confidence >= 0.8 but missing evidence"
                )

    return errors
