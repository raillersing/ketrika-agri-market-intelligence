"""Unit tests and Golden validation for World Bank RTFP Madagascar connector (CC1, CC2, T3.2, R1.8)."""

import hashlib
import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from ketrika.connectors.base import DiscoveredItem, RawArtifact, RunContext
from ketrika.connectors.records import PriceRecord
from ketrika.connectors.wb_rtfp_mdg import WB_RTFP_CSV_URL, WbRtfpMdgConnector
from ketrika.core.bronze import BronzeStore
from ketrika.core.registry import find_repo_root

FIXTURE_PATH = (
    find_repo_root() / "backend" / "tests" / "fixtures" / "wb_rtfp_mdg" / "wb_rtfp_mdg_sample.csv"
)

GOLDEN_PATH = (
    find_repo_root()
    / "backend"
    / "tests"
    / "golden"
    / "wb_rtfp_mdg"
    / "wb_rtfp_sample.expected.json"
)


@pytest.fixture
def wb_rtfp_fixture_bytes() -> bytes:
    with open(FIXTURE_PATH, "rb") as f:
        return f.read()


@pytest.fixture
def golden_expected() -> dict[str, Any]:
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


def test_wb_rtfp_parse_fixture(wb_rtfp_fixture_bytes: bytes) -> None:
    """CC1: Unit test verifying parsing of World Bank RTFP CSV fixture."""
    connector = WbRtfpMdgConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = wb_rtfp_fixture_bytes
    ctx = RunContext(source_id="wb_rtfp_mdg", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-rec-id",
        object_key="bronze/wb_rtfp_mdg/sample.csv",
        content_sha256="dummy-sha",
        mime_type="text/csv",
        url="http://example.com/wb_rtfp.csv",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    # 1. Verify count
    assert len(result.records) == 36
    assert len(result.issues) == 0

    price_records = [r for r in result.records if isinstance(r, PriceRecord)]
    assert len(price_records) == 36

    # 2. Strict T3.2 requirement: No imputed record has observed_or_imputed == 'observed'
    observed_recs = [r for r in price_records if r.observed_or_imputed == "observed"]
    imputed_recs = [r for r in price_records if r.observed_or_imputed == "imputed"]
    assert len(observed_recs) == 24
    assert len(imputed_recs) == 12

    for imp_r in imputed_recs:
        assert imp_r.observed_or_imputed != "observed"
        assert imp_r.confidence == 0.8
        assert imp_r.evidence.get("value_kind_raw") == "imputed" or imp_r.evidence.get(
            "price_observed_raw"
        ) in (None, "", "null")

    for obs_r in observed_recs:
        assert obs_r.observed_or_imputed == "observed"
        assert obs_r.confidence == 1.0
        assert obs_r.evidence.get("value_kind_raw") == "observed"

    # Imputed share check
    imputed_share = len(imputed_recs) / len(price_records)
    assert 0.32 <= imputed_share <= 0.35

    # 3. Verify commodities
    commodities = {r.product_raw for r in price_records}
    assert "Rice" in commodities
    assert "Maize" in commodities
    assert "Cassava" in commodities
    assert "Wheat" in commodities

    # 4. Verify markets
    markets = {r.location_raw for r in price_records}
    assert "Anosibe" in markets
    assert "Toamasina" in markets
    assert "Antsirabe" in markets
    assert "Mahajanga" in markets


def test_wb_rtfp_golden_test(wb_rtfp_fixture_bytes: bytes, golden_expected: dict[str, Any]) -> None:
    """CC2: Golden test comparing parsed records to manually annotated reference dataset.

    Ensures field accuracy >= 99% and record recall >= 98% across >= 30 values.
    """
    connector = WbRtfpMdgConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = wb_rtfp_fixture_bytes
    ctx = RunContext(source_id="wb_rtfp_mdg", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-golden-id",
        object_key="bronze/wb_rtfp_mdg/sample.csv",
        content_sha256="golden-sha",
        mime_type="text/csv",
        url="http://example.com/wb_rtfp.csv",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    expected_records = golden_expected["records"]
    price_records = [r for r in result.records if isinstance(r, PriceRecord)]

    assert len(expected_records) >= 30
    assert len(price_records) == len(expected_records)

    correct_fields = 0
    total_fields = 0

    for parsed, expected in zip(price_records, expected_records, strict=True):
        # Commodity
        total_fields += 1
        if parsed.product_raw == expected["commodity"]:
            correct_fields += 1

        # Unit
        total_fields += 1
        if parsed.unit_raw == expected["unit"]:
            correct_fields += 1

        # Actor level
        total_fields += 1
        if parsed.actor_level == expected["actor_level"]:
            correct_fields += 1

        # Price raw
        total_fields += 1
        if parsed.price_raw == expected["price_raw"]:
            correct_fields += 1

        # Price value
        total_fields += 1
        if parsed.price_value == expected["price_value"]:
            correct_fields += 1

        # Market
        total_fields += 1
        if parsed.evidence.get("market_name") == expected["market"]:
            correct_fields += 1

        # Period start
        total_fields += 1
        if parsed.period_start.isoformat() == expected["period_start"]:
            correct_fields += 1

        # Observed or imputed
        total_fields += 1
        if parsed.observed_or_imputed == expected["observed_or_imputed"]:
            correct_fields += 1

    accuracy = correct_fields / total_fields
    recall = len(price_records) / len(expected_records)

    assert accuracy >= 0.99, f"Field accuracy {accuracy:.2%} is below 99%"
    assert recall >= 0.98, f"Record recall {recall:.2%} is below 98%"


def test_wb_rtfp_unknown_flag_never_promoted_to_observed() -> None:
    """R1.8: Unknown value_kind is never promoted to observed, routed to review queue."""
    connector = WbRtfpMdgConnector()
    csv_content = b"""country,country_code,adm1_name,market_name,date,commodity,unit,currency,price_observed,price_imputed,value_kind
Madagascar,MDG,Analamanga,Anosibe,2024-03-01,Rice,kg,MGA,3200.0,3200.0,estimated_trend
"""
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = csv_content
    ctx = RunContext(source_id="wb_rtfp_mdg", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-unknown-flag",
        object_key="bronze/wb/unknown.csv",
        content_sha256="dummy-sha",
        mime_type="text/csv",
        url="http://example.com/wb.csv",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.records) == 0
    assert len(result.issues) == 1
    assert result.issues[0]["kind"] == "unknown_value_kind_needs_review"
    assert result.issues[0]["raw_value_kind"] == "estimated_trend"


def test_wb_rtfp_unresolved_location_needs_review() -> None:
    """R1.8: When both market_name and adm1_name are missing, never assign arbitrary default."""
    connector = WbRtfpMdgConnector()
    csv_content = b"""country,country_code,adm1_name,market_name,date,commodity,unit,currency,price_observed,price_imputed,value_kind
Madagascar,MDG,,,2024-03-01,Rice,kg,MGA,3200.0,3200.0,observed
"""
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = csv_content
    ctx = RunContext(source_id="wb_rtfp_mdg", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-no-location",
        object_key="bronze/wb/no_loc.csv",
        content_sha256="dummy-sha",
        mime_type="text/csv",
        url="http://example.com/wb.csv",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.records) == 0
    assert len(result.issues) == 1
    assert result.issues[0]["kind"] == "unresolved_location_needs_review"


def test_wb_rtfp_evidence_schema_c3_traceability(wb_rtfp_fixture_bytes: bytes) -> None:
    """R1.8 / C3: Traceability of source dependency (WFP/FAO) and forecast exclusion flag."""
    connector = WbRtfpMdgConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = wb_rtfp_fixture_bytes
    ctx = RunContext(source_id="wb_rtfp_mdg", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-trace-id",
        object_key="bronze/wb_rtfp_mdg/sample.csv",
        content_sha256="dummy-sha",
        mime_type="text/csv",
        url="http://example.com/wb_rtfp.csv",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    for record in result.records:
        assert isinstance(record, PriceRecord)
        ev = record.evidence
        assert ev.get("source_family") == "world_bank"
        assert ev.get("source_dependency") == "wfp_fao"
        if record.observed_or_imputed == "imputed":
            assert ev.get("is_forecast_or_estimated") is True
            assert record.confidence == 0.8
        else:
            assert ev.get("is_forecast_or_estimated") is False
            assert record.confidence == 1.0


def test_wb_rtfp_fetch_offline_into_bronze() -> None:
    """R1.8: Offline fetch copies local authentic fixture into BronzeStore."""
    connector = WbRtfpMdgConnector()
    mem_store: dict[str, bytes] = {}
    mock_bronze = MagicMock(spec=BronzeStore)

    def _put(source_id: str, content: bytes, mime_type: str, url: str) -> Any:
        sha = hashlib.sha256(content).hexdigest()
        key = f"{source_id}/test/{sha}.csv"
        mem_store[key] = content
        art = MagicMock()
        art.object_key = key
        art.content_sha256 = sha
        art.is_new = True
        return art

    mock_bronze.put.side_effect = _put
    ctx = RunContext(
        source_id="wb_rtfp_mdg",
        bronze_store=mock_bronze,
        offline=True,
    )
    item = DiscoveredItem(
        url=WB_RTFP_CSV_URL,
        partition_key="mdg_rtfp",
    )
    artifact = connector.fetch(item, ctx)
    assert artifact.object_key.startswith("wb_rtfp_mdg/")
    assert len(artifact.content_sha256) == 64
    assert artifact.mime_type == "text/csv"


def test_wb_rtfp_discover_flexible_targets() -> None:
    """R1.8: Discovery respects metadata file targets and fallback URL."""
    connector = WbRtfpMdgConnector()

    # Case 1: Default URL
    ctx_default = RunContext(source_id="wb_rtfp_mdg")
    items_default = list(connector.discover(ctx_default))
    assert len(items_default) == 1
    assert items_default[0].url == WB_RTFP_CSV_URL

    # Case 2: Explicit metadata file_url
    custom_url = "https://microdata.worldbank.org/downloads/custom_mdg_rtfp_2024.csv"
    ctx_custom = RunContext(source_id="wb_rtfp_mdg", metadata={"file_url": custom_url})
    items_custom = list(connector.discover(ctx_custom))
    assert len(items_custom) == 1
    assert items_custom[0].url == custom_url
    assert items_custom[0].partition_key == "custom_mdg_rtfp_2024"

    # Case 3: Explicit metadata file_urls (list)
    urls = [
        "https://microdata.worldbank.org/downloads/mdg_rtfp_2023.csv",
        "https://microdata.worldbank.org/downloads/mdg_rtfp_2024.csv",
    ]
    ctx_list = RunContext(source_id="wb_rtfp_mdg", metadata={"file_urls": urls})
    items_list = list(connector.discover(ctx_list))
    assert len(items_list) == 2
    assert [it.partition_key for it in items_list] == ["mdg_rtfp_2023", "mdg_rtfp_2024"]


def test_wb_rtfp_dynamic_catalog_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """R1.8: Dynamic catalog discovery finds editions with regex matching."""
    connector = WbRtfpMdgConnector()
    mock_engine = MagicMock()
    mock_edition = MagicMock()
    mock_edition.url = "https://microdata.worldbank.org/index.php/catalog/food-prices/download/mdg_food_prices_2024.csv"
    mock_edition.title = "Madagascar Food Prices 2024"
    mock_edition.published_at = None
    mock_engine.discover_html_editions.return_value = MagicMock(editions=[mock_edition])

    monkeypatch.setattr(
        "ketrika.connectors.wb_rtfp_mdg.CatalogDiscoveryEngine",
        lambda **kwargs: mock_engine,
    )

    ctx = RunContext(
        source_id="wb_rtfp_mdg",
        metadata={"catalog_url": "https://microdata.worldbank.org/index.php/catalog/food-prices"},
        offline=False,
    )
    items = list(connector.discover(ctx))
    assert len(items) == 1
    assert items[0].url == mock_edition.url
    assert items[0].partition_key == "mdg_food_prices_2024"


def test_wb_rtfp_market_missing_falls_back_to_adm1() -> None:
    """R1.8: When market is missing but adm1 is available, location_raw is set to adm1."""
    connector = WbRtfpMdgConnector()
    csv_content = b"""country,country_code,adm1_name,market_name,date,commodity,unit,currency,price_observed,price_imputed,value_kind
Madagascar,MDG,Analamanga,,2024-03-01,Rice,kg,MGA,3200.0,3200.0,observed
"""
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = csv_content
    ctx = RunContext(source_id="wb_rtfp_mdg", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-adm1-fallback",
        object_key="bronze/wb/adm1.csv",
        content_sha256="dummy-sha",
        mime_type="text/csv",
        url="http://example.com/wb.csv",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.records) == 1
    assert len(result.issues) == 0
    rec = result.records[0]
    assert isinstance(rec, PriceRecord)
    assert rec.location_raw == "Analamanga"


def test_wb_rtfp_parse_ignores_empty_and_corrupt_lines() -> None:
    """R1.8: Empty lines, comment lines and rows missing date/commodity are handled safely."""
    connector = WbRtfpMdgConnector()
    csv_content = b"""# Comment line
country,country_code,adm1_name,market_name,date,commodity,unit,currency,price_observed,price_imputed,value_kind

# Another comment
Madagascar,MDG,Analamanga,Anosibe,,Rice,kg,MGA,3200.0,3200.0,observed
Madagascar,MDG,Analamanga,Anosibe,2024-03-01,,kg,MGA,3200.0,3200.0,observed
Madagascar,MDG,Analamanga,Anosibe,2024-03-01,Rice,kg,MGA,invalid_price,invalid_price,observed
"""
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = csv_content
    ctx = RunContext(source_id="wb_rtfp_mdg", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-corrupt-lines",
        object_key="bronze/wb/corrupt.csv",
        content_sha256="dummy-sha",
        mime_type="text/csv",
        url="http://example.com/wb.csv",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    # The invalid_price row parses with price_val=None
    assert len(result.records) == 1
    rec = result.records[0]
    assert isinstance(rec, PriceRecord)
    assert rec.price_value is None

