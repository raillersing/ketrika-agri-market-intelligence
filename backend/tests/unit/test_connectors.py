"""Unit tests for Connector base, record schemas, and Dagster factory (SPECS §9)."""

from datetime import date

from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.records import (
    CpiRecord,
    EventRecord,
    PriceRecord,
    ProductionRecord,
    StockRecord,
    TradeFlowRecord,
    WeatherRecord,
)
from ketrika.pipelines.factory import build_source_assets


def test_price_record_natural_key():
    """Verify natural key generation for PriceRecord."""
    rec = PriceRecord(
        product_raw="Riz gasy",
        location_raw="Antananarivo",
        actor_level="retail",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        price_raw="2800",
        unit_raw="kg",
    )
    nk1 = rec.compute_natural_key("src_a")
    nk2 = rec.compute_natural_key("src_a")
    nk3 = rec.compute_natural_key("src_b")
    assert nk1 == nk2
    assert nk1 != nk3


def test_other_records_instantiation_and_keys():
    """Verify all 7 record types can be instantiated with valid attributes."""
    # 1. StockRecord
    stock = StockRecord(
        product_raw="Riz",
        location_raw="Toamasina",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        quantity_raw="500",
        stock_status="sufficient",
    )
    assert len(stock.compute_natural_key("test")) == 64

    # 2. TradeFlowRecord
    trade = TradeFlowRecord(
        flow="import",
        product_raw="Riz blanc",
        partner_raw="Pakistan",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        value_raw="1000000",
    )
    assert len(trade.compute_natural_key("test")) == 64

    # 3. ProductionRecord
    prod = ProductionRecord(
        product_raw="Paddy",
        location_raw="Alaotra",
        element="production_t",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        value_raw="450000",
    )
    assert len(prod.compute_natural_key("test")) == 64

    # 4. WeatherRecord
    weather = WeatherRecord(
        location_raw="MDG11",
        date=date(2025, 2, 1),
        variable="precip_mm",
        value=12.5,
    )
    assert weather.period_start == date(2025, 2, 1)
    assert len(weather.compute_natural_key("nasa")) == 64

    # 5. CpiRecord
    cpi = CpiRecord(
        series_code="CPI_FOOD",
        series_label="Alimentation",
        geo_scope="national",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        index_value_raw="112.4",
    )
    assert len(cpi.compute_natural_key("instat")) == 64

    # 6. EventRecord
    event = EventRecord(
        event_type="climate",
        title="Cyclone Batsirai",
        event_date=date(2022, 2, 5),
        severity=4,
    )
    assert event.period_start == date(2022, 2, 5)
    assert len(event.compute_natural_key("picm")) == 64


def test_build_source_assets():
    """Verify Dagster factory builds assets, checks and definitions."""
    source_assets = build_source_assets(DummyCsvConnector)
    assert source_assets.source_id == "dummy_csv"
    assert source_assets.bronze_asset is not None
    assert source_assets.silver_asset is not None
    assert len(source_assets.checks) >= 1
    defs = source_assets.all_definitions()
    assert len(defs) >= 3
