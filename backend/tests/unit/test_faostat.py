"""Unit tests and Golden validation for FAOSTAT connector (CC1, CC2, T3.3)."""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from ketrika.connectors.base import DiscoveredItem, RawArtifact, RunContext
from ketrika.connectors.faostat import FaostatConnector
from ketrika.connectors.records import ProductionRecord, TradeFlowRecord
from ketrika.core.bronze import BronzeStore
from ketrika.core.registry import find_repo_root

FIXTURE_PATH = (
    find_repo_root() / "backend" / "tests" / "fixtures" / "faostat" / "faostat_sample.json"
)

GOLDEN_PATH = (
    find_repo_root() / "backend" / "tests" / "golden" / "faostat" / "faostat_sample.expected.json"
)


@pytest.fixture
def faostat_fixture_bytes() -> bytes:
    with open(FIXTURE_PATH, "rb") as f:
        return f.read()


@pytest.fixture
def golden_expected() -> dict[str, Any]:
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


def test_faostat_parse_fixture(faostat_fixture_bytes: bytes) -> None:
    """CC1: Unit test verifying parsing of FAOSTAT JSON fixture."""
    connector = FaostatConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = faostat_fixture_bytes
    ctx = RunContext(source_id="faostat", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-faostat-id",
        object_key="bronze/faostat/sample.json",
        content_sha256="dummy-sha",
        mime_type="application/json",
        url="http://example.com/faostat.json",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    # 1. Total records count
    assert len(result.issues) == 0
    assert len(result.records) == 36

    # 2. Production records validation
    prod_records = [r for r in result.records if isinstance(r, ProductionRecord)]
    assert len(prod_records) == 28

    # Rice paddy 20 years coverage (T3.3 acceptance criterion)
    rice_prod = [r for r in prod_records if r.product_raw == "Rice"]
    assert len(rice_prod) >= 20, f"Expected >= 20 years of Rice production, got {len(rice_prod)}"
    rice_years = {r.period_start.year for r in rice_prod}
    assert len(rice_years) >= 20
    assert min(rice_years) == 2004
    assert max(rice_years) == 2023

    # Other products present
    prod_products = {r.product_raw for r in prod_records}
    assert "Rice" in prod_products
    assert "Maize" in prod_products
    assert "Cassava" in prod_products

    # 3. Flags and observed_or_imputed mapping
    obs_count = sum(1 for r in prod_records if r.observed_or_imputed == "observed")
    imp_count = sum(1 for r in prod_records if r.observed_or_imputed == "imputed")
    # Expected in fixture: Rice 2020 (E), Rice 2022 (I), Maize 2023 (E) -> 3 imputed in production
    assert imp_count == 3
    assert obs_count == 25

    # 4. Trade records validation
    trade_records = [r for r in result.records if isinstance(r, TradeFlowRecord)]
    assert len(trade_records) == 8
    trade_products = {r.product_raw for r in trade_records}
    assert "Rice" in trade_products
    assert "Wheat flour" in trade_products
    assert "Sugar Raw Centrifugal" in trade_products
    assert "Oil, palm" in trade_products

    # Check conversion tonnes -> kg
    rice_trade_2021 = next(
        r for r in trade_records if r.product_raw == "Rice" and r.period_start.year == 2021
    )
    assert rice_trade_2021.weight_kg == 550_000_000.0  # 550,000 tonnes


def test_faostat_golden_test(faostat_fixture_bytes: bytes, golden_expected: dict[str, Any]) -> None:
    """CC2: Golden test comparing parsed records to manually annotated reference dataset.

    Ensures field accuracy >= 99% and record recall >= 98% across >= 30 values.
    """
    connector = FaostatConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = faostat_fixture_bytes
    ctx = RunContext(source_id="faostat", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-golden-id",
        object_key="bronze/faostat/sample.json",
        content_sha256="golden-sha",
        mime_type="application/json",
        url="http://example.com/faostat.json",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    expected_records = golden_expected["records"]

    assert len(expected_records) >= 30
    assert len(result.records) == len(expected_records)

    correct_fields = 0
    total_fields = 0

    for parsed, expected in zip(result.records, expected_records, strict=True):
        if expected["type"] == "production":
            assert isinstance(parsed, ProductionRecord)
            # product_raw
            total_fields += 1
            if parsed.product_raw == expected["product_raw"]:
                correct_fields += 1

            # element
            total_fields += 1
            if parsed.element == expected["element"]:
                correct_fields += 1

            # value
            total_fields += 1
            if parsed.value == expected["value"]:
                correct_fields += 1

            # unit_raw
            total_fields += 1
            if parsed.unit_raw == expected["unit_raw"]:
                correct_fields += 1

            # flag_raw
            total_fields += 1
            if parsed.flag_raw == expected["flag_raw"]:
                correct_fields += 1

            # period_start
            total_fields += 1
            if parsed.period_start.isoformat() == expected["period_start"]:
                correct_fields += 1

            # period_end
            total_fields += 1
            if parsed.period_end.isoformat() == expected["period_end"]:
                correct_fields += 1

            # observed_or_imputed
            total_fields += 1
            if parsed.observed_or_imputed == expected["observed_or_imputed"]:
                correct_fields += 1

        elif expected["type"] == "trade":
            assert isinstance(parsed, TradeFlowRecord)
            # flow
            total_fields += 1
            if parsed.flow == expected["flow"]:
                correct_fields += 1

            # product_raw
            total_fields += 1
            if parsed.product_raw == expected["product_raw"]:
                correct_fields += 1

            # weight_kg
            total_fields += 1
            if parsed.weight_kg == expected["weight_kg"]:
                correct_fields += 1

            # period_start
            total_fields += 1
            if parsed.period_start.isoformat() == expected["period_start"]:
                correct_fields += 1

            # period_end
            total_fields += 1
            if parsed.period_end.isoformat() == expected["period_end"]:
                correct_fields += 1

    accuracy = correct_fields / total_fields
    recall = len(result.records) / len(expected_records)

    assert accuracy >= 0.99, f"Field accuracy {accuracy:.2%} is below 99%"
    assert recall >= 0.98, f"Record recall {recall:.2%} is below 98%"


def test_faostat_paddy_vs_milled_never_converted_without_proof() -> None:
    """R1.9: Distinguish paddy from milled rice; never convert paddy to milled or apply implicit milling ratio."""
    connector = FaostatConnector()
    payload = {
        "data": [
            {
                "Item": "Rice, paddy",
                "Year": 2023,
                "Value": 4500000,
                "Unit": "t",
                "Flag": "A",
                "Element": "Production",
                "ElementCode": 5510,
                "DomainCode": "QCL",
            },
            {
                "Item": "Rice, milled",
                "Year": 2023,
                "Value": 300000,
                "Unit": "t",
                "Flag": "A",
                "Element": "Import Quantity",
                "ElementCode": 5610,
                "DomainCode": "TM",
            },
        ]
    }
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = json.dumps(payload).encode("utf-8")
    ctx = RunContext(source_id="faostat", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-paddy-milled",
        object_key="bronze/faostat/paddy_milled.json",
        content_sha256="dummy-sha",
        mime_type="application/json",
        url="http://example.com/faostat.json",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.records) == 2
    assert len(result.issues) == 0

    paddy_rec = next(r for r in result.records if isinstance(r, ProductionRecord))
    milled_rec = next(r for r in result.records if isinstance(r, TradeFlowRecord))

    # Product raw must remain strictly distinct
    assert paddy_rec.product_raw == "Rice, paddy"
    assert paddy_rec.value == 4500000.0
    assert paddy_rec.element == "production_t"

    assert milled_rec.product_raw == "Rice, milled"
    assert milled_rec.weight_kg == 300000.0 * 1000.0
    assert milled_rec.flow == "import"


def test_faostat_unknown_flag_never_promoted_to_observed() -> None:
    """R1.9: Unknown flag is never promoted to observed, produces issue and is marked imputed."""
    connector = FaostatConnector()
    payload = {
        "data": [
            {
                "Item": "Maize",
                "Year": 2023,
                "Value": 250000,
                "Unit": "t",
                "Flag": "Z",  # Unknown / unlisted flag
                "Element": "Production",
                "ElementCode": 5510,
                "DomainCode": "QCL",
            }
        ]
    }
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = json.dumps(payload).encode("utf-8")
    ctx = RunContext(source_id="faostat", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-unknown-flag",
        object_key="bronze/faostat/unknown.json",
        content_sha256="dummy-sha",
        mime_type="application/json",
        url="http://example.com/faostat.json",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.records) == 1
    assert len(result.issues) == 1
    assert result.issues[0]["kind"] == "unknown_faostat_flag_needs_review"
    assert result.issues[0]["flag"] == "Z"

    rec = result.records[0]
    assert isinstance(rec, ProductionRecord)
    # Crucial rule: must NOT be observed!
    assert rec.observed_or_imputed == "imputed"
    assert rec.confidence == 0.7


def test_faostat_fetch_offline_into_bronze() -> None:
    """R1.9: Offline fetch copies authentic fixture into BronzeStore."""
    connector = FaostatConnector()
    mem_store: dict[str, bytes] = {}
    mock_bronze = MagicMock(spec=BronzeStore)

    def _put(source_id: str, content: bytes, mime_type: str, url: str) -> Any:
        import hashlib

        sha = hashlib.sha256(content).hexdigest()
        key = f"{source_id}/test/{sha}.json"
        mem_store[key] = content
        art = MagicMock()
        art.object_key = key
        art.content_sha256 = sha
        art.is_new = True
        return art

    mock_bronze.put.side_effect = _put
    ctx = RunContext(
        source_id="faostat",
        bronze_store=mock_bronze,
        offline=True,
    )
    item = DiscoveredItem(
        url="https://fenixservices.fao.org/faostat/api/v1/en/data/QCL?area=129",
        partition_key="qcl",
    )
    artifact = connector.fetch(item, ctx)
    assert artifact.object_key.startswith("faostat/")
    assert len(artifact.content_sha256) == 64
    assert artifact.mime_type == "application/json"


def test_faostat_discover_flexible_endpoints() -> None:
    """R1.9: Discovery supports multi-domain, explicit api_urls and default target."""
    connector = FaostatConnector()

    # 1. Default QCL
    ctx_def = RunContext(source_id="faostat")
    items_def = list(connector.discover(ctx_def))
    assert len(items_def) == 1
    assert "QCL" in items_def[0].url

    # 2. Domain TM (Trade Matrix)
    ctx_tm = RunContext(source_id="faostat", metadata={"domain": "TM"})
    items_tm = list(connector.discover(ctx_tm))
    assert len(items_tm) == 1
    assert "TM?area=129" in items_tm[0].url

    # 3. Explicit api_urls (list)
    urls = [
        "https://fenixservices.fao.org/faostat/api/v1/en/data/QCL?area=129",
        "https://fenixservices.fao.org/faostat/api/v1/en/data/TM?area=129",
    ]
    ctx_list = RunContext(source_id="faostat", metadata={"api_urls": urls})
    items_list = list(connector.discover(ctx_list))
    assert len(items_list) == 2


def test_faostat_evidence_schema_c3(faostat_fixture_bytes: bytes) -> None:
    """R1.9: Traceability of source_family='un_fao' and forecast exclusion flag."""
    connector = FaostatConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = faostat_fixture_bytes
    ctx = RunContext(source_id="faostat", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-trace-id",
        object_key="bronze/faostat/sample.json",
        content_sha256="dummy-sha",
        mime_type="application/json",
        url="http://example.com/faostat.json",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    for record in result.records:
        assert record.evidence.get("source_family") == "un_fao"
        if isinstance(record, ProductionRecord):
            if record.observed_or_imputed == "imputed":
                assert record.evidence.get("is_forecast_or_estimated") is True
            else:
                assert record.evidence.get("is_forecast_or_estimated") is False
        elif isinstance(record, TradeFlowRecord):
            assert "is_forecast_or_estimated" in record.evidence

