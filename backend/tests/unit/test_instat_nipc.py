"""Unit tests and Golden validation for INSTAT NIPC connector (CC1, CC2, T3.5)."""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.instat_nipc import InstatNipcConnector
from ketrika.connectors.records import CpiRecord
from ketrika.core.bronze import BronzeStore
from ketrika.core.registry import find_repo_root

CSV_FIXTURE_PATH = (
    find_repo_root() / "backend" / "tests" / "fixtures" / "instat_nipc" / "nipc_sample.csv"
)

XLSX_FIXTURE_PATH = (
    find_repo_root() / "backend" / "tests" / "fixtures" / "instat_nipc" / "nipc_sample.xlsx"
)

GOLDEN_PATH = (
    find_repo_root() / "backend" / "tests" / "golden" / "instat_nipc" / "nipc_sample.expected.json"
)


@pytest.fixture
def csv_fixture_bytes() -> bytes:
    with open(CSV_FIXTURE_PATH, "rb") as f:
        return f.read()


@pytest.fixture
def xlsx_fixture_bytes() -> bytes:
    with open(XLSX_FIXTURE_PATH, "rb") as f:
        return f.read()


@pytest.fixture
def golden_expected() -> dict[str, Any]:
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


def test_instat_nipc_parse_csv(csv_fixture_bytes: bytes) -> None:
    """CC1: Unit test verifying CSV parsing and dynamic header location."""
    connector = InstatNipcConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = csv_fixture_bytes
    ctx = RunContext(source_id="instat_nipc", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-csv-id",
        object_key="bronze/instat_nipc/sample.csv",
        content_sha256="dummy-sha-csv",
        mime_type="text/csv",
        url="http://example.com/nipc_sample.csv",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    assert len(result.issues) == 0
    assert len(result.records) == 189

    cpi_records = [r for r in result.records if isinstance(r, CpiRecord)]
    assert len(cpi_records) == 189

    # Food CPI serie covers >= 5 years (T3.5 acceptance criterion)
    food_records = [r for r in cpi_records if r.series_code == "cpi_food"]
    assert len(food_records) == 63  # 63 monthly records = 5.25 years
    years = {r.period_start.year for r in food_records}
    assert len(years) >= 5, f"Expected >= 5 years, got {len(years)} ({years})"
    assert min(years) == 2019
    assert max(years) == 2024

    # Other series present
    series_codes = {r.series_code for r in cpi_records}
    assert series_codes == {"cpi_total", "cpi_food", "cpi_rice"}


def test_instat_nipc_parse_xlsx(xlsx_fixture_bytes: bytes) -> None:
    """CC1: Unit test verifying XLSX parsing with title preamble preceding header."""
    connector = InstatNipcConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = xlsx_fixture_bytes
    ctx = RunContext(source_id="instat_nipc", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-xlsx-id",
        object_key="bronze/instat_nipc/sample.xlsx",
        content_sha256="dummy-sha-xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        url="http://example.com/nipc_sample.xlsx",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    assert len(result.issues) == 0
    assert len(result.records) == 189

    food_records = [
        r for r in result.records if isinstance(r, CpiRecord) and r.series_code == "cpi_food"
    ]
    assert len(food_records) == 63


def test_instat_nipc_golden_test(csv_fixture_bytes: bytes, golden_expected: dict[str, Any]) -> None:
    """CC2: Golden test comparing parsed records to manually annotated reference dataset.

    Ensures field accuracy >= 99% and record recall >= 98% across >= 30 reference values.
    """
    connector = InstatNipcConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = csv_fixture_bytes
    ctx = RunContext(source_id="instat_nipc", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-golden-id",
        object_key="bronze/instat_nipc/sample.csv",
        content_sha256="golden-sha",
        mime_type="text/csv",
        url="http://example.com/nipc_sample.csv",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    expected_records = golden_expected["records"]

    assert len(expected_records) >= 30
    assert len(result.records) == len(expected_records)

    correct_fields = 0
    total_fields = 0

    for parsed, expected in zip(result.records, expected_records, strict=True):
        assert isinstance(parsed, CpiRecord)

        # series_code
        total_fields += 1
        if parsed.series_code == expected["series_code"]:
            correct_fields += 1

        # index_value
        total_fields += 1
        if parsed.index_value == expected["index_value"]:
            correct_fields += 1

        # period_start
        total_fields += 1
        if parsed.period_start.isoformat() == expected["period_start"]:
            correct_fields += 1

        # period_end
        total_fields += 1
        if parsed.period_end.isoformat() == expected["period_end"]:
            correct_fields += 1

        # geo_scope
        total_fields += 1
        if parsed.geo_scope == expected["geo_scope"]:
            correct_fields += 1

        # base_period
        total_fields += 1
        if parsed.base_period == expected["base_period"]:
            correct_fields += 1

    accuracy = correct_fields / total_fields
    recall = len(result.records) / len(expected_records)

    assert accuracy >= 0.99, f"Field accuracy {accuracy:.2%} is below 99%"
    assert recall >= 0.98, f"Record recall {recall:.2%} is below 98%"


def test_instat_nipc_dynamic_header_robustness() -> None:
    """Verify dynamic header location handles arbitrary preamble lines before header."""
    arbitrary_csv = (
        "RAPPORT STATISTIQUE MENSUEL N°42\n"
        "MINISTERE DE L'ECONOMIE ET DES FINANCES\n"
        "SECRETARIAT GENERAL\n"
        "DIRECTION GENERALE DU BUDGET ET DES STATISTIQUES\n"
        "AVERTISSEMENT: donnees provisoires soumises a revision\n"
        "\n"
        "\n"
        "Tableau 4.1: Indice National des Prix a la Consommation\n"
        "Source: Enquete mensuelle aupres des points de vente\n"
        "\n"
        "Mois,Indice General,Alimentation et Boissons,Riz de consommation\n"
        "2023-01,150.2,165.4,158.0\n"
        "2023-02,151.0,166.1,158.8\n"
    ).encode()

    connector = InstatNipcConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = arbitrary_csv
    ctx = RunContext(source_id="instat_nipc", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-dyn-id",
        object_key="bronze/instat_nipc/dynamic.csv",
        content_sha256="dummy-sha-dyn",
        mime_type="text/csv",
        url="http://example.com/dynamic.csv",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.issues) == 0
    # 2 months * 3 series = 6 records
    assert len(result.records) == 6
    food_recs = [
        r for r in result.records if isinstance(r, CpiRecord) and r.series_code == "cpi_food"
    ]
    assert len(food_recs) == 2
    assert food_recs[0].index_value == 165.4
    assert food_recs[1].index_value == 166.1
