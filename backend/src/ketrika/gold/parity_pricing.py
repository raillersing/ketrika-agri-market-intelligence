"""Synthetic IPP/substitution scenarios, unverified and excluded from ingestion.

Constants and sinusoidal trajectories below are illustrative inputs, not
observations from BFM, OMH, World Bank, customs, or IFPRI. Numeric helpers
remain for offline scenario exploration; no writer may publish them. ADR152.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

IPP_PRODUCTS = ["RICE_WHITE_IMPORTED", "WHEAT_FLOUR", "VEG_OIL", "SUGAR"]
SUBSTITUTION_PRODUCTS = [
    "CASSAVA_FRESH",
    "CASSAVA_DRIED",
    "MAIZE_GRAIN",
    "SWEET_POTATO",
    "BEANS_DRY",
    "BAMBARA_GROUNDNUT",
    "LIMA_BEANS",
    "GROUNDNUT",
    "LENTILS",
    "RICE_PADDY",
]
CANONICAL_PPN_PRODUCTS = ["RICE_WHITE_LOCAL"] + IPP_PRODUCTS + SUBSTITUTION_PRODUCTS

# Date range: 2020-01-01 to 2026-10-01 (82 months)
START_YEAR = 2020
START_MONTH = 1
END_YEAR = 2026
END_MONTH = 10


def get_monthly_dates() -> list[date]:
    """Generate monthly date sequence from 2020-01 to 2026-10."""
    dates: list[date] = []
    y, m = START_YEAR, START_MONTH
    while (y < END_YEAR) or (y == END_YEAR and m <= END_MONTH):
        dates.append(date(y, m, 1))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return dates


# Synthetic scenario parameters; no primary-source verification.
def get_macro_benchmarks(d: date) -> dict[str, float]:
    """Synthetic exchange, freight, and fuel trajectories; not historical facts."""
    year, month = d.year, d.month
    progress = (year - 2020) + (month - 1) / 12.0

    # Official BFM USD/MGA exchange rate (Marché Interbancaire de Devises)
    # Starts at ~3750 in Jan 2020, gradual depreciation to ~4620 in Oct 2026
    fx_usd_mga = 3750.0 + progress * (4620.0 - 3750.0) / 6.75
    fx_usd_mga += 25.0 * math.sin(progress * 3.1415)

    # Ocean freight per metric ton to Toamasina (CNUCED / World Bank shipping index)
    if year in (2021, 2022):
        freight_ocean_usd = 110.0 + 35.0 * math.sin(progress * 2.0)
    else:
        freight_ocean_usd = 75.0 + 10.0 * math.sin(progress)

    # OMH Diesel price per liter (MGA/L)
    if year <= 2021:
        diesel_mga = 3400.0
    elif year == 2022:
        diesel_mga = 4100.0
    else:
        diesel_mga = 4900.0

    return {
        "fx_usd_mga": round(fx_usd_mga, 2),
        "freight_ocean_usd": round(freight_ocean_usd, 2),
        "diesel_mga": diesel_mga,
    }


def compute_import_parity_price(
    product_code: str, d: date, macro: dict[str, float]
) -> dict[str, Any]:
    """Compute Import Parity Price (IPP) in MGA/kg or MGA/L."""
    year, month = d.year, d.month
    progress = (year - 2020) + (month - 1) / 12.0
    fx = macro["fx_usd_mga"]
    freight = macro["freight_ocean_usd"]
    diesel = macro["diesel_mga"]

    # Port handling + GasyNet fee (MGA/MT)
    c_port = 85000.0
    # RN2 road transport (350 km Toamasina -> Antananarivo) in MGA/MT
    c_transport = 350.0 * (diesel / 4900.0) * 120.0  # ~42,000 MGA/MT

    if product_code == "RICE_WHITE_IMPORTED":
        if year in (2023, 2024):
            fob_usd = 580.0 + 30.0 * math.cos(progress * 2)
        else:
            fob_usd = 450.0 + 40.0 * (progress / 6.75)
        tariff_dd = 0.0
        vat_rate = 0.0
        margin = 0.12
        unit = "kg"

    elif product_code == "WHEAT_FLOUR":
        if year == 2022:
            fob_usd = 410.0 + 20.0 * math.sin(month)
        elif year >= 2023:
            fob_usd = 285.0 + 15.0 * math.sin(progress)
        else:
            fob_usd = 240.0 + 10.0 * math.sin(progress)
        tariff_dd = 0.10
        vat_rate = 0.20
        c_milling = 180000.0
        margin = 0.15
        unit = "kg"

    elif product_code == "VEG_OIL":
        if year == 2022:
            fob_usd = 1450.0 + 100.0 * math.cos(month)
        elif year >= 2024:
            fob_usd = 960.0 + 40.0 * math.sin(progress)
        else:
            fob_usd = 780.0 + 50.0 * math.sin(progress)
        tariff_dd = 0.10
        vat_rate = 0.20
        c_port += 65000.0
        margin = 0.15
        unit = "l"

    elif product_code == "SUGAR":
        if year in (2023, 2024):
            fob_usd = 530.0 + 25.0 * math.sin(month)
        elif year >= 2025:
            fob_usd = 470.0 + 20.0 * math.cos(progress)
        else:
            fob_usd = 310.0 + 30.0 * math.sin(progress)
        tariff_dd = 0.20
        vat_rate = 0.20
        margin = 0.15
        unit = "kg"
    else:
        raise ValueError(f"Unknown IPP product: {product_code}")

    cif_mga_mt = (fob_usd + freight) * fx
    landed_cost_mt = cif_mga_mt * (1.0 + tariff_dd) * (1.0 + vat_rate) + c_port + c_transport
    if product_code == "WHEAT_FLOUR":
        landed_cost_mt = landed_cost_mt * 1.35 + c_milling

    retail_mt = landed_cost_mt * (1.0 + margin)
    retail_unit_price = round(retail_mt / 1000.0, 2)

    return {
        "price": retail_unit_price,
        "qualification": "synthetic_unverified",
        "unit": unit,
        "fob_usd": round(fob_usd, 2),
        "freight_usd": freight,
        "fx_usd_mga": fx,
        "tariff_dd": tariff_dd,
        "vat_rate": vat_rate,
        "method": "Import Parity Pricing (IPP)",
        "source_citation": None,
    }


def compute_substitution_price(
    product_code: str, d: date, anchor_rice_price: float, macro: dict[str, float]
) -> dict[str, Any]:
    """Compute certified econometric substitution price based on IFPRI caloric model & harvest calendar."""
    month = d.month
    is_soudure = month in (11, 12, 1, 2, 3)

    if product_code == "CASSAVA_FRESH":
        ratio = 0.46 if is_soudure else 0.36
        price = round(anchor_rice_price * ratio, 2)
        unit = "kg"
        details = "IFPRI caloric substitution ratio 0.36-0.46 vs local rice"

    elif product_code == "CASSAVA_DRIED":
        fresh_ratio = 0.46 if is_soudure else 0.36
        price = round(anchor_rice_price * fresh_ratio * 1.55, 2)
        unit = "kg"
        details = "Dry cossettes conversion (2.5:1 fresh ratio + drying margin)"

    elif product_code == "MAIZE_GRAIN":
        ratio = 0.64 if is_soudure else 0.52
        price = round(anchor_rice_price * ratio, 2)
        unit = "kg"
        details = "IFPRI maize caloric substitution ratio 0.52-0.64 vs local rice"

    elif product_code == "SWEET_POTATO":
        ratio = 0.44 if is_soudure else 0.34
        price = round(anchor_rice_price * ratio, 2)
        unit = "kg"
        details = "Tuber caloric parity 0.34-0.44 vs local rice"

    elif product_code == "BEANS_DRY":
        ratio = 1.62 if is_soudure else 1.38
        price = round(anchor_rice_price * ratio, 2)
        unit = "kg"
        details = "Protein pulse parity ratio 1.38-1.62 vs local rice"

    elif product_code == "BAMBARA_GROUNDNUT":
        ratio = 1.75 if is_soudure else 1.48
        price = round(anchor_rice_price * ratio, 2)
        unit = "kg"
        details = "Traditional pulse parity 1.48-1.75 vs local rice"

    elif product_code == "LIMA_BEANS":
        ratio = 1.85 if is_soudure else 1.55
        price = round(anchor_rice_price * ratio, 2)
        unit = "kg"
        details = "Southwest pulse export & local parity 1.55-1.85 vs local rice"

    elif product_code == "GROUNDNUT":
        ratio = 2.05 if is_soudure else 1.75
        price = round(anchor_rice_price * ratio, 2)
        unit = "kg"
        details = "Oilseed & protein parity 1.75-2.05 vs local rice"

    elif product_code == "LENTILS":
        ratio = 2.20 if is_soudure else 1.95
        price = round(anchor_rice_price * ratio, 2)
        unit = "kg"
        details = "Imported pulse parity 1.95-2.20 vs local rice"

    elif product_code == "RICE_PADDY":
        price = round(anchor_rice_price * 0.60 - 50.0, 2)
        unit = "kg"
        details = "Milling technical extraction ratio 0.60 vs milled local rice"

    else:
        raise ValueError(f"Unknown substitution product: {product_code}")

    return {
        "price": price,
        "qualification": "synthetic_unverified",
        "unit": unit,
        "method": "IFPRI Caloric Substitution & Seasonality Model",
        "details": details,
        "anchor_rice_price": anchor_rice_price,
        "is_soudure": is_soudure,
    }


class UnverifiedPricingInputs(ValueError):
    """Synthetic trajectories cannot be published as sourced market prices."""


def generate_and_load_econometric_prices(session: Session) -> dict[str, int]:
    """Refuse synthetic inputs before SQL, Bronze, or observation mutations."""
    raise UnverifiedPricingInputs("verified_economic_pricing_inputs_required")


def main() -> None:
    """Do not connect to a database for an unqualified generator."""
    raise UnverifiedPricingInputs("verified_economic_pricing_inputs_required")


if __name__ == "__main__":
    main()
