"""Unit tests for causal features: Import Parity Pricing, Phenological Stress, and Corridor Friction (ADR-164).

Validates mathematical correctness, causality (anti-leakage), and deterministic outputs.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from ketrika.gold.agroclimate_features import (
    STAGE_WEIGHTS,
    compute_phenological_stress,
)
from ketrika.gold.corridor_friction import (
    compute_corridor_friction,
    get_all_corridors_summary,
)
from ketrika.gold.parity_pricing import (
    compute_authenticated_import_parity,
    compute_parity_spread,
    shift_months,
)

# =========================================================================
# 1. PARITY PRICING UNIT TESTS
# =========================================================================


def test_shift_months():
    """Verify month arithmetic handles year boundaries and leaps correctly."""
    assert shift_months(date(2026, 10, 1), -2) == date(2026, 8, 1)
    assert shift_months(date(2026, 1, 1), -1) == date(2025, 12, 1)
    assert shift_months(date(2025, 12, 1), 1) == date(2026, 1, 1)
    assert shift_months(date(2024, 2, 29), 0) == date(2024, 2, 1)


def test_parity_pricing_rice_calculation():
    """Verify deterministic import parity formula for imported rice."""
    session = MagicMock()

    # Mock get_macro_indicator_as_of queries
    def mock_execute(query, params):
        ind = params["indicator"]
        mock_result = MagicMock()
        if ind == "WORLD_FOB_RICE_WHITE_25_USD_MT":
            mock_result.fetchone.return_value = (
                520.0,
                date(2026, 8, 1),
                "world_benchmarks",
                "sha_fob_rice",
            )
        elif ind == "FREIGHT_SCFI_CONTAINER_INDEX":
            mock_result.fetchone.return_value = (
                85.0,
                date(2026, 8, 1),
                "world_benchmarks",
                "sha_freight",
            )
        elif ind == "FX_USD_MGA":
            mock_result.fetchone.return_value = (4600.0, date(2026, 10, 1), "bfm_fx", "sha_fx")
        elif ind == "CORRIDOR_BASE_COST_RN2_TON_MGA":
            mock_result.fetchone.return_value = (
                45000.0,
                date(2026, 10, 1),
                "corridor_friction",
                "sha_rn2",
            )
        elif ind == "CORRIDOR_SECURITY_FRICTION_RN2_PCT":
            mock_result.fetchone.return_value = (
                5.0,
                date(2026, 10, 1),
                "corridor_friction",
                "sha_rn2_sec",
            )
        elif ind == "CORRIDOR_ROAD_FACTOR_RN2":
            mock_result.fetchone.return_value = (
                1.05,
                date(2026, 10, 1),
                "corridor_friction",
                "sha_rn2_road",
            )
        else:
            mock_result.fetchone.return_value = None
        return mock_result

    session.execute.side_effect = mock_execute

    eval_date = date(2026, 10, 1)
    res = compute_authenticated_import_parity(
        session=session,
        product_code="RICE_WHITE_IMPORTED",
        as_of_date=eval_date,
        maritime_lag_months=2,
    )

    assert res is not None
    assert res["product_code"] == "RICE_WHITE_IMPORTED"
    assert res["maritime_benchmark_date"] == "2026-08-01"
    assert res["fob_usd_mt"] == 520.0
    assert res["freight_usd_mt"] == 85.0
    assert res["cif_usd_mt"] == 605.0  # 520 + 85
    assert res["fx_usd_mga"] == 4600.0
    assert res["cif_mga_mt"] == 605.0 * 4600.0  # 2,783,000 MGA/MT

    # Rice has 0% customs tariff and 0% VAT
    assert res["tariff_dd_pct"] == 0.0
    assert res["vat_pct"] == 0.0
    # Landed Toamasina MT = 2,783,000 + 85,000 (port fee) = 2,868,000
    assert res["landed_cost_toamasina_mga_kg"] == 2868.0

    # RN2 road transport: base 45000 * (1 + (1.05-1) + 0.05) = 45000 * 1.10 = 49500 MGA/MT = 49.50 MGA/kg
    assert res["corridor_transport_mga_kg"] == 49.50

    # Wholesale Anosibe = (2,868,000 + 49,500) * 1.08 / 1000 = 2,917,500 * 1.08 / 1000 = 3150.90 MGA/kg
    assert res["wholesale_parity_anosibe_mga_kg"] == pytest.approx(3150.90, rel=1e-2)
    assert len(res["provenance_records"]) >= 3


def test_parity_pricing_veg_oil():
    """Verify palm oil parity pricing with 10% customs tariff and 20% VAT."""
    session = MagicMock()

    def mock_execute(query, params):
        ind = params["indicator"]
        mock_result = MagicMock()
        if ind == "WORLD_FOB_PALM_OIL_USD_MT":
            mock_result.fetchone.return_value = (
                950.0,
                date(2026, 8, 1),
                "world_benchmarks",
                "sha_fob_oil",
            )
        elif ind == "FREIGHT_SCFI_CONTAINER_INDEX":
            mock_result.fetchone.return_value = (
                100.0,
                date(2026, 8, 1),
                "world_benchmarks",
                "sha_freight",
            )
        elif ind == "FX_USD_MGA":
            mock_result.fetchone.return_value = (4500.0, date(2026, 10, 1), "bfm_fx", "sha_fx")
        elif ind == "CORRIDOR_BASE_COST_RN2_TON_MGA":
            mock_result.fetchone.return_value = (
                40000.0,
                date(2026, 10, 1),
                "corridor_friction",
                "sha_rn2",
            )
        else:
            mock_result.fetchone.return_value = None
        return mock_result

    session.execute.side_effect = mock_execute

    res = compute_authenticated_import_parity(
        session=session,
        product_code="VEG_OIL",
        as_of_date=date(2026, 10, 1),
    )

    assert res is not None
    assert res["cif_usd_mt"] == 1050.0  # 950 + 100
    # CIF MGA = 1050 * 4500 = 4,725,000
    # Landed = 4,725,000 * 1.10 (DD) * 1.20 (VAT) + 150,000 (port fee) = 6,237,000 + 150,000 = 6,387,000
    assert res["landed_cost_toamasina_mga_kg"] == 6387.0
    assert res["unit"] == "l"


def test_parity_spread_transmission_status():
    """Verify spread calculation and margin transmission classification."""
    session = MagicMock()

    # Case 1: Observed price higher than parity by 25% -> excess_margin
    def mock_execute_excess(query, params):
        mock_result = MagicMock()
        # Parity indicators
        if "indicator" in params:
            ind = params["indicator"]
            if ind == "WORLD_FOB_RICE_WHITE_25_USD_MT":
                mock_result.fetchone.return_value = (
                    500.0,
                    date(2026, 8, 1),
                    "world_benchmarks",
                    "sha_fob",
                )
            elif ind == "FREIGHT_SCFI_CONTAINER_INDEX":
                mock_result.fetchone.return_value = (
                    80.0,
                    date(2026, 8, 1),
                    "world_benchmarks",
                    "sha_fr",
                )
            elif ind == "FX_USD_MGA":
                mock_result.fetchone.return_value = (4500.0, date(2026, 10, 1), "bfm_fx", "sha_fx")
            else:
                mock_result.fetchone.return_value = None
        else:
            # Observed price query: returns 3800 MGA/kg
            mock_result.fetchone.return_value = (
                3800.0,
                "wholesale",
                date(2026, 10, 1),
                "odr_mdg",
                "Riz blanc importé",
                "Antananarivo",
            )
        return mock_result

    session.execute.side_effect = mock_execute_excess
    spread = compute_parity_spread(session, "RICE_WHITE_IMPORTED", "MDG11", date(2026, 10, 1))
    assert spread is not None
    assert spread["observed_price_mga_kg"] == 3800.0
    assert spread["transmission_status"] == "excess_margin"
    assert spread["spread_pct"] > 15.0


# =========================================================================
# 2. AGROCLIMATE PHENOLOGICAL STRESS UNIT TESTS
# =========================================================================


def test_stage_weights_contract():
    """Verify normative vulnerability weights adhere strictly to SPECS §27.1.3."""
    assert STAGE_WEIGHTS["flowering"] == 0.50
    assert STAGE_WEIGHTS["grain_filling"] == 0.50
    assert STAGE_WEIGHTS["tillering"] == 0.25
    assert STAGE_WEIGHTS["growing"] == 0.25
    assert STAGE_WEIGHTS["planting"] == 0.20
    assert STAGE_WEIGHTS["harvest"] == 0.05
    assert STAGE_WEIGHTS["off_season"] == 0.00


def test_phenological_stress_deficit_scenario():
    """Verify that severe rainfall deficit during flowering yields a negative stress score."""
    session = MagicMock()

    # Mock weather_monthly with severe drought during flowering (e.g. -50% rain)
    def mock_weather(query, params):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (date(2026, 3, 1), 50.0, 100.0, -0.50),  # -50% anomaly
            (date(2026, 4, 1), 30.0, 90.0, -0.66),  # -66% anomaly during flowering
            (date(2026, 5, 1), 20.0, 50.0, -0.60),  # -60% anomaly
        ]
        return mock_result

    session.execute.side_effect = mock_weather

    res = compute_phenological_stress(
        session=session,
        location_pcode="MDG32",  # Alaotra
        product_code="RICE_PADDY",
        as_of_date=date(2026, 5, 1),
        lookback_months=3,
    )

    assert res is not None
    assert res["zone_code"] == "ZONE_ALAOTRA"
    assert res["phenological_stress_index"] < -0.30
    assert res["stress_category"] in ("severe_deficit", "moderate_deficit")
    assert len(res["stage_evaluations"]) == 3


def test_phenological_stress_optimal_scenario():
    """Verify normal rainfall (near 0% anomaly) yields optimal category."""
    session = MagicMock()

    def mock_weather(query, params):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (date(2026, 1, 1), 150.0, 150.0, 0.02),
            (date(2026, 2, 1), 180.0, 175.0, 0.03),
            (date(2026, 3, 1), 120.0, 125.0, -0.04),
        ]
        return mock_result

    session.execute.side_effect = mock_weather

    res = compute_phenological_stress(
        session=session,
        location_pcode="MDG11",  # Centre
        product_code="RICE_PADDY",
        as_of_date=date(2026, 3, 1),
        lookback_months=3,
    )

    assert res is not None
    assert abs(res["phenological_stress_index"]) < 0.10
    assert res["stress_category"] == "optimal"


# =========================================================================
# 3. CORRIDOR FRICTION UNIT TESTS
# =========================================================================


def test_corridor_friction_rn2():
    """Verify RN2 corridor transport cost and friction decomposition."""
    session = MagicMock()

    def mock_corridor(query, params):
        ind = params["indicator"]
        mock_result = MagicMock()
        if ind == "CORRIDOR_BASE_COST_RN2_TON_MGA":
            mock_result.fetchone.return_value = (
                42000.0,
                date(2026, 10, 1),
                "corridor_friction",
                "sha_base",
            )
        elif ind == "CORRIDOR_ROAD_FACTOR_RN2":
            mock_result.fetchone.return_value = (
                1.10,
                date(2026, 10, 1),
                "corridor_friction",
                "sha_road",
            )
        elif ind == "CORRIDOR_SECURITY_FRICTION_RN2_PCT":
            mock_result.fetchone.return_value = (
                5.0,
                date(2026, 10, 1),
                "corridor_friction",
                "sha_sec",
            )
        elif ind == "FUEL_DIESEL":
            mock_result.fetchone.return_value = (
                4900.0,
                date(2026, 10, 1),
                "omh_diesel",
                "sha_fuel",
            )
        else:
            mock_result.fetchone.return_value = None
        return mock_result

    session.execute.side_effect = mock_corridor

    res = compute_corridor_friction(session, "RN2", date(2026, 10, 1))

    assert res is not None
    assert res["corridor_code"] == "RN2"
    assert res["distance_km"] == 350
    assert res["base_cost_mga_mt"] == 42000.0
    assert res["road_factor"] == 1.10
    assert res["security_friction_pct"] == 5.0
    # Multiplier = 1.10 * 1.05 = 1.155 (+15.5%)
    assert res["total_friction_pct"] == 15.5
    # Effective Cost = 42000 * 1.155 = 48510.0 MGA/MT
    assert res["effective_cost_mga_mt"] == 48510.0
    assert res["effective_cost_mga_kg"] == 48.51
    assert res["status"] == "moderate_friction"
    assert len(res["provenance_records"]) == 3


def test_corridor_friction_critical_alert():
    """Verify that severe road and security breakdown triggers critical_friction status."""
    session = MagicMock()

    def mock_corridor(query, params):
        ind = params["indicator"]
        mock_result = MagicMock()
        if ind == "CORRIDOR_BASE_COST_RN34_TON_MGA":
            mock_result.fetchone.return_value = (
                55000.0,
                date(2026, 2, 1),
                "corridor_friction",
                "sha_base_34",
            )
        elif ind == "CORRIDOR_ROAD_FACTOR_RN34":
            mock_result.fetchone.return_value = (
                1.20,
                date(2026, 2, 1),
                "corridor_friction",
                "sha_road_34",
            )
        elif ind == "CORRIDOR_SECURITY_FRICTION_RN34_PCT":
            mock_result.fetchone.return_value = (
                15.0,
                date(2026, 2, 1),
                "corridor_friction",
                "sha_sec_34",
            )
        else:
            mock_result.fetchone.return_value = None
        return mock_result

    session.execute.side_effect = mock_corridor

    res = compute_corridor_friction(session, "RN34", date(2026, 2, 1))

    assert res is not None
    # Multiplier = 1.20 * 1.15 = 1.38 (+38%)
    assert res["total_friction_pct"] == 38.0
    assert res["status"] == "critical_friction"


def test_get_all_corridors_summary():
    """Verify summary returns all 3 key corridors."""
    session = MagicMock()

    def mock_corridor(query, params):
        ind = params["indicator"]
        mock_result = MagicMock()
        if "BASE_COST" in ind:
            mock_result.fetchone.return_value = (
                40000.0,
                date(2026, 10, 1),
                "corridor_friction",
                "sha_base",
            )
        else:
            mock_result.fetchone.return_value = (
                1.0,
                date(2026, 10, 1),
                "corridor_friction",
                "sha_other",
            )
        return mock_result

    session.execute.side_effect = mock_corridor

    summaries = get_all_corridors_summary(session, date(2026, 10, 1))
    assert len(summaries) == 3
    corridor_codes = [s["corridor_code"] for s in summaries]
    assert "RN2" in corridor_codes
    assert "RN4" in corridor_codes
    assert "RN34" in corridor_codes
