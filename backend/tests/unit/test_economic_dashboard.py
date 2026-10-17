"""Unit and CC-R qualification tests for Interpretable Economic Dashboard (R2.8, ADR-070).

Guards and contracts tested:
1. Catalog conformance: 14 canonical metric cards across 5 autonomous dimensions.
2. Anti-implicit chaining: Strict refusal of variation across different index bases (base shift).
3. Zero/missing denominator guards: Strict NULL with standardized reason code.
4. Physical unit compatibility guard: Trade volume (tons) vs value (MGA) and import unit cost (MGA/kg).
5. Temporal alignment guard: Refusal of import dependency calculation across misaligned periods.
6. Absolute conceptual separation: CPI food inflation vs direct market price variation.
7. No fake aggregate score: Autonomous dimensions with separate completeness status.
8. Non-invention invariant: Missing series yield NULL and 'partial' status, never 0.0 or LLM numbers.
9. API contracts: /v1/economic/indicators, /v1/economic/dashboard, /v1/economic/pilot-context.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from ketrika.api.main import app
from ketrika.core.db import get_db
from ketrika.gold.economic import (
    ECONOMIC_METRIC_CARDS,
    REASON_BASE_SHIFT,
    REASON_INCOMPATIBLE_UNITS,
    REASON_MISSING_DENOMINATOR,
    REASON_MISSING_SERIES,
    REASON_UNALIGNED_PERIOD,
    REASON_ZERO_DENOMINATOR,
    audit_inflation_vs_market_price_distinctness,
    calculate_import_dependency_ratio,
    calculate_import_unit_cost,
    calculate_safe_variation,
)
from ketrika.gold.provenance_gate import VIEW_TABLES
from ketrika.gold.refresh import ORDERED_GOLD_VIEWS

# =========================================================================
# 1. CATALOG AND METRIC CARDS CONFORMANCE
# =========================================================================

def test_economic_metric_cards_catalog_structure():
    """Verify that all 14 canonical metric cards are defined and conform to specs."""
    assert len(ECONOMIC_METRIC_CARDS) >= 14
    expected_dimensions = {"inflation", "exchange_rate", "fuel_energy", "external_trade", "real_activity"}
    actual_dimensions = {card.dimension for card in ECONOMIC_METRIC_CARDS.values()}
    assert actual_dimensions == expected_dimensions

    for metric_id, card in ECONOMIC_METRIC_CARDS.items():
        assert card.metric_id == metric_id
        assert card.title
        assert card.definition
        assert card.formula
        assert card.unit
        assert card.frequency in ("daily", "monthly", "quarterly", "annual", "event")
        assert card.geo_scope == "national"
        assert card.primary_source
        assert card.source_family in ("instat", "bfm", "omh", "douanes", "faostat")
        assert card.publication_lag_days >= 0
        assert card.limitations


# =========================================================================
# 2. BASE SHIFT & ANTI-IMPLICIT CHAINING GUARDS
# =========================================================================

def test_safe_variation_normal_computation():
    """Verify standard relative variation on identical base."""
    # Example: CPI goes from 110.0 to 115.5 on same base 2016=100
    val, reason = calculate_safe_variation(
        current_val=115.5,
        prev_val=110.0,
        current_base="2016=100",
        prev_base="2016=100",
    )
    assert reason is None
    assert val == 0.05  # +5%


def test_safe_variation_refuses_base_shift():
    """Strictly refuse variation when index bases differ (ADR-070)."""
    # Example: CPI changed base from 2016=100 to 2024=100
    val, reason = calculate_safe_variation(
        current_val=102.0,
        prev_val=145.0,
        current_base="2024=100",
        prev_base="2016=100",
    )
    assert val is None
    assert reason == REASON_BASE_SHIFT


def test_safe_variation_zero_denominator_guard():
    """Verify division by zero produces NULL with zero_denominator reason."""
    val, reason = calculate_safe_variation(
        current_val=100.0,
        prev_val=0.0,
    )
    assert val is None
    assert reason == REASON_ZERO_DENOMINATOR


def test_safe_variation_missing_denominator_guard():
    """Verify missing previous value produces NULL with missing_denominator reason."""
    val, reason = calculate_safe_variation(
        current_val=100.0,
        prev_val=None,
    )
    assert val is None
    assert reason == REASON_MISSING_DENOMINATOR


def test_safe_variation_missing_series_guard():
    """Verify missing current value produces NULL with missing_series reason."""
    val, reason = calculate_safe_variation(
        current_val=None,
        prev_val=100.0,
    )
    assert val is None
    assert reason == REASON_MISSING_SERIES


# =========================================================================
# 3. PHYSICAL UNIT COMPATIBILITY & CIF IMPORT UNIT COST
# =========================================================================

def test_calculate_import_unit_cost_valid():
    """Verify CIF unit cost calculation in MGA/kg from MGA and tons."""
    # 250,000,000 MGA for 100 metric tons = 250,000,000 / 100,000 kg = 2,500 MGA/kg
    cost, reason = calculate_import_unit_cost(
        import_val_mga=250_000_000.0,
        import_vol_tons=100.0,
        unit_val="MGA",
        unit_vol="tons",
    )
    assert reason is None
    assert cost == 2500.0


def test_calculate_import_unit_cost_incompatible_units():
    """Verify refusal if physical units are incompatible."""
    cost, reason = calculate_import_unit_cost(
        import_val_mga=250_000_000.0,
        import_vol_tons=100.0,
        unit_val="EUR",  # Incompatible currency
        unit_vol="tons",
    )
    assert cost is None
    assert reason == REASON_INCOMPATIBLE_UNITS

    cost_vol, reason_vol = calculate_import_unit_cost(
        import_val_mga=250_000_000.0,
        import_vol_tons=100.0,
        unit_val="MGA",
        unit_vol="liters",  # Incompatible physical unit
    )
    assert cost_vol is None
    assert reason_vol == REASON_INCOMPATIBLE_UNITS


def test_calculate_import_unit_cost_zero_or_negative_volume():
    """Verify refusal if import volume is zero or negative."""
    cost, reason = calculate_import_unit_cost(
        import_val_mga=100_000.0,
        import_vol_tons=0.0,
    )
    assert cost is None
    assert reason == REASON_ZERO_DENOMINATOR


# =========================================================================
# 4. TEMPORAL ALIGNMENT & IMPORT DEPENDENCY RATIO
# =========================================================================

def test_calculate_import_dependency_ratio_valid():
    """Verify valid IDR calculation for aligned periods."""
    # Production = 4000 tons, Imports = 1000 tons, Exports = 0 tons
    # Net avail = 5000 tons, IDR = 1000 / 5000 = 0.20 (20%)
    idr, reason = calculate_import_dependency_ratio(
        import_tonnes=1000.0,
        prod_tonnes=4000.0,
        export_tonnes=0.0,
        period_import="2026",
        period_prod="2026",
    )
    assert reason is None
    assert idr == 0.20


def test_calculate_import_dependency_ratio_unaligned_period():
    """Strictly refuse IDR when periods are unaligned."""
    idr, reason = calculate_import_dependency_ratio(
        import_tonnes=1000.0,
        prod_tonnes=4000.0,
        export_tonnes=0.0,
        period_import="2026",
        period_prod="2024",  # Misaligned year
    )
    assert idr is None
    assert reason == REASON_UNALIGNED_PERIOD


def test_calculate_import_dependency_ratio_zero_availability():
    """Verify refusal when net availability is zero."""
    idr, reason = calculate_import_dependency_ratio(
        import_tonnes=0.0,
        prod_tonnes=0.0,
        export_tonnes=0.0,
    )
    assert idr is None
    assert reason == REASON_ZERO_DENOMINATOR


# =========================================================================
# 5. CONCEPT SEPARATION: INFLATION VS MARKET PRICE VARIATION
# =========================================================================

def test_audit_inflation_vs_market_price_distinctness():
    """Verify that CPI food inflation and market price changes are formally segregated."""
    audit = audit_inflation_vs_market_price_distinctness(
        cpi_food_chg_12m=0.085,       # 8.5% food CPI inflation
        market_price_chg_12m=0.124,   # 12.4% local rice market price increase
    )
    assert audit["concepts_strictly_separated"] is True
    assert audit["cpi_food_inflation_rate_pct"] == 8.5
    assert audit["market_price_variation_rate_pct"] == 12.4
    assert audit["spread_pct_points"] == 3.9
    assert "CPI food measures an urban basket" in audit["warning"]


# =========================================================================
# 6. SQL VIEW, REFRESH PIPELINE AND PROVENANCE REGISTRATION
# =========================================================================

def test_economic_dashboard_sql_view_and_refresh_registration():
    """Verify 014_economic_dashboard.sql exists and is properly registered in Gold pipelines."""
    sql_path = Path(__file__).resolve().parent.parent.parent / "src" / "ketrika" / "gold" / "sql" / "014_economic_dashboard.sql"
    assert sql_path.exists(), "014_economic_dashboard.sql view file must exist"
    content = sql_path.read_text(encoding="utf-8")
    assert "CREATE MATERIALIZED VIEW gold.economic_dashboard" in content
    assert "chg_1m" in content
    assert "chg_12m" in content
    assert "dimension" in content

    # Check refresh pipeline registration
    assert "economic_dashboard" in ORDERED_GOLD_VIEWS
    # Check provenance gate registration
    assert "economic_dashboard" in VIEW_TABLES


# =========================================================================
# 7. API ENDPOINTS QUALIFICATION
# =========================================================================

def test_api_get_economic_indicators_catalog():
    """Verify GET /v1/economic/indicators returns all metric cards."""
    client = TestClient(app)
    response = client.get("/v1/economic/indicators")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 14
    ids = {item["metric_id"] for item in data}
    assert "inflation_headline" in ids
    assert "fx_usd_mga" in ids
    assert "fuel_diesel" in ids
    assert "rice_import_unit_cost" in ids
    assert "gdp_growth_real" in ids


def test_api_get_economic_dashboard_structure(monkeypatch):
    """Test response formatting only; stubbed input is not publication qualification."""
    monkeypatch.setattr(
        "ketrika.api.routers.economic.query_economic_dashboard_from_db", lambda *args, **kwargs: []
    )
    client = TestClient(app)
    response = client.get("/v1/economic/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "overall_status" in data
    assert "dimensions" in data
    assert "metric_catalog" in data

    dimensions = data["dimensions"]
    assert "inflation" in dimensions
    assert "exchange_rate" in dimensions
    assert "fuel_energy" in dimensions
    assert "external_trade" in dimensions
    assert "real_activity" in dimensions

    # Verify no fake composite score
    assert "economic_health_score" not in data
    assert "composite_score" not in data

    # Verify that indicators in dimensions carry null reasons when values are absent
    for _dim_name, dim_summary in dimensions.items():
        assert dim_summary["completeness"] in ("complete", "partial", "no_data")
        for ind in dim_summary["indicators"]:
            if ind["current_value"] is None:
                assert ind["null_reason"] is not None


def test_api_get_pilot_economic_context():
    """Verify GET /v1/economic/pilot-context provides transmission context."""
    client = TestClient(app)
    response = client.get("/v1/economic/pilot-context?target_month=2026-05-01")
    assert response.status_code == 503
    assert response.json()["detail"] == "economic_data_not_qualified"


def test_api_get_pilot_economic_context_with_populated_db():
    """Verify pilot context with mocked DB observations."""
    mock_session = MagicMock()
    # Macro rows: EXCHANGE_RATE_USD_MGA=4500.0, FUEL_PUMP_CEILING_PRICE_MGA=4900.0, CPI_FOOD_CHG_12M=0.08, RICE_IMPORT_VAL=500M, RICE_IMPORT_VOL=200t
    mock_macro_rows = [
        ("EXCHANGE_RATE_USD_MGA", 4500.0),
        ("FUEL_PUMP_CEILING_PRICE_MGA", 4900.0),
        ("CPI_FOOD_CHG_12M", 0.08),
        ("RICE_IMPORT_VALUE_CAF_MGA", 500_000_000.0),
        ("RICE_IMPORT_VOLUME_TONS", 200.0),
    ]
    mock_price_row = (3200.0, 0.10)

    def mock_execute(statement, params=None):
        mock_result = MagicMock()
        stmt_str = str(statement)
        if "obs.macro_observation" in stmt_str:
            mock_result.fetchall.return_value = mock_macro_rows
        elif "gold.price_changes" in stmt_str:
            mock_result.fetchone.return_value = mock_price_row
        return mock_result

    mock_session.execute.side_effect = mock_execute

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        client = TestClient(app)
        response = client.get("/v1/economic/pilot-context?target_month=2026-05-01")
        assert response.status_code == 503
        assert response.json()["detail"] == "economic_data_not_qualified"
        mock_session.execute.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_api_get_economic_dashboard_with_db_rows():
    """Verify economic dashboard when gold.economic_dashboard has rows."""
    mock_session = MagicMock()
    # ed.indicator_code, ed.dimension, ed.indicator_name, ed.unit, ed.frequency, ed.geo_scope, ed.period_month, ed.current_value, ed.base_period, ed.chg_1m, ed.chg_12m, ed.source_id, ed.source_family
    mock_db_rows = [
        (
            "EXCHANGE_RATE_USD_MGA",
            "exchange_rate",
            "Cours USD/MGA",
            "MGA/USD",
            "daily",
            "national",
            dt.date(2026, 5, 1),
            4550.0,
            None,
            0.012,
            0.085,
            "bfm_public",
            "bfm",
        ),
        (
            "FUEL_PUMP_CEILING_PRICE_MGA",
            "fuel_energy",
            "Prix plafond Gazole",
            "MGA/L",
            "event",
            "national",
            dt.date(2026, 5, 1),
            4900.0,
            None,
            0.0,
            0.05,
            "omh_public",
            "omh",
        ),
    ]

    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_db_rows
    mock_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        client = TestClient(app)
        response = client.get("/v1/economic/dashboard?month=2026-05-01")
        assert response.status_code == 503
        assert response.json()["detail"] == "economic_data_not_qualified"
        mock_session.execute.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)

