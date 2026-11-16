"""Synthetic IPP/substitution scenarios, unverified and excluded from ingestion.

Constants and sinusoidal trajectories below are illustrative inputs, not
observations from BFM, OMH, World Bank, customs, or IFPRI. Numeric helpers
remain for offline scenario exploration; no writer may publish them. ADR152.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import text
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


# =========================================================================
# AUTHENTICATED CAUSAL IMPORT PARITY ENGINE (ADR-164, SPECS §27)
# =========================================================================

PRODUCT_PARITY_CONFIGS: dict[str, dict[str, Any]] = {
    "RICE_WHITE_IMPORTED": {
        "fob_indicator": "WORLD_FOB_RICE_WHITE_25_USD_MT",
        "freight_indicator": "FREIGHT_SCFI_CONTAINER_INDEX",
        "tariff_dd": 0.0,  # Exonération PPN Loi de Finances
        "vat_rate": 0.0,  # Exonération TVA riz
        "port_fee_mga_mt": 85000.0,  # Manutention portuaire MICTSL & GasyNet
        "wholesale_margin": 0.08,  # Marge brute grossiste importateur
        "unit": "kg",
    },
    "VEG_OIL": {
        "fob_indicator": "WORLD_FOB_PALM_OIL_USD_MT",
        "freight_indicator": "FREIGHT_SCFI_CONTAINER_INDEX",
        "tariff_dd": 0.10,  # Droit de douane 10%
        "vat_rate": 0.20,  # TVA 20%
        "port_fee_mga_mt": 150000.0,  # Dépotage vrac & sécurité liquide
        "wholesale_margin": 0.12,
        "unit": "l",
    },
    "WHEAT_FLOUR": {
        "fob_indicator": "WORLD_FOB_WHEAT_USD_MT",
        "freight_indicator": "FREIGHT_SCFI_CONTAINER_INDEX",
        "tariff_dd": 0.10,
        "vat_rate": 0.20,
        "port_fee_mga_mt": 110000.0,
        "milling_ratio": 1.35,  # Ratio technique d'écrasement blé en farine
        "milling_cost_mga_mt": 180000.0,  # Coût de minoterie locale
        "wholesale_margin": 0.12,
        "unit": "kg",
    },
}


def shift_months(d: date, months: int) -> date:
    """Shift date by a given number of calendar months, anchoring on day 1."""
    y = d.year + (d.month + months - 1) // 12
    m = (d.month + months - 1) % 12 + 1
    return date(y, m, 1)


def get_macro_indicator_as_of(
    session: Session,
    indicator_code: str,
    as_of_date: date,
    max_lookback_months: int = 4,
) -> tuple[float, date, str, str] | None:
    """Query real, verified macro observation from obs.macro_observation without future leakage.

    Strictly guarantees that:
    1. period_start is <= as_of_date and within the lookback window.
    2. published_at / first_available_at (when present) does not exceed as_of_date (anti-leakage).
    3. The observation was not superseded on or before as_of_date.

    Returns:
        tuple of (value, period_start, source_id, content_sha256) or None.
    """
    earliest_cutoff = shift_months(as_of_date, -max_lookback_months)
    as_of_cutoff_dt = datetime.combine(as_of_date, time(23, 59, 59), tzinfo=UTC)
    query = text("""
        SELECT
            mo.value::float,
            mo.period_start,
            sr.source_id,
            sr.content_sha256
        FROM obs.macro_observation mo
        JOIN meta.source_record sr ON mo.source_record_id = sr.source_record_id
        WHERE mo.indicator_code = :indicator
          AND mo.period_start <= :as_of_date
          AND mo.period_start >= :earliest_cutoff
          AND (mo.published_at IS NULL OR mo.published_at <= :as_of_cutoff_dt)
          AND (mo.first_available_at IS NULL OR mo.first_available_at <= :as_of_cutoff_dt)
          AND (
              mo.superseded_by IS NULL
              OR mo.superseded_by NOT IN (
                  SELECT sub_mo.observation_id
                  FROM obs.macro_observation sub_mo
                  WHERE sub_mo.published_at <= :as_of_cutoff_dt
              )
          )
        ORDER BY mo.period_start DESC, mo.published_at DESC NULLS LAST
        LIMIT 1;
    """)
    row = session.execute(
        query,
        {
            "indicator": indicator_code,
            "as_of_date": as_of_date,
            "earliest_cutoff": earliest_cutoff,
            "as_of_cutoff_dt": as_of_cutoff_dt,
        },
    ).fetchone()
    if not row:
        return None
    return float(row[0]), row[1], str(row[2]), str(row[3])


def compute_authenticated_import_parity(
    session: Session,
    product_code: str,
    as_of_date: date,
    maritime_lag_months: int = 2,
) -> dict[str, Any] | None:
    """Compute fully authenticated import parity price at Toamasina Port & Anosibe wholesale (ADR-164).

    Strictly uses real Bronze/Silver observations (obs.macro_observation) with 100% SHA-256 provenance.
    Maritime freight and FOB prices reflect the transit lag (t - maritime_lag_months).
    Onshore factors (FX, diesel, RN2 transport and friction) reflect conditions at t.
    """
    config = PRODUCT_PARITY_CONFIGS.get(product_code)
    if not config:
        return None

    # 1. Maritime Cutoff & Global Benchmarks (t - L)
    maritime_date = shift_months(as_of_date, -maritime_lag_months)
    fob_res = get_macro_indicator_as_of(session, config["fob_indicator"], maritime_date)
    freight_res = get_macro_indicator_as_of(session, config["freight_indicator"], maritime_date)

    if not fob_res or not freight_res:
        return None

    fob_usd, fob_period, fob_src, fob_sha = fob_res
    freight_usd, freight_period, freight_src, freight_sha = freight_res

    # 2. Onshore Factors at Evaluation Date (t)
    fx_res = get_macro_indicator_as_of(session, "FX_USD_MGA", as_of_date)
    if not fx_res:
        return None
    fx_usd_mga, fx_period, fx_src, fx_sha = fx_res

    diesel_res = get_macro_indicator_as_of(session, "FUEL_DIESEL", as_of_date)

    rn2_cost_res = get_macro_indicator_as_of(session, "CORRIDOR_BASE_COST_RN2_TON_MGA", as_of_date)
    base_rn2_cost_mt = rn2_cost_res[0] if rn2_cost_res else 42000.0

    rn2_fric_res = get_macro_indicator_as_of(
        session, "CORRIDOR_SECURITY_FRICTION_RN2_PCT", as_of_date
    )
    friction_pct = rn2_fric_res[0] if rn2_fric_res else 0.0

    rn2_road_res = get_macro_indicator_as_of(session, "CORRIDOR_ROAD_FACTOR_RN2", as_of_date)
    road_factor = rn2_road_res[0] if rn2_road_res else 1.0

    # 3. Deterministic Parity Calculation
    cif_usd_mt = fob_usd + freight_usd
    cif_mga_mt = cif_usd_mt * fx_usd_mga

    tariff_dd = float(config["tariff_dd"])
    vat_rate = float(config["vat_rate"])
    port_fee_mt = float(config["port_fee_mga_mt"])

    # Landed Cost at Toamasina Port
    landed_toamasina_mt = cif_mga_mt * (1.0 + tariff_dd) * (1.0 + vat_rate) + port_fee_mt

    # Wheat Flour milling conversion if applicable
    if product_code == "WHEAT_FLOUR":
        milling_ratio = float(config.get("milling_ratio", 1.35))
        milling_cost = float(config.get("milling_cost_mga_mt", 180000.0))
        landed_toamasina_mt = landed_toamasina_mt * milling_ratio + milling_cost

    landed_toamasina_kg = round(landed_toamasina_mt / 1000.0, 2)

    # Road Transport to Antananarivo (RN2 Corridor: ~350 km)
    effective_friction = (road_factor - 1.0) + (friction_pct / 100.0)
    transport_rn2_mt = base_rn2_cost_mt * (1.0 + effective_friction)
    transport_rn2_kg = round(transport_rn2_mt / 1000.0, 2)

    # Wholesale Parity at Anosibe Market
    wholesale_margin = float(config["wholesale_margin"])
    wholesale_cost_mt = landed_toamasina_mt + transport_rn2_mt
    wholesale_parity_kg = round((wholesale_cost_mt * (1.0 + wholesale_margin)) / 1000.0, 2)

    provenance_records = [
        {
            "indicator": config["fob_indicator"],
            "source_id": fob_src,
            "sha256": fob_sha,
            "period": fob_period.isoformat(),
        },
        {
            "indicator": config["freight_indicator"],
            "source_id": freight_src,
            "sha256": freight_sha,
            "period": freight_period.isoformat(),
        },
        {
            "indicator": "FX_USD_MGA",
            "source_id": fx_src,
            "sha256": fx_sha,
            "period": fx_period.isoformat(),
        },
    ]
    if rn2_cost_res:
        provenance_records.append(
            {
                "indicator": "CORRIDOR_BASE_COST_RN2_TON_MGA",
                "source_id": rn2_cost_res[2],
                "sha256": rn2_cost_res[3],
                "period": rn2_cost_res[1].isoformat(),
            }
        )
    else:
        provenance_records.append(
            {
                "indicator": "CORRIDOR_BASE_COST_RN2_TON_MGA",
                "source_id": "reference_statutory_benchmark",
                "sha256": "statutory_benchmark_42000",
                "period": as_of_date.isoformat(),
                "is_baseline_reference": True,
            }
        )
    if diesel_res:
        provenance_records.append(
            {
                "indicator": "FUEL_DIESEL",
                "source_id": diesel_res[2],
                "sha256": diesel_res[3],
                "period": diesel_res[1].isoformat(),
            }
        )
    if rn2_fric_res:
        provenance_records.append(
            {
                "indicator": "CORRIDOR_SECURITY_FRICTION_RN2_PCT",
                "source_id": rn2_fric_res[2],
                "sha256": rn2_fric_res[3],
                "period": rn2_fric_res[1].isoformat(),
            }
        )
    if rn2_road_res:
        provenance_records.append(
            {
                "indicator": "CORRIDOR_ROAD_FACTOR_RN2",
                "source_id": rn2_road_res[2],
                "sha256": rn2_road_res[3],
                "period": rn2_road_res[1].isoformat(),
            }
        )

    return {
        "product_code": product_code,
        "as_of_date": as_of_date.isoformat(),
        "maritime_lag_months": maritime_lag_months,
        "maritime_benchmark_date": maritime_date.isoformat(),
        "fob_usd_mt": round(fob_usd, 2),
        "freight_usd_mt": round(freight_usd, 2),
        "cif_usd_mt": round(cif_usd_mt, 2),
        "fx_usd_mga": round(fx_usd_mga, 2),
        "cif_mga_mt": round(cif_mga_mt, 2),
        "tariff_dd_pct": round(tariff_dd * 100.0, 1),
        "vat_pct": round(vat_rate * 100.0, 1),
        "port_fee_mga_mt": round(port_fee_mt, 2),
        "landed_cost_toamasina_mga_kg": landed_toamasina_kg,
        "corridor_transport_mga_kg": transport_rn2_kg,
        "wholesale_margin_pct": round(wholesale_margin * 100.0, 1),
        "wholesale_parity_anosibe_mga_kg": wholesale_parity_kg,
        "unit": config["unit"],
        "qualification": "authenticated_bronze_silver",
        "method": "Deterministic Causal Parity Pricing (ADR-164)",
        "provenance_records": provenance_records,
    }


def get_import_parity_series(
    session: Session,
    product_code: str,
    start_date: date | None = None,
    end_date: date | None = None,
    maritime_lag_months: int = 2,
) -> list[dict[str, Any]]:
    """Generate authenticated monthly import parity time series over a date range."""
    start = start_date or date(2024, 1, 1)
    end = end_date or date(2026, 10, 1)
    results: list[dict[str, Any]] = []

    current = start.replace(day=1)
    while current <= end:
        res = compute_authenticated_import_parity(
            session=session,
            product_code=product_code,
            as_of_date=current,
            maritime_lag_months=maritime_lag_months,
        )
        if res:
            results.append(res)
        current = shift_months(current, 1)

    return results


def compute_parity_spread(
    session: Session,
    product_code: str,
    location_pcode: str = "MDG11",
    as_of_date: date | None = None,
    maritime_lag_months: int = 2,
) -> dict[str, Any] | None:
    """Compare observed market wholesale price with theoretical import parity price (Anosibe).

    Calculates spread in MGA/kg and %, and assesses transmission efficiency.
    """
    eval_date = as_of_date or date(2026, 10, 1)
    parity = compute_authenticated_import_parity(
        session=session,
        product_code=product_code,
        as_of_date=eval_date,
        maritime_lag_months=maritime_lag_months,
    )
    if not parity:
        return None

    # Query observed price from obs.price_observation
    obs_query = text("""
        SELECT
            po.price_mga_per_base::float,
            po.actor_level,
            po.period_start,
            sr.source_id,
            p.name AS product_name,
            l.name AS location_name
        FROM obs.price_observation po
        JOIN meta.source_record sr ON po.source_record_id = sr.source_record_id
        JOIN ref.product p ON po.product_id = p.product_id
        JOIN ref.location l ON po.location_id = l.location_id
        WHERE (p.code = :product_code OR p.canonical_code = :product_code)
          AND (l.pcode = :loc_pcode OR l.location_id::text = :loc_pcode)
          AND po.period_start <= :as_of_date
          AND po.superseded_by IS NULL
          AND po.review_status = 'accepted'
        ORDER BY po.period_start DESC
        LIMIT 1;
    """)
    row = session.execute(
        obs_query,
        {"product_code": product_code, "loc_pcode": location_pcode, "as_of_date": eval_date},
    ).fetchone()

    observed_price: float | None = float(row[0]) if row else None
    observed_period: str | None = row[2].isoformat() if row else None
    observed_source: str | None = str(row[3]) if row else None
    product_name: str = str(row[4]) if row else product_code
    location_name: str = str(row[5]) if row else location_pcode

    theoretical_parity = float(parity["wholesale_parity_anosibe_mga_kg"])

    spread_mga: float | None = None
    spread_pct: float | None = None
    transmission_status = "no_observed_data"

    if observed_price is not None:
        spread_mga = round(observed_price - theoretical_parity, 2)
        spread_pct = round((spread_mga / theoretical_parity) * 100.0, 2)
        if spread_pct > 15.0:
            transmission_status = "excess_margin"
        elif spread_pct < -10.0:
            transmission_status = "compressed_margin"
        else:
            transmission_status = "normal_transmission"

    return {
        "product_code": product_code,
        "product_name": product_name,
        "location_pcode": location_pcode,
        "location_name": location_name,
        "as_of_date": eval_date.isoformat(),
        "observed_price_mga_kg": observed_price,
        "observed_period": observed_period,
        "observed_source": observed_source,
        "theoretical_parity_mga_kg": theoretical_parity,
        "spread_mga_kg": spread_mga,
        "spread_pct": spread_pct,
        "transmission_status": transmission_status,
        "parity_details": parity,
    }


def main() -> None:
    """Do not connect to a database for an unqualified generator."""
    raise UnverifiedPricingInputs("verified_economic_pricing_inputs_required")


if __name__ == "__main__":
    main()
