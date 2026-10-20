"""Unit tests and Golden validation for INSTAT NIPC connector (CC1, CC2, T3.5, R1.3, CC-R)."""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_httpserver import HTTPServer

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.instat_nipc import InstatNipcConnector
from ketrika.connectors.records import CpiRecord, PriceRecord
from ketrika.core.bronze import BronzeStore
from ketrika.core.http import PoliteHttpClient
from ketrika.core.policy import PolicyEngine
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

AUTHENTIC_HISTORIC_PATH = (
    find_repo_root()
    / "backend"
    / "tests"
    / "fixtures"
    / "instat_nipc"
    / "nipc_historique_2016_2023.xlsx"
)

AUTHENTIC_RECENT_PATH = (
    find_repo_root() / "backend" / "tests" / "fixtures" / "instat_nipc" / "nipc_recent_2024.xlsx"
)

AUTHENTIC_GOLDEN_PATH = (
    find_repo_root()
    / "backend"
    / "tests"
    / "golden"
    / "instat_nipc"
    / "nipc_authentic.expected.json"
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


@pytest.fixture
def authentic_historic_bytes() -> bytes:
    with open(AUTHENTIC_HISTORIC_PATH, "rb") as f:
        return f.read()


@pytest.fixture
def authentic_recent_bytes() -> bytes:
    with open(AUTHENTIC_RECENT_PATH, "rb") as f:
        return f.read()


@pytest.fixture
def authentic_golden() -> dict[str, Any]:
    with open(AUTHENTIC_GOLDEN_PATH, encoding="utf-8") as f:
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


def test_instat_nipc_authentic_corpus_golden(
    authentic_recent_bytes: bytes,
    authentic_golden: dict[str, Any],
) -> None:
    """CC-R / R1.3: Golden validation across authentic multi-sheet & recent editions.

    Verifies >= 30 reference values, accuracy >= 99% and recall >= 98%.
    Identifies at least two food series (cpi_food and cpi_rice).
    """
    connector = InstatNipcConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = authentic_recent_bytes
    ctx = RunContext(source_id="instat_nipc", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="auth-recent-id",
        object_key="bronze/instat_nipc/nipc_recent_2024.xlsx",
        content_sha256="auth-recent-sha",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        url="https://www.instat.mg/statistiques/prix-a-la-consommation/nipc_recent_2024.xlsx",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.issues) == 0
    assert len(result.records) == 27  # 9 months * 3 series

    # Identify at least two food series
    food_codes = {
        r.series_code
        for r in result.records
        if isinstance(r, CpiRecord) and r.series_code in ("cpi_food", "cpi_rice")
    }
    assert "cpi_food" in food_codes, "Food series (cpi_food) must be identified"
    assert "cpi_rice" in food_codes, "Rice series (cpi_rice) must be identified"

    # Match against reference golden subset for recent file
    expected_subset = [
        exp for exp in authentic_golden["records"] if exp["period_start"].startswith("2024")
    ]
    assert len(expected_subset) == 27

    correct_fields = 0
    total_fields = 0

    for parsed, expected in zip(result.records, expected_subset, strict=True):
        assert isinstance(parsed, CpiRecord)

        for field_name in ("series_code", "geo_scope", "base_period", "index_value"):
            total_fields += 1
            if getattr(parsed, field_name) == expected[field_name]:
                correct_fields += 1

        total_fields += 1
        if parsed.period_start.isoformat() == expected["period_start"]:
            correct_fields += 1

        total_fields += 1
        if parsed.period_end.isoformat() == expected["period_end"]:
            correct_fields += 1

    accuracy = correct_fields / total_fields
    recall = len(result.records) / len(expected_subset)

    assert accuracy >= 0.99, f"Accuracy {accuracy:.2%} is below 99%"
    assert recall >= 0.98, f"Recall {recall:.2%} is below 98%"


def test_instat_nipc_multi_sheet_and_base_change_preservation(
    authentic_historic_bytes: bytes,
) -> None:
    """CC-R / R1.3: Verify multi-sheet parsing and strict base change preservation.

    The base 2011=100 and base 2016=100 series must retain their respective base periods
    and MUST NEVER be spliced, converted, or concatenated silently.
    """
    connector = InstatNipcConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = authentic_historic_bytes
    ctx = RunContext(source_id="instat_nipc", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="auth-historic-id",
        object_key="bronze/instat_nipc/nipc_historique_2016_2023.xlsx",
        content_sha256="auth-historic-sha",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        url="https://www.instat.mg/statistiques/prix-a-la-consommation/nipc_historique_2016_2023.xlsx",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.issues) == 0

    cpi_recs = [r for r in result.records if isinstance(r, CpiRecord)]
    bases_found = {r.base_period for r in cpi_recs}
    assert bases_found == {"2016=100", "2011=100"}, (
        "Both 2016 and 2011 bases must be preserved explicitly"
    )

    recs_2011 = [r for r in cpi_recs if r.base_period == "2011=100"]
    recs_2016 = [r for r in cpi_recs if r.base_period == "2016=100"]

    assert len(recs_2011) == 180  # 60 months * 3 series
    assert len(recs_2016) > 400  # 96 months across 5 series

    # Check that 2011 base series ends at 2015-12 and 2016 base starts at 2016-01
    assert max(r.period_start.year for r in recs_2011) == 2015
    assert min(r.period_start.year for r in recs_2016) == 2016

    # Verify no silent splicing: no record with base 2016=100 has year < 2016
    for r in recs_2016:
        assert r.base_period == "2016=100"
        assert r.period_start.year >= 2016


def test_instat_nipc_missing_nd_values_handling(authentic_historic_bytes: bytes) -> None:
    """CC-R / R1.3: Verify ND / NA cells are skipped without converting to 0.0 or failing."""
    connector = InstatNipcConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = authentic_historic_bytes
    ctx = RunContext(source_id="instat_nipc", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="auth-nd-id",
        object_key="bronze/instat_nipc/nipc_historique_2016_2023.xlsx",
        content_sha256="auth-nd-sha",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        url="https://www.instat.mg/statistiques/prix-a-la-consommation/nipc_historique_2016_2023.xlsx",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    # In our fixture, Pain et Céréales had "ND" for the first 3 months (2016-01, 2016-02, 2016-03)
    bread_recs = [
        r
        for r in result.records
        if isinstance(r, CpiRecord) and r.series_code == "cpi_bread_cereals"
    ]
    bread_starts = {r.period_start.isoformat() for r in bread_recs}
    assert "2016-01-01" not in bread_starts
    assert "2016-02-01" not in bread_starts
    assert "2016-03-01" not in bread_starts
    assert "2016-04-01" in bread_starts

    # Ensure zero invalid values
    for r in result.records:
        assert isinstance(r, CpiRecord)
        assert r.index_value is not None
        assert r.index_value > 0.0


def test_instat_nipc_never_emits_market_price(authentic_recent_bytes: bytes) -> None:
    """CC-R / R1.3: Verify connector produces ONLY CpiRecord, NEVER PriceRecord (index != Ar/kg)."""
    connector = InstatNipcConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = authentic_recent_bytes
    ctx = RunContext(source_id="instat_nipc", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="auth-price-check-id",
        object_key="bronze/instat_nipc/nipc_recent_2024.xlsx",
        content_sha256="auth-price-sha",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        url="https://www.instat.mg/statistiques/prix-a-la-consommation/nipc_recent_2024.xlsx",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    for rec in result.records:
        assert isinstance(rec, CpiRecord)
        assert not isinstance(rec, PriceRecord)
        assert hasattr(rec, "base_period")
        assert not hasattr(rec, "price_value")


def test_instat_nipc_catalog_discovery(
    monkeypatch: pytest.MonkeyPatch,
    httpserver: HTTPServer,
) -> None:
    """CC-R / R1.3: Verify dynamic catalog discovery following HTML links to official spreadsheets."""
    monkeypatch.setenv("KETRIKA_ALLOW_TEST_LOOPBACK", "1")
    httpserver.expect_request("/robots.txt").respond_with_data(
        "User-agent: *\nDisallow:\n", status=200
    )

    catalog_html = """
    <html>
      <head><title>INSTAT - Statistiques des Prix à la Consommation</title></head>
      <body>
        <h1>Publications Récentes NIPC</h1>
        <div class="downloads">
          <a href="/downloads/nipc_bulletin_2024_09.xlsx">Télécharger Bulletin NIPC Septembre 2024 (Excel)</a>
          <a href="/downloads/nipc_bulletin_2024_08.xlsx">Télécharger Bulletin NIPC Août 2024 (Excel)</a>
          <a href="/mentions-legales">Mentions Légales</a>
        </div>
      </body>
    </html>
    """
    httpserver.expect_request("/statistiques/prix-a-la-consommation").respond_with_data(
        catalog_html, content_type="text/html"
    )

    from ketrika.core.http_budget import MemoryBudgetBackend

    policy = PolicyEngine()
    policy.set_robots_txt(httpserver.url_for("/"), "User-agent: *\nDisallow:\n")
    http_client = PoliteHttpClient(
        policy_engine=policy,
        budget_backend=MemoryBudgetBackend(),
        allow_loopback=True,
    )
    http_client.bind_source("instat_nipc", daily_request_budget=100, max_rps=10.0)

    connector = InstatNipcConnector()
    ctx = RunContext(
        source_id="instat_nipc",
        http_client=http_client,
        policy_engine=policy,
        metadata={
            "catalog_url": httpserver.url_for("/statistiques/prix-a-la-consommation"),
            "allow_loopback": True,
        },
    )

    discovered = list(connector.discover(ctx))
    assert len(discovered) == 2
    urls = [d.url for d in discovered]
    assert any("nipc_bulletin_2024_09.xlsx" in u for u in urls)
    assert any("nipc_bulletin_2024_08.xlsx" in u for u in urls)
    assert all(d.hints.get("publisher") == "INSTAT" for d in discovered)
    assert all(d.partition_key == "nipc_national" for d in discovered)
