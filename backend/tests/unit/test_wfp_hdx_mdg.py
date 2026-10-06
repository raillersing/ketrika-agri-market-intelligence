"""Unit tests and Golden validation for WFP HDX Food Prices connector (CC1, CC2, T3.1)."""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.records import PriceRecord
from ketrika.connectors.wfp_hdx_mdg import WfpHdxMdgConnector
from ketrika.core.bronze import BronzeStore
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
