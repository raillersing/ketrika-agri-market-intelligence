"""Unit tests and Golden validation for World Bank RTFP Madagascar connector (CC1, CC2, T3.2)."""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.records import PriceRecord
from ketrika.connectors.wb_rtfp_mdg import WbRtfpMdgConnector
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
        # Verify evidence trace
        assert imp_r.evidence.get("value_kind_raw") == "imputed" or imp_r.evidence.get(
            "price_observed_raw"
        ) in (None, "", "null")

    for obs_r in observed_recs:
        assert obs_r.observed_or_imputed == "observed"
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
