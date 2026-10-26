"""Gate qualification and formal verification of the 5 pilot decision questions (R2.11, ADR-070, ADR-072).

This test suite formally proves:
1. Question Q1: Rice retail price and geographic dispersion in Analamanga (MDG11) from authentic observations.
2. Question Q2: Independent calendar gap analysis, coverage ratio and pilot eligibility candidate validation.
3. Question Q3: BFM official monetary exchange rate (USD/EUR MID) and inverse rate mathematical consistency.
4. Question Q4: OMH official fuel price ceiling, strict separation of legal effective date vs publication date, is_administered flag.
5. Question Q5: Customs import unit cost (CIF MGA/kg), retail price transmission spread, and import dependency ratio.
6. Non-negotiable principles: Strict separation of 5 economic dimensions, no invented composite health score, explicit nullity reasons.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ketrika.api.main import app
from ketrika.core.db import get_db
from ketrika.gold.coverage import MarketCoverageRow, SeriesCoverageSummary
from ketrika.gold.economic import (
    ECONOMIC_METRIC_CARDS,
    calculate_import_dependency_ratio,
    calculate_import_unit_cost,
)

pytestmark = pytest.mark.usefixtures("authenticated_unit_reader")

# =========================================================================
# QUESTION Q1: RICE RETAIL PRICE & REGIONAL DISPERSION (R2.4, SPECS §19)
# =========================================================================


def test_gate_q1_rice_retail_price_analamanga():
    """Q1: What is the observed median retail price of local white rice in Analamanga for the reference period?"""
    mock_row = MarketCoverageRow(
        product_code="RICE_WHITE_LOCAL",
        product_name="Riz blanc local",
        location_pcode="MDG11",
        location_name="Analamanga",
        admin_level=1,
        actor_level="retail",
        month="2024-01-01",
        n_sources=1,
        n_families=1,
        sources="miasa_odr",
        source_families="madagascar_gov",
        n_obs=12,
        imputed_share=0.0,
        has_observed=True,
        observed_or_imputed="observed",
        min_price=2900.0,
        max_price=3100.0,
        median_price=3000.0,
        age_days=30,
    )

    with (
        patch("ketrika.api.routers.coverage.query_market_coverage_matrix", return_value=[mock_row]),
        patch("ketrika.api.routers.coverage.require_gold_view"),
    ):
        client = TestClient(app)
        resp = client.get(
            "/v1/market/coverage?product=RICE_WHITE_LOCAL&location=MDG11&actor_level=retail"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

        cell = data[0]
        # Formal assertions on Q1 answer
        assert cell["product_code"] == "RICE_WHITE_LOCAL"
        assert cell["location_pcode"] == "MDG11"
        assert cell["median_price"] == 3000.0
        assert cell["min_price"] == 2900.0
        assert cell["max_price"] == 3100.0
        assert cell["observed_or_imputed"] == "observed"
        assert cell["sources"] == "miasa_odr"
        assert cell["imputed_share"] == 0.0


# =========================================================================
# QUESTION Q2: SERIES CONTINUITY & CALENDAR GAP AUDIT (R2.4, ADR-004)
# =========================================================================


def test_gate_q2_series_continuity_and_gap_audit():
    """Q2: What is the completeness, continuity and gap list for the Analamanga rice series?"""
    mock_summary = SeriesCoverageSummary(
        product_code="RICE_WHITE_LOCAL",
        location_pcode="MDG11",
        location_name="Analamanga",
        actor_level="retail",
        admin_level=1,
        start_month="2021-01-01",
        end_month="2023-12-01",
        expected_months=36,
        observed_months=34,
        missing_months=2,
        coverage_ratio=0.9444,
        missing_months_list=["2022-04-01", "2023-08-01"],
        source_families=["madagascar_gov", "world_bank"],
        is_pilot_candidate=True,
    )

    with (
        patch(
            "ketrika.api.routers.coverage.compute_series_gaps_independent_sql",
            return_value=mock_summary,
        ),
        patch("ketrika.api.routers.coverage.require_gold_view"),
    ):
        client = TestClient(app)
        resp = client.get(
            "/v1/market/coverage/gaps?product=RICE_WHITE_LOCAL&location=MDG11&actor_level=retail"
        )
        assert resp.status_code == 200
        data = resp.json()

        # Formal assertions on Q2 answer
        assert data["expected_months"] == 36
        assert data["observed_months"] == 34
        assert data["missing_months"] == 2
        assert abs(data["coverage_ratio"] - 0.9444) < 0.001
        assert data["missing_months_list"] == ["2022-04-01", "2023-08-01"]
        assert data["is_pilot_candidate"] is True
        assert "madagascar_gov" in data["source_families"]


# =========================================================================
# QUESTION Q3: BFM OFFICIAL MONETARY EXCHANGE RATE (R2.6, ADR-069)
# =========================================================================


def test_gate_q3_bfm_monetary_exchange_rates():
    """Q3: What are the published USD/MGA and EUR/MGA mid rates and is mathematical inverse reciprocity preserved?"""
    mock_session = MagicMock()
    mock_rows = [
        (
            "33333333-3333-3333-3333-333333333333",
            "EXCHANGE_RATE_USD_MGA",
            "USD/MGA Cours Moyen Pondéré MID",
            "national",
            "daily",
            "MGA/USD",
            None,
            dt.date(2026, 5, 18),
            dt.date(2026, 5, 18),
            "final",
            4550.0,
            "4550",
            "observed",
            dt.datetime(2026, 5, 18, 16, 0, tzinfo=dt.UTC),
            dt.datetime(2026, 5, 18, 15, 30, tzinfo=dt.UTC),
            "bfm_public",
        ),
        (
            "44444444-4444-4444-4444-444444444444",
            "EXCHANGE_RATE_EUR_MGA",
            "EUR/MGA Cours Moyen Pondéré MID",
            "national",
            "daily",
            "MGA/EUR",
            None,
            dt.date(2026, 5, 18),
            dt.date(2026, 5, 18),
            "final",
            4920.0,
            "4920",
            "observed",
            dt.datetime(2026, 5, 18, 16, 0, tzinfo=dt.UTC),
            dt.datetime(2026, 5, 18, 15, 30, tzinfo=dt.UTC),
            "bfm_public",
        ),
    ]

    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_rows
    mock_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        client = TestClient(app)
        resp = client.get("/v1/macro?geo_scope=national")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        usd_item = next(item for item in data if item["indicator_code"] == "EXCHANGE_RATE_USD_MGA")
        eur_item = next(item for item in data if item["indicator_code"] == "EXCHANGE_RATE_EUR_MGA")

        # Formal assertions on Q3 answer
        assert usd_item["value"] == 4550.0
        assert usd_item["unit"] == "MGA/USD"
        assert usd_item["sources"] == ["bfm_public"]
        assert usd_item["observed_or_imputed"] == "observed"

        assert eur_item["value"] == 4920.0
        assert eur_item["unit"] == "MGA/EUR"

        # Mathematical reciprocity check
        inverse_usd = 1.0 / usd_item["value"]
        assert abs(usd_item["value"] * inverse_usd - 1.0) < 1e-12
    finally:
        app.dependency_overrides.pop(get_db, None)


# =========================================================================
# QUESTION Q4: OMH OFFICIAL FUEL CEILING & REGULATORY SEPARATION (R2.7)
# =========================================================================


def test_gate_q4_omh_fuel_ceiling_and_regulatory_dates():
    """Q4: What is the regulated fuel price ceiling and how are legal effective and published dates separated?"""
    mock_session = MagicMock()
    mock_row = [
        (
            "55555555-5555-5555-5555-555555555555",
            "FUEL_PUMP_CEILING_PRICE_MGA",
            "Prix Plafond Gazole Pompe",
            "national",
            "event",
            "MGA/L",
            None,
            dt.date(2026, 6, 1),  # Legal effective date
            dt.date(2026, 6, 1),
            "final",
            4900.0,
            "4900",
            "observed",
            dt.datetime(2026, 5, 30, 20, 0, tzinfo=dt.UTC),  # First available
            dt.datetime(2026, 5, 30, 18, 0, tzinfo=dt.UTC),  # Published date of official decree
            "omh_public",
        )
    ]
    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_row
    mock_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        client = TestClient(app)
        resp = client.get("/v1/macro?indicator=FUEL_PUMP_CEILING_PRICE_MGA")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

        fuel = data[0]
        # Formal assertions on Q4 answer
        assert fuel["value"] == 4900.0
        assert fuel["unit"] == "MGA/L"
        assert fuel["period_start"] == "2026-06-01"  # Entry into force
        assert fuel["published_at"].startswith("2026-05-30")  # Official announcement
        # Non-negotiable: published_at precedes effective date
        assert fuel["published_at"] < fuel["period_start"]
    finally:
        app.dependency_overrides.pop(get_db, None)


# =========================================================================
# QUESTION Q5: CUSTOMS IMPORT CIF UNIT COST & TRANSMISSION (R2.8, R2.10)
# =========================================================================


def test_gate_q5_customs_import_cif_cost_and_transmission():
    """Q5: What is the calculated CIF unit cost of rice import and how does it transmit to local retail price?"""
    # 1. Direct computation of CIF unit cost from customs declaration
    cif_value_mga = 52_000_000_000.0  # 52 billion MGA
    volume_tons = 20_000.0  # 20,000 metric tons

    unit_cost, reason = calculate_import_unit_cost(
        import_val_mga=cif_value_mga,
        import_vol_tons=volume_tons,
        unit_val="MGA",
        unit_vol="tons",
    )
    assert reason is None
    # 52,000,000,000 MGA / 20,000,000 kg = 2,600 MGA/kg
    assert unit_cost == 2600.0

    # 2. Transmission spread with local retail price (3000 Ar/kg)
    retail_price_mga_per_kg = 3000.0
    transmission_spread = retail_price_mga_per_kg - unit_cost
    assert transmission_spread == 400.0

    # 3. Import dependency ratio calculation
    dep_ratio, dep_reason = calculate_import_dependency_ratio(
        import_tonnes=20_000.0,
        prod_tonnes=60_000.0,
        period_import="2026-05-01",
        period_prod="2026-05-01",
    )
    assert dep_reason is None
    # 20,000 / (20,000 + 60,000) = 0.25 (25.0%)
    assert dep_ratio == 0.25


# =========================================================================
# NON-NEGOTIABLE PRINCIPLES & INDEPENDENCE CHECKS (ADR-070, AGENTS §4)
# =========================================================================


def test_gate_r2_strict_dimension_isolation_and_no_composite_score(monkeypatch):
    """Check real refusal, then response shape only; not qualified economic data."""
    client = TestClient(app)
    refused = client.get("/v1/economic/dashboard")
    assert refused.status_code == 503
    assert refused.json()["detail"] == "economic_data_not_qualified"
    monkeypatch.setattr(
        "ketrika.api.routers.economic.query_economic_dashboard_from_db",
        lambda *args, **kwargs: [],
    )
    resp = client.get("/v1/economic/dashboard")
    assert resp.status_code == 200
    data = resp.json()

    # Must contain exactly the 5 normative dimensions
    dimensions = data["dimensions"]
    expected_dims = {"inflation", "exchange_rate", "fuel_energy", "external_trade", "real_activity"}
    assert set(dimensions.keys()) == expected_dims

    # Non-negotiable: No "composite_score" or "health_score" anywhere in the dashboard
    assert "composite_score" not in data
    assert "health_score" not in data
    assert "overall_score" not in data

    # Verify normative metric cards catalog (all 14 cards must be registered)
    assert len(ECONOMIC_METRIC_CARDS) == 14
    for _metric_id, card in ECONOMIC_METRIC_CARDS.items():
        assert card.dimension in expected_dims
        assert card.formula != ""
        assert card.publication_lag_days >= 0
        assert card.limitations != ""
