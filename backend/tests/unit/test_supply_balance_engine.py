"""Unit tests for supply balance engine, mass conservation, and non-double-counting (R5.6, ADR-092, SPECS §27)."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.market_supply import MarketSupplyConnector
from ketrika.connectors.records import StockRecord, TradeFlowRecord
from ketrika.supply.balance import (
    BalanceType,
    ScenarioAssumption,
    SupplyBalanceEngine,
)
from ketrika.supply.contracts import QuantityTarget

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "market_supply"


class DummyBronzeStore:
    def __init__(self, data: bytes):
        self._data = data

    def get(self, object_key: str) -> bytes | None:
        return self._data


def test_mass_conservation_on_analytic_complete_case():
    """Verify physical mass conservation holds on an analytic scenario."""
    engine = SupplyBalanceEngine()

    start_date = date(2024, 5, 1)
    end_date = date(2024, 5, 10)  # 10 days

    records = [
        # Initial stock at period start
        StockRecord(
            target=QuantityTarget.STOCK_INVENTORY.value,
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="rice_vary_gasy",
            period_start=date(2024, 5, 1),
            period_end=date(2024, 5, 1),
            quantity_raw="100",
            quantity_value=100_000.0,
            unit_raw="tonne",
            extraction_method="deterministic",
            confidence=1.0,
        ),
        # Physical arrivals during interval
        StockRecord(
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="rice_vary_gasy",
            period_start=date(2024, 5, 2),
            period_end=date(2024, 5, 5),
            quantity_raw="300",
            quantity_value=300_000.0,
            unit_raw="tonne",
            extraction_method="deterministic",
            confidence=1.0,
        ),
    ]

    assumptions = [
        ScenarioAssumption(
            assumption_id="fao_loss_2024",
            parameter_name="post_harvest_loss_rate_pct",
            parameter_value=5.0,  # 5% of 300,000 = 15,000 kg
            unit="percent",
            rationale="FAO standard post-harvest loss rate for rice in sub-Saharan Africa",
        ),
        ScenarioAssumption(
            assumption_id="inscale_sales_2024",
            parameter_name="daily_market_sales_kg",
            parameter_value=25_000.0,  # 25,000 kg/day * 10 days = 250,000 kg
            unit="kg/day",
            rationale="Estimated wholesale dispatch rate for Antananarivo agglomeration",
        ),
    ]

    report = engine.simulate_scenario_balance(
        market_or_basin_code="MKT_ANOSIBE",
        product_raw="rice_vary_gasy",
        period_start=start_date,
        period_end=end_date,
        records=records,
        assumptions=assumptions,
    )

    assert report.balance_type == BalanceType.SCENARIO_SIMULATION
    assert report.observed_inflows_total_kg == 300_000.0
    assert report.initial_stock_kg == 100_000.0
    # Expected final stock: 100,000 + 300,000 - 250,000 - 15,000 = 135,000 kg
    assert report.final_stock_kg == 135_000.0
    assert report.mass_conservation_holds is True
    assert report.mass_discrepancy_kg == 0.0


def test_observed_partial_balance_unknown_component_remains_unknown():
    """Verify that unobserved retail sales and spoilage remain strictly None (never invented)."""
    engine = SupplyBalanceEngine()

    start_date = date(2024, 5, 1)
    end_date = date(2024, 5, 7)

    records = [
        # Stock observation
        StockRecord(
            target=QuantityTarget.STOCK_INVENTORY.value,
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="rice_vary_gasy",
            period_start=date(2024, 5, 1),
            period_end=date(2024, 5, 1),
            quantity_raw="450",
            quantity_value=450_000.0,
            unit_raw="tonne",
            extraction_method="deterministic",
            confidence=1.0,
        ),
        # Arrivals
        StockRecord(
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="rice_vary_gasy",
            period_start=date(2024, 5, 2),
            period_end=date(2024, 5, 3),
            quantity_raw="180",
            quantity_value=180_000.0,
            unit_raw="tonne",
            extraction_method="deterministic",
            confidence=1.0,
        ),
    ]

    report = engine.compute_observed_partial_balance(
        market_or_basin_code="MKT_ANOSIBE",
        product_raw="rice_vary_gasy",
        period_start=start_date,
        period_end=end_date,
        records=records,
    )

    assert report.balance_type == BalanceType.OBSERVED_PARTIAL
    assert report.has_unobserved_terms is True
    # Crucial rule: unobserved terms must remain None, not 0.0 !
    assert report.terms["outflow_sales"].quantity_kg is None
    assert report.terms["outflow_sales"].is_observed is False
    assert report.terms["post_harvest_losses"].quantity_kg is None
    assert report.terms["post_harvest_losses"].is_observed is False
    assert report.observed_inflows_total_kg == 180_000.0
    assert report.initial_stock_kg == 450_000.0


def test_customs_trade_flows_vs_market_arrivals_double_count_hazard():
    """Verify detection and refusal of combining national customs trade flows with market arrivals."""
    engine = SupplyBalanceEngine()

    market_records = [
        StockRecord(
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="rice_imported",
            period_start=date(2024, 5, 1),
            period_end=date(2024, 5, 1),
            quantity_raw="50",
            quantity_value=50_000.0,
            unit_raw="tonne",
            extraction_method="deterministic",
            confidence=1.0,
        ),
    ]

    customs_records = [
        TradeFlowRecord(
            flow="import",
            hs_code="100630",
            product_raw="Riz semi-blanchi ou blanchi",
            partner_raw="Inde",
            partner_iso3="IND",
            period_start=date(2024, 5, 1),
            period_end=date(2024, 5, 31),
            net_mass_kg=25_000_000.0,  # 25,000 tonnes at port
            extraction_method="deterministic",
            confidence=1.0,
        ),
    ]

    alerts = engine.check_customs_vs_market_double_count(market_records, customs_records)
    assert len(alerts) >= 1
    assert "DOUBLE_COUNT_HAZARD" in alerts[0]
    assert "customs trade flows with physical market arrivals" in alerts[0]

    # Run report with customs records passed
    report = engine.compute_observed_partial_balance(
        market_or_basin_code="MKT_ANOSIBE",
        product_raw="rice_imported",
        period_start=date(2024, 5, 1),
        period_end=date(2024, 5, 31),
        records=market_records,
        customs_records=customs_records,
    )
    assert len(report.double_counting_alerts) >= 1
    # Market inflows must NOT include the 25,000,000 kg from port!
    assert report.observed_inflows_total_kg == 50_000.0


def test_static_inventory_never_added_as_periodic_inflow():
    """Verify that static stock observations are strictly isolated from inflow arrivals."""
    engine = SupplyBalanceEngine()

    records = [
        # Stock observation of 200,000 kg
        StockRecord(
            target=QuantityTarget.STOCK_INVENTORY.value,
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="maize",
            period_start=date(2024, 5, 1),
            period_end=date(2024, 5, 1),
            quantity_raw="200",
            quantity_value=200_000.0,
            unit_raw="tonne",
            extraction_method="deterministic",
            confidence=1.0,
        ),
        # Physical arrival of 30,000 kg
        StockRecord(
            target=QuantityTarget.INFLOW_ARRIVAL.value,
            market_code="MKT_ANOSIBE",
            location_raw="Marché d'Anosibe",
            product_raw="maize",
            period_start=date(2024, 5, 2),
            period_end=date(2024, 5, 2),
            quantity_raw="30",
            quantity_value=30_000.0,
            unit_raw="tonne",
            extraction_method="deterministic",
            confidence=1.0,
        ),
    ]

    report = engine.compute_observed_partial_balance(
        market_or_basin_code="MKT_ANOSIBE",
        product_raw="maize",
        period_start=date(2024, 5, 1),
        period_end=date(2024, 5, 7),
        records=records,
    )

    # Inflows must be exactly 30,000 kg (stock 200,000 kg must NOT be counted as an inflow!)
    assert report.observed_inflows_total_kg == 30_000.0
    assert report.initial_stock_kg == 200_000.0


def test_supply_balance_on_authentic_odr_fixtures():
    """Verify supply balance computation on authentic ODR Anosibe dataset."""
    fixture_path = FIXTURES_DIR / "odr_approvisionnement_anosibe_2024.csv"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = MarketSupplyConnector()
    ctx = RunContext(
        source_id="market_supply",
        run_id="run-balance-odr",
        bronze_store=DummyBronzeStore(payload),
        metadata={},
    )
    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="file:///workspace/data/supply/odr_suivi_approvisionnement_anosibe_2024.csv",
        object_key="raw/market_supply/anosibe_2024.csv",
        mime_type="text/csv",
        content_sha256="mockshabalance",
        is_new=True,
    )
    result = connector.parse(artifact, ctx)
    assert len(result.records) == 7

    engine = SupplyBalanceEngine()

    # Week 1: 2024-05-01 to 2024-05-07 (ending inventory = 450 tonnes vary gasy)
    report_w1 = engine.compute_observed_partial_balance(
        market_or_basin_code="MKT_ANOSIBE",
        product_raw="rice_vary_gasy",
        period_start=date(2024, 5, 1),
        period_end=date(2024, 5, 7),
        records=result.records,
    )
    assert report_w1.balance_type == BalanceType.OBSERVED_PARTIAL
    assert report_w1.market_or_basin_code == "MKT_ANOSIBE"
    assert report_w1.observed_inflows_total_kg == 180_000.0  # 180 tonnes vary gasy
    assert report_w1.final_stock_kg == 450_000.0  # 450 tonnes ending inventory
    assert len(report_w1.double_counting_alerts) == 0

    # Week 2: 2024-05-08 to 2024-05-14 (initial inventory from 7th = 450t, arrivals = 210t, final = 520t)
    report_w2 = engine.compute_observed_partial_balance(
        market_or_basin_code="MKT_ANOSIBE",
        product_raw="rice_vary_gasy",
        period_start=date(2024, 5, 8),
        period_end=date(2024, 5, 14),
        records=result.records,
    )
    assert report_w2.initial_stock_kg == 450_000.0
    assert report_w2.observed_inflows_total_kg == 210_000.0
    assert report_w2.final_stock_kg == 520_000.0
    assert report_w2.delta_stock_kg == 70_000.0  # 520,000 - 450,000
