"""Unit and currency normalization, conversion and numeric parsing (SPECS §7, §13)."""

from __future__ import annotations

import re

from ketrika.core.units import load_units

MISSING_CODES = {"nd", "na", "-", "nc", "none", "null", ".", "n/a", "n.d.", "n.a."}


def parse_numeric_value(raw: str | float | int | None) -> tuple[float | None, str | None]:
    """Parse raw numeric strings in fr/mg formats into float (SPECS §13).

    Rules:
    - ND, NA, -, empty -> (None, 'ND'). NEVER 0!
    - '2 850,50' or '2.850,50' -> (2850.5, None)
    - '2 850' or '2850' -> (2850.0, None)
    """
    if raw is None:
        return None, "ND"

    if isinstance(raw, (int, float)):
        return float(raw), None

    s = str(raw).strip()
    if not s or s.lower() in MISSING_CODES:
        return None, "ND"

    # Remove currency abbreviations if attached (e.g. "2850 Ar", "2850Ar")
    s_clean = re.sub(r"(?i)\s*(ar|mga|fmg|francs?)\s*$", "", s).strip()

    # Detect formats:
    # 1. European format with space/dot thousands and comma decimal: '2 850,50' or '2.850,50'
    if "," in s_clean and "." in s_clean:
        # Check order: if dot comes before comma, dot is thousand separator, comma is decimal
        if s_clean.rfind(",") > s_clean.rfind("."):
            s_clean = s_clean.replace(".", "").replace(",", ".")
        else:
            s_clean = s_clean.replace(",", "")
    elif "," in s_clean:
        # e.g. "2850,50" or "2 850,50" -> replace space and comma to dot
        s_clean = (
            s_clean.replace(" ", "").replace("\u00a0", "").replace("\u202f", "").replace(",", ".")
        )
    else:
        # Standard space or dot thousands separator without decimal: "2 850"
        s_clean = s_clean.replace(" ", "").replace("\u00a0", "").replace("\u202f", "")

    try:
        val = float(s_clean)
        return val, None
    except ValueError:
        return None, "ND"


def normalize_currency(
    price: float | None,
    currency_raw: str | None,
) -> tuple[float | None, str, float]:
    """Convert currency to MGA (Ariary).

    Rules (SPECS §13):
    - FMG / Francs: divided by 5, conversion_status = 'confident', confidence = 0.95
    - MGA / Ariary: kept as is, conversion_status = 'exact', confidence = 1.0
    - Other/unknown: price_mga = None, conversion_status = 'uncertain', confidence = 0.5
    """
    if price is None:
        return None, "exact", 1.0

    curr = (currency_raw or "MGA").strip().lower()
    if curr in {"fmg", "franc", "francs"}:
        return round(price / 5.0, 4), "confident", 0.95
    elif curr in {"mga", "ariary", "ar", ""}:
        return price, "exact", 1.0
    else:
        return None, "uncertain", 0.5


class UnitConverter:
    """Converts price and volume measurements to base units (kg, l)."""

    def __init__(self) -> None:
        self.units = {u.unit_code: u for u in load_units()}

    def convert_price_to_base(
        self,
        price_mga: float | None,
        unit_raw: str | None,
        product_code: str | None = None,
    ) -> tuple[float | None, str | None, str, float]:
        """Convert MGA price to price per base unit (MGA/kg or MGA/l) (SPECS §7).

        Returns: (price_mga_per_base, base_unit, conversion_status, confidence)
        Rule: price_mga_per_base is ONLY computed if conversion confidence >= 0.8.
        If confidence < 0.8 (e.g. kapoaka with 0.5): price_mga_per_base = None, status = 'uncertain'.
        """
        if not unit_raw or price_mga is None:
            return None, None, "uncertain", 0.0

        u_norm = unit_raw.strip().lower()
        # Direct base unit match
        if u_norm in {"kg", "kilogramme", "kilo"}:
            return price_mga, "kg", "exact", 1.0
        if u_norm in {"l", "litre", "liter"}:
            return price_mga, "l", "exact", 1.0

        # Look up in taxonomy
        unit_def = self.units.get(u_norm)
        if not unit_def:
            # Check common synonyms
            synonyms = {
                "tonne": "t",
                "tonnes": "t",
                "sac 50kg": "sac_50kg",
                "sac 50 kg": "sac_50kg",
                "sac": "sac_50kg",
                "quintal": "qx",
            }
            mapped_code = synonyms.get(u_norm)
            if mapped_code:
                unit_def = self.units.get(mapped_code)

        if not unit_def:
            return None, None, "uncertain", 0.0

        factor: float | None = None
        base_u: str | None = None
        conf: float = unit_def.confidence

        # 1. Product-specific conversion
        if unit_def.product_specific and product_code in unit_def.product_specific:
            spec = unit_def.product_specific[product_code]
            conf = spec.confidence
            base_u = spec.target_unit
            factor = spec.factor

        # 2. Generic conversion
        elif unit_def.factor is not None and unit_def.target_unit is not None:
            base_u = unit_def.target_unit
            factor = unit_def.factor
            conf = unit_def.confidence

        # Evaluate confidence threshold (SPECS §7: confidence >= 0.8 required for price_mga_per_base)
        if factor is not None and factor > 0 and conf >= 0.8:
            price_per_base = round(price_mga / factor, 4)
            status = "exact" if conf >= 0.99 else "confident"
            return price_per_base, base_u, status, conf

        # Confidence < 0.8 or unknown factor -> price_mga_per_base is NULL!
        return None, base_u, "uncertain", conf
