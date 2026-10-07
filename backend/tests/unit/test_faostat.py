"""Unit tests and Golden validation for FAOSTAT connector (CC1, CC2, T3.3)."""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from ketrika.connectors.base import RawArtifact, RunContext
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
