"""Unit tests for MarketSupplyConnector and legal physical quantity imports (R5.2, ADR-089, SPECS §27)."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.market_supply import MarketSupplyConnector
from ketrika.connectors.records import StockRecord
from ketrika.connectors.runner import load_stock_record_with_supersession
from ketrika.core.models.db import StockObservation
from ketrika.supply.contracts import QuantityTarget

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "market_supply"


class DummyBronzeStore:
    def __init__(self, data: bytes):
        self._data = data

    def get(self, object_key: str) -> bytes | None:
        return self._data


def test_market_supply_discovery():
    """Verify discovery produces standard institutional drops and supports metadata overrides."""
    connector = MarketSupplyConnector()
    assert connector.source_id == "market_supply"

    # Default discovery
    ctx = RunContext(source_id="market_supply", metadata={})
    items = list(connector.discover(ctx))
    assert len(items) == 2
    urls = [i.url for i in items]
    assert any("anosibe" in u for u in urls)
    assert any("ambatondrazaka" in u for u in urls)

    # Override discovery
    ctx_override = RunContext(
        source_id="market_supply",
        metadata={"urls": [{"url": "file:///custom/supply.csv", "partition_key": "custom_drop"}]},
    )
    custom_items = list(connector.discover(ctx_override))
    assert len(custom_items) == 1
    assert custom_items[0].partition_key == "custom_drop"


def test_parse_anosibe_supply_arrivals_and_stocks():
    """Verify parsing of authentic Anosibe market supply arrivals and stock inventory with unit conversions."""
    fixture_path = FIXTURES_DIR / "odr_approvisionnement_anosibe_2024.csv"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = MarketSupplyConnector()
    ctx = RunContext(
        source_id="market_supply",
        run_id="run-supply-anosibe",
        bronze_store=DummyBronzeStore(payload),
        metadata={},
    )
    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="file:///workspace/data/supply/odr_suivi_approvisionnement_anosibe_2024.csv",
        object_key="raw/market_supply/anosibe_2024.csv",
        mime_type="text/csv",
        content_sha256="mockshaanosibe",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.issues) == 0
    assert len(result.records) == 7

    arrivals = [r for r in result.records if r.target == QuantityTarget.INFLOW_ARRIVAL.value]
    stocks = [r for r in result.records if r.target == QuantityTarget.STOCK_INVENTORY.value]

    assert len(arrivals) == 4
    assert len(stocks) == 3

    # Check metric kg conversions
    # Row 1: 180 tonnes rice vary gasy = 180,000 kg
    r1 = arrivals[0]
    assert r1.product_raw == "rice_vary_gasy"
    assert r1.quantity_value == 180_000.0
    assert r1.market_code == "MKT_ANOSIBE"
    assert r1.measurement_mode == "measured_scale"

    # Row 3: 600 bags 50kg maize = 30,000 kg
    r3 = arrivals[2]
    assert r3.product_raw == "maize"
    assert r3.quantity_value == 30_000.0

    # Stock row: 450 tonnes = 450,000 kg
    s1 = stocks[0]
    assert s1.quantity_value == 450_000.0
    assert s1.measurement_mode == "declared_trader"


def test_parse_ambatondrazaka_basin_harvest_and_collection():
    """Verify parsing of Ambatondrazaka basin harvest volume and collection market inflows."""
    fixture_path = FIXTURES_DIR / "odr_collecte_ambatondrazaka_2024.csv"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = MarketSupplyConnector()
    ctx = RunContext(
        source_id="market_supply",
        run_id="run-supply-alaotra",
        bronze_store=DummyBronzeStore(payload),
        metadata={},
    )
    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="file:///workspace/data/supply/odr_suivi_collecte_ambatondrazaka_2024.csv",
        object_key="raw/market_supply/alaotra_2024.csv",
        mime_type="text/csv",
        content_sha256="mockshaalaotra",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.issues) == 0
    assert len(result.records) == 3

    harvests = [r for r in result.records if r.target == QuantityTarget.HARVEST_VOLUME.value]
    assert len(harvests) == 1
    assert harvests[0].quantity_value == 8_500_000.0  # 8500 tonnes in kg


def test_strict_rejection_of_corrupted_pii_payload():
    """Verify immediate and absolute rejection of any supply payload containing PII columns."""
    fixture_path = FIXTURES_DIR / "rejet_pii_interdit_2024.csv"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = MarketSupplyConnector()
    ctx = RunContext(
        source_id="market_supply",
        run_id="run-supply-pii-test",
        bronze_store=DummyBronzeStore(payload),
        metadata={},
    )
    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="file:///workspace/data/supply/rejet_pii_interdit_2024.csv",
        object_key="raw/market_supply/rejet_pii_2024.csv",
        mime_type="text/csv",
        content_sha256="mockshapiro",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    # Zero records must be extracted
    assert len(result.records) == 0
    # Must report PII violation issue
    assert len(result.issues) >= 1
    assert any("PII_REJECTION" in str(i) for i in result.issues)


def test_parse_json_supply_payload():
    """Verify parsing of structured JSON supply observations."""
    json_data = """{
        "observations": [
            {
                "target": "inflow_arrival",
                "measurement_mode": "measured_scale",
                "market_type": "regional_wholesale",
                "market_code": "MKT_MAROVOAY",
                "location_raw": "Marché Marovoay",
                "product_raw": "rice_paddy",
                "period_start": "2024-05-01",
                "period_end": "2024-05-07",
                "quantity_raw": 50.0,
                "unit_raw": "tonne",
                "stock_status": "sufficient"
            }
        ]
    }"""
    connector = MarketSupplyConnector()
    ctx = RunContext(
        source_id="market_supply",
        run_id="run-json",
        bronze_store=DummyBronzeStore(json_data.encode("utf-8")),
        metadata={},
    )
    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="file:///json/supply.json",
        object_key="raw/market_supply/supply.json",
        mime_type="application/json",
        content_sha256="mockshajson",
        is_new=True,
    )
    result = connector.parse(artifact, ctx)
    assert len(result.issues) == 0
    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.target == QuantityTarget.INFLOW_ARRIVAL.value
    assert rec.quantity_value == 50_000.0


def test_load_stock_record_with_supersession():
    """Verify loading StockRecord handles fresh insertion, idempotency, and non-destructive supersession."""
    rec1 = StockRecord(
        target=QuantityTarget.INFLOW_ARRIVAL.value,
        measurement_mode="measured_scale",
        market_type="terminal_wholesale",
        market_code="MKT_ANOSIBE",
        location_raw="Marché d'Anosibe",
        product_raw="rice_vary_gasy",
        period_start=date(2024, 5, 1),
        period_end=date(2024, 5, 7),
        quantity_raw="180",
        quantity_value=180_000.0,
        unit_raw="tonne",
        stock_status="sufficient",
        extraction_method="deterministic",
        confidence=1.0,
    )

    mock_session = MagicMock()
    source_rec_id = uuid.uuid4()

    # Case 1: Fresh insertion
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    action1, obs_id1 = load_stock_record_with_supersession(
        mock_session, rec1, "market_supply", source_rec_id
    )
    assert action1 == "inserted"
    assert obs_id1 is not None
    assert mock_session.add.call_count == 1

    # Case 2: Idempotent skip
    existing_obs = StockObservation(
        observation_id=obs_id1,
        source_record_id=source_rec_id,
        natural_key=rec1.compute_natural_key("market_supply"),
        product_raw=rec1.product_raw,
        location_raw=rec1.location_raw,
        period_start=rec1.period_start,
        period_end=rec1.period_end,
        quantity_raw=rec1.quantity_raw,
        quantity_value=rec1.quantity_value,
        unit_raw=rec1.unit_raw,
        stock_status=rec1.stock_status,
        target=rec1.target,
        measurement_mode=rec1.measurement_mode,
        market_code=rec1.market_code,
        superseded_by=None,
    )
    mock_session.execute.return_value.scalar_one_or_none.return_value = existing_obs
    mock_session.add.reset_mock()

    action2, obs_id2 = load_stock_record_with_supersession(
        mock_session, rec1, "market_supply", source_rec_id
    )
    assert action2 == "idempotent_skipped"
    assert obs_id2 == obs_id1
    mock_session.add.assert_not_called()

    # Case 3: Revision with changed quantity -> non-destructive supersession
    revised_rec = StockRecord(
        target=QuantityTarget.INFLOW_ARRIVAL.value,
        measurement_mode="measured_scale",
        market_type="terminal_wholesale",
        market_code="MKT_ANOSIBE",
        location_raw="Marché d'Anosibe",
        product_raw="rice_vary_gasy",
        period_start=date(2024, 5, 1),
        period_end=date(2024, 5, 7),
        quantity_raw="195",
        quantity_value=195_000.0,
        unit_raw="tonne",
        stock_status="sufficient",
        extraction_method="deterministic",
        confidence=1.0,
    )
    action3, obs_id3 = load_stock_record_with_supersession(
        mock_session, revised_rec, "market_supply", source_rec_id
    )
    assert action3 == "superseded"
    assert obs_id3 != obs_id1
    assert mock_session.add.call_count == 1
    # Check that update was executed to set superseded_by
    assert mock_session.execute.call_count >= 1
