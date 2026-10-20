"""Unit tests and Golden validation for WFP HDX Food Prices connector (CC1, CC2, T3.1, R1.7)."""

import hashlib
import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from ketrika.connectors.base import DiscoveredItem, RawArtifact, RunContext
from ketrika.connectors.records import PriceRecord
from ketrika.connectors.wfp_hdx_mdg import WfpHdxMdgConnector
from ketrika.core.bronze import BronzeStore
from ketrika.core.policy import PolicyEngine, PolicyStop
from ketrika.core.registry import find_repo_root

FIXTURE_PATH = (
    find_repo_root()
    / "backend"
    / "tests"
    / "fixtures"
    / "wfp_hdx_mdg"
    / "wfp_food_prices_mdg_sample.csv"
)

GOLDEN_PATH = (
    find_repo_root() / "backend" / "tests" / "golden" / "wfp_hdx_mdg" / "wfp_sample.expected.json"
)


@pytest.fixture
def wfp_fixture_bytes() -> bytes:
    with open(FIXTURE_PATH, "rb") as f:
        return f.read()


@pytest.fixture
def golden_expected() -> dict[str, Any]:
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


def test_wfp_hdx_parse_fixture(wfp_fixture_bytes: bytes) -> None:
    """CC1: Unit test verifying parsing of WFP HDX CSV fixture."""
    connector = WfpHdxMdgConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = wfp_fixture_bytes
    ctx = RunContext(source_id="wfp_hdx_mdg", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-rec-id",
        object_key="bronze/wfp_hdx_mdg/sample.csv",
        content_sha256="dummy-sha",
        mime_type="text/csv",
        url="http://example.com/wfp.csv",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    # 1. Verify count
    assert len(result.records) == 36
    assert len(result.issues) == 0

    price_records = [r for r in result.records if isinstance(r, PriceRecord)]
    assert len(price_records) == 36

    # 2. Verify actor_level mapping (Retail -> retail, Wholesale -> wholesale)
    retail_recs = [r for r in price_records if r.actor_level == "retail"]
    wholesale_recs = [r for r in price_records if r.actor_level == "wholesale"]
    assert len(retail_recs) == 33
    assert len(wholesale_recs) == 3

    # 3. Acceptance criterion: Prices for rice, maize and cassava present for >= 1 market
    commodities = {r.product_raw for r in price_records}
    assert "Rice (local)" in commodities
    assert "Rice (imported)" in commodities
    assert "Maize" in commodities
    assert "Cassava (fresh)" in commodities

    markets = {r.location_raw for r in price_records}
    assert "Anosibe" in markets
    assert "Bazar Be" in markets
    assert "Asabotsy" in markets

    # Check date extraction
    dates = {r.period_start.isoformat() for r in price_records}
    assert "2024-01-15" in dates
    assert "2024-02-15" in dates


def test_wfp_hdx_golden_test(wfp_fixture_bytes: bytes, golden_expected: dict[str, Any]) -> None:
    """CC2: Golden test comparing parsed records to manually annotated reference dataset.

    Ensures field accuracy >= 99% and record recall >= 98% across >= 30 values.
    """
    connector = WfpHdxMdgConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = wfp_fixture_bytes
    ctx = RunContext(source_id="wfp_hdx_mdg", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-golden-id",
        object_key="bronze/wfp_hdx_mdg/sample.csv",
        content_sha256="golden-sha",
        mime_type="text/csv",
        url="http://example.com/wfp.csv",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    expected_records = golden_expected["records"]
    price_records = [r for r in result.records if isinstance(r, PriceRecord)]

    # Verify minimum 30 values checked
    assert len(expected_records) >= 30
    assert len(price_records) == len(expected_records)

    correct_fields = 0
    total_fields = 0

    for parsed, expected in zip(price_records, expected_records, strict=True):
        # Check commodity
        total_fields += 1
        if parsed.product_raw == expected["commodity"]:
            correct_fields += 1

        # Check unit
        total_fields += 1
        if parsed.unit_raw == expected["unit"]:
            correct_fields += 1

        # Check actor_level
        total_fields += 1
        if parsed.actor_level == expected["actor_level"]:
            correct_fields += 1

        # Check price_raw
        total_fields += 1
        if parsed.price_raw == expected["price_raw"]:
            correct_fields += 1

        # Check price_value
        total_fields += 1
        if parsed.price_value == expected["price_value"]:
            correct_fields += 1

        # Check market
        total_fields += 1
        if parsed.evidence.get("market") == expected["market"]:
            correct_fields += 1

        # Check period_start
        total_fields += 1
        if parsed.period_start.isoformat() == expected["period_start"]:
            correct_fields += 1

    accuracy = correct_fields / total_fields
    recall = len(price_records) / len(expected_records)

    assert accuracy >= 0.99, f"Field accuracy {accuracy:.2%} is below 99%"
    assert recall >= 0.98, f"Record recall {recall:.2%} is below 98%"


def test_wfp_policy_stop_on_disabled_live_network() -> None:
    """R1.7: Any attempt to access live network when source is disabled raises PolicyStop."""
    connector = WfpHdxMdgConnector()
    policy = PolicyEngine()
    ctx = RunContext(
        source_id="wfp_hdx_mdg",
        policy_engine=policy,
        offline=False,
    )
    item = DiscoveredItem(
        url="https://data.humdata.org/dataset/wfp_food_prices_mdg.csv",
        partition_key="full_series",
    )
    with pytest.raises(PolicyStop) as exc_info:
        connector.fetch(item, ctx)
    assert "disabled" in str(exc_info.value).lower()


def test_wfp_unresolved_market_never_assigned_to_default_region() -> None:
    """R1.7: Row with unresolved/missing market produces issue, never defaulted to admin1 region."""
    connector = WfpHdxMdgConnector()
    csv_unresolved = b"""date,admin1,admin2,market,latitude,longitude,category,commodity,unit,priceflag,pricetype,currency,price,usdprice
#date,#adm1+name,#adm2+name,#loc+market+name,#geo+lat,#geo+lon,#item+type,#item+name,#item+unit,#item+price+flag,#item+price+type,#currency+code,#value+monetary,#value+usd
2024-03-15,Analamanga,Antananarivo Renivohitra,,,-18.91,47.53,cereals,Rice (local),KG,actual,Retail,MGA,3000,0.67
"""
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = csv_unresolved
    ctx = RunContext(source_id="wfp_hdx_mdg", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-unresolved",
        object_key="bronze/wfp/unresolved.csv",
        content_sha256="dummy-sha",
        mime_type="text/csv",
        url="http://example.com/unresolved.csv",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    # Market missing must NOT create PriceRecord with location_raw="Analamanga"
    assert len(result.records) == 0
    assert len(result.issues) == 1
    assert result.issues[0]["kind"] == "unresolved_market_needs_review"


def test_wfp_priceflag_distinguishes_observed_vs_imputed() -> None:
    """R1.7: priceflag=forecast produces observed_or_imputed='imputed' with reduced confidence."""
    connector = WfpHdxMdgConnector()
    csv_forecast = b"""date,admin1,admin2,market,latitude,longitude,category,commodity,unit,priceflag,pricetype,currency,price,usdprice
#date,#adm1+name,#adm2+name,#loc+market+name,#geo+lat,#geo+lon,#item+type,#item+name,#item+unit,#item+price+flag,#item+price+type,#currency+code,#value+monetary,#value+usd
2024-03-15,Analamanga,Antananarivo Renivohitra,Anosibe,-18.91,47.53,cereals,Rice (local),KG,actual,Retail,MGA,3000,0.67
2024-04-15,Analamanga,Antananarivo Renivohitra,Anosibe,-18.91,47.53,cereals,Rice (local),KG,forecast,Retail,MGA,3150,0.70
"""
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = csv_forecast
    ctx = RunContext(source_id="wfp_hdx_mdg", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-forecast",
        object_key="bronze/wfp/forecast.csv",
        content_sha256="dummy-sha",
        mime_type="text/csv",
        url="http://example.com/forecast.csv",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.records) == 2

    actual_rec = result.records[0]
    forecast_rec = result.records[1]

    assert isinstance(actual_rec, PriceRecord)
    assert isinstance(forecast_rec, PriceRecord)

    assert actual_rec.observed_or_imputed == "observed"
    assert actual_rec.confidence == 1.0

    assert forecast_rec.observed_or_imputed == "imputed"
    assert forecast_rec.confidence == 0.8


def test_wfp_fetch_offline_into_bronze() -> None:
    """R1.7: Offline fetch copies local authentic fixture into BronzeStore."""
    connector = WfpHdxMdgConnector()
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
        source_id="wfp_hdx_mdg",
        bronze_store=mock_bronze,
        offline=True,
    )
    item = DiscoveredItem(
        url="https://data.humdata.org/dataset/wfp_food_prices_mdg.csv",
        partition_key="full_series",
    )
    artifact = connector.fetch(item, ctx)
    assert artifact.object_key.startswith("wfp_hdx_mdg/")
    assert len(artifact.content_sha256) == 64
    assert artifact.mime_type == "text/csv"
