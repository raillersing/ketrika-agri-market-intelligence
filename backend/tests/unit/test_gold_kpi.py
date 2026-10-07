"""Unit tests for Gold KPIs and Market Health Score calculations (SPECS §16, MVP_EXECUTION_PLAN T5.2)."""

from __future__ import annotations

import pytest

from ketrika.gold.kpi import (
    calculate_affordability_score,
    calculate_availability_score,
    calculate_climate_risk_score,
    calculate_import_dependency_ratio,
    calculate_market_health_score,
    calculate_price_stability_score,
    calculate_robust_volatility,
    calculate_robust_z_score,
    calculate_variation,
)


# 1. Test KPI: calculate_variation (>= 3 cases)
def test_calculate_variation():
    # Case 1: Inflation (+20%)
    assert calculate_variation(3000.0, 2500.0) == 0.2000
    # Case 2: Deflation (-20%)
    assert calculate_variation(2400.0, 3000.0) == -0.2000
    # Case 3: Flat (0%)
    assert calculate_variation(2850.0, 2850.0) == 0.0000
    # Edge cases
    assert calculate_variation(3000.0, None) is None
    assert calculate_variation(3000.0, 0.0) is None
    assert calculate_variation(3000.0, -100.0) is None


# 2. Test KPI: calculate_robust_volatility (>= 3 cases)
def test_calculate_robust_volatility():
    # Case 1: Zero dispersion
    prices_flat = [2000.0, 2000.0, 2000.0, 2000.0, 2000.0]
    assert calculate_robust_volatility(prices_flat) == 0.0

    # Case 2: Known symmetric distribution (med=120, MAD=10 -> vol=10/120=0.0833)
    prices_known = [100.0, 110.0, 120.0, 130.0, 140.0]
    assert calculate_robust_volatility(prices_known) == pytest.approx(0.0833, abs=0.0001)

    # Case 3: High dispersion (med=300, MAD=100 -> vol=100/300=0.3333)
    prices_high = [100.0, 200.0, 300.0, 400.0, 500.0]
    assert calculate_robust_volatility(prices_high) == pytest.approx(0.3333, abs=0.0001)

    # Edge cases: < 3 observations
    assert calculate_robust_volatility([100.0, 110.0]) is None
    assert calculate_robust_volatility([]) is None


# 3. Test KPI: calculate_robust_z_score (>= 3 cases)
def test_calculate_robust_z_score():
    prices = [100.0, 110.0, 120.0, 130.0, 140.0]  # med=120, mad=10, 1.4826*mad=14.826
    # Case 1: Point at median -> z=0
    assert calculate_robust_z_score(120.0, prices) == 0.0

    # Case 2: Point above median (134.826 -> z = +1.0)
    assert calculate_robust_z_score(134.826, prices) == pytest.approx(1.0, abs=0.001)

    # Case 3: Point below median (105.174 -> z = -1.0)
    assert calculate_robust_z_score(105.174, prices) == pytest.approx(-1.0, abs=0.001)

    # Edge cases
    assert calculate_robust_z_score(100.0, [100.0, 100.0]) is None
    assert calculate_robust_z_score(100.0, [100.0, 100.0, 100.0]) == 0.0


# 4. Test KPI: calculate_import_dependency_ratio (>= 3 cases)
def test_calculate_import_dependency_ratio():
    # Case 1: Standard PPN case (50kt prod, 10kt imp, 1kt exp -> 10 / 59 = 0.1695)
    assert calculate_import_dependency_ratio(50000.0, 10000.0, 1000.0) == 0.1695

    # Case 2: 100% Import Dependent (0 prod, 5000 imp, 0 exp -> 5000 / 5000 = 1.0)
    assert calculate_import_dependency_ratio(0.0, 5000.0, 0.0) == 1.0000

    # Case 3: 0% Import Dependent (10000 prod, 0 imp, 2000 exp -> 0 / 8000 = 0.0)
    assert calculate_import_dependency_ratio(10000.0, 0.0, 2000.0) == 0.0000

    # Case 4: Net availability non-positive
    assert calculate_import_dependency_ratio(100.0, 0.0, 500.0) is None


# 5. Test Components: Price Stability S_p, Affordability A_f, Availability A_v, Climate R_c
def test_kpi_components():
    # Stability S_p: 100 * (1 - min(vol / 0.30, 1))
    assert calculate_price_stability_score(0.0) == 100.0
    assert calculate_price_stability_score(0.15) == 50.0
    assert calculate_price_stability_score(0.30) == 0.0
    assert calculate_price_stability_score(0.45) == 0.0
    assert calculate_price_stability_score(None) is None

    # Affordability A_f: 100 * (1 - min(max(chg_12m, 0) / 0.40, 1))
    assert calculate_affordability_score(0.0) == 100.0
    assert calculate_affordability_score(-0.10) == 100.0  # Deflation no penalty
    assert calculate_affordability_score(0.20) == 50.0  # +20% inflation
    assert calculate_affordability_score(0.40) == 0.0  # +40% inflation
    assert calculate_affordability_score(0.60) == 0.0  # Capped at 0
    assert calculate_affordability_score(None) is None

    # Availability A_v: sufficient=100, tight=50, shortage=0
    assert calculate_availability_score("sufficient") == 100.0
    assert calculate_availability_score("tight") == 50.0
    assert calculate_availability_score("shortage") == 0.0
    assert calculate_availability_score("unknown") is None
    assert calculate_availability_score(None) is None

    # Climate R_c: 100 * (1 - min(max(-rain_anom_3m, 0) / 0.50, 1))
    assert calculate_climate_risk_score(0.20) == 100.0  # Wet anomaly
    assert calculate_climate_risk_score(0.0) == 100.0  # Normal rain
    assert calculate_climate_risk_score(-0.25) == 50.0  # -25% drought
    assert calculate_climate_risk_score(-0.50) == 0.0  # -50% drought
    assert calculate_climate_risk_score(-0.75) == 0.0  # Extreme drought
    assert calculate_climate_risk_score(None) is None


# 6. Dedicated acceptance test: coverage < 0.5 -> score NULL (SPECS §16, MVP_EXECUTION_PLAN T5.2)
def test_market_health_score_coverage_threshold():
    # Case 1: Only stability present (weight = 0.30 < 0.50) -> composite_score MUST be None!
    res1 = calculate_market_health_score(score_stability=90.0)
    assert res1.coverage == 0.30
    assert res1.composite_score is None

    # Case 2: Only affordability present (weight = 0.25 < 0.50) -> composite_score MUST be None!
    res2 = calculate_market_health_score(score_affordability=80.0)
    assert res2.coverage == 0.25
    assert res2.composite_score is None

    # Case 3: Only climate present (weight = 0.20 < 0.50) -> composite_score MUST be None!
    res3 = calculate_market_health_score(score_climate=100.0)
    assert res3.coverage == 0.20
    assert res3.composite_score is None

    # Case 4: Stability (0.30) + Climate (0.20) = coverage 0.50 (>= 0.50):
    # S_p = 100.0, R_c = 50.0
    # Weighted sum = 100*0.30 + 50*0.20 = 30 + 10 = 40.0
    # Composite score = 40.0 / 0.50 = 80.0
    res4 = calculate_market_health_score(score_stability=100.0, score_climate=50.0)
    assert res4.coverage == 0.50
    assert res4.composite_score == 80.00
    assert res4.available_components == ["stability", "climate"]

    # Case 5: Stability (0.30) + Affordability (0.25) = coverage 0.55:
    # S_p = 100.0, A_f = 50.0
    # Weighted sum = 100*0.30 + 50*0.25 = 30 + 12.5 = 42.5
    # Composite score = 42.5 / 0.55 = 77.27
    res5 = calculate_market_health_score(score_stability=100.0, score_affordability=50.0)
    assert res5.coverage == 0.55
    assert res5.composite_score == 77.27

    # Case 6: All 4 components present: coverage = 1.00
    # S_p=80 (0.30), A_f=60 (0.25), A_v=100 (0.25), R_c=50 (0.20)
    # Sum = 24 + 15 + 25 + 10 = 74.0
    res6 = calculate_market_health_score(
        score_stability=80.0,
        score_affordability=60.0,
        score_availability=100.0,
        score_climate=50.0,
    )
    assert res6.coverage == 1.00
    assert res6.composite_score == 74.00
    assert set(res6.available_components) == {
        "stability",
        "affordability",
        "availability",
        "climate",
    }
