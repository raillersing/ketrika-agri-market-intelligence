"""Unit and CC-R qualification tests for Office Malgache des Hydrocarbures (OMH) connector (R2.7)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_httpserver import HTTPServer

from ketrika.connectors.base import DiscoveredItem, RawArtifact, RunContext
from ketrika.connectors.omh_public import (
    Connector as OmhPublicConnector,
)
from ketrika.connectors.omh_public import (
    clean_fuel_price,
    parse_french_date_text,
)
from ketrika.connectors.records import MacroRecord
from ketrika.connectors.registry import get_connector_class, list_registered_connectors
from ketrika.connectors.runner import load_macro_record_with_supersession
from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import MemoryBudgetBackend
from ketrika.core.policy import PolicyEngine
from ketrika.core.registry import load_sources

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "omh_public"
GOLDEN_PATH = (
    Path(__file__).resolve().parent.parent / "golden" / "omh_public" / "omh_sample.expected.json"
)


# ============================================================================
# 1. Metadata and Registry Governance Tests
# ============================================================================


def test_omh_public_registered_in_registry():
    """Verify omh_public is registered in connector registry and sources.yaml."""
    cls = get_connector_class("omh_public")
    assert cls is not None
    assert cls is OmhPublicConnector
    assert "omh_public" in list_registered_connectors()

    sources = {s.source_id: s for s in load_sources()}
    assert "omh_public" in sources
    spec = sources["omh_public"]
    assert spec.source_id == "omh_public"
    assert spec.source_family == "omh"
    assert spec.priority == "P1"
    assert spec.status == "active"
    assert spec.cadence == "monthly"
    assert spec.collection_cadence == "monthly"
    assert spec.observation_cadence == "event"
    assert spec.publication_cadence == "event"


def test_omh_public_connector_constants():
    """Verify connector class attributes."""
    connector = OmhPublicConnector()
    assert connector.source_id == "omh_public"
    assert connector.source_family == "omh"
    assert connector.parser_version == "1.0.0"


# ============================================================================
# 2. Helpers and Price/Date Parsing Tests
# ============================================================================


def test_clean_fuel_price():
    """Verify parsing numeric price strings with spaces, commas, and plus signs."""
    assert clean_fuel_price("5 200") == 5200.0
    assert clean_fuel_price("4900,00") == 4900.0
    assert clean_fuel_price("+300") == 300.0
    assert clean_fuel_price(2430) == 2430.0

    with pytest.raises(ValueError):
        clean_fuel_price(None)


def test_parse_french_date_text():
    """Verify extraction of French date expressions."""
    assert parse_french_date_text("1er Juin 2026") == date(2026, 6, 1)
    assert parse_french_date_text("30 Mai 2026") == date(2026, 5, 30)
    assert parse_french_date_text("Application: 2026-06-01") == date(2026, 6, 1)
    assert parse_french_date_text("01/06/2026") == date(2026, 6, 1)
    assert parse_french_date_text("Texte sans aucune date") is None


# ============================================================================
# 3. Authentic CSV Ingestion, Golden Matching and Invariants
# ============================================================================


def test_parse_authentic_csv_fixture_and_golden_match():
    """Parse OMH CSV fixture and verify exact match with expected golden values."""
    csv_path = FIXTURES_DIR / "omh_bareme_carburants_2026.csv"
    assert csv_path.exists(), f"Missing fixture {csv_path}"

    with open(csv_path, "rb") as f:
        content = f.read()

    artifact = RawArtifact(
        source_record_id="rec_omh_csv",
        object_key="bronze/omh_public/bareme_2026.csv",
        content_sha256="fake_sha_omh",
        mime_type="text/csv",
        url="https://www.omh.mg/bareme_2026.csv",
        is_new=True,
        published_at=datetime(2026, 5, 30, 10, 0, tzinfo=UTC),
    )

    connector = OmhPublicConnector()
    mock_store = MagicMock()
    mock_store.get.return_value = content
    ctx = RunContext(source_id="omh_public", bronze_store=mock_store)

    result = connector.parse(artifact, ctx)

    assert len(result.issues) == 0
    assert len(result.records) == 6  # 3 products for Jan + 3 products for June

    # Read golden expectations
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        golden = json.load(f)

    records_by_key = {
        (r.indicator_code, r.period_start.isoformat()): r
        for r in result.records
        if isinstance(r, MacroRecord)
    }

    for sample in golden["sample_records"]:
        key = (sample["indicator_code"], sample["period_start"])
        assert key in records_by_key, f"Expected sample {key} not found"
        matched = records_by_key[key]
        assert matched.value == sample["value"]
        assert matched.unit == sample["unit"]
        assert matched.frequency == sample["frequency"]
        assert matched.evidence["primary_institution"] == sample["primary_institution"]
        assert matched.evidence["is_administered"] is True


def test_separation_of_effective_date_and_publication_date():
    """Invariant: effective_date (period_start) is strictly distinct from publication date."""
    csv_path = FIXTURES_DIR / "omh_bareme_carburants_2026.csv"
    with open(csv_path, "rb") as f:
        content = f.read()

    artifact = RawArtifact(
        source_record_id="rec_omh_csv",
        object_key="bronze/omh_public/bareme_2026.csv",
        content_sha256="fake_sha",
        mime_type="text/csv",
        url="https://www.omh.mg/bareme_2026.csv",
        is_new=True,
    )

    connector = OmhPublicConnector()
    mock_store = MagicMock()
    mock_store.get.return_value = content
    ctx = RunContext(source_id="omh_public", bronze_store=mock_store)

    result = connector.parse(artifact, ctx)

    june_records = [
        r
        for r in result.records
        if isinstance(r, MacroRecord) and r.period_start == date(2026, 6, 1)
    ]
    assert len(june_records) == 3

    for rec in june_records:
        # Effective application date is 2026-06-01
        assert rec.period_start == date(2026, 6, 1)
        assert rec.period_end == date(2026, 6, 1)
        # Publication date is 2026-05-30
        assert rec.evidence["effective_date"] == "2026-06-01"
        assert rec.evidence["published_date"] == "2026-05-30"
        assert rec.published_at.date() == date(2026, 5, 30)
        assert rec.evidence["effective_date"] != rec.evidence["published_date"]


# ============================================================================
# 4. Authentic Daily HTML Bulletin Ingestion
# ============================================================================


def test_parse_authentic_html_communique():
    """Parse OMH official communique HTML and verify price revision extraction."""
    html_path = FIXTURES_DIR / "omh_communique_revision_juin_2026.html"
    assert html_path.exists(), f"Missing fixture {html_path}"

    with open(html_path, "rb") as f:
        content = f.read()

    artifact = RawArtifact(
        source_record_id="rec_omh_html",
        object_key="bronze/omh_public/communique_2026_06.html",
        content_sha256="fake_sha_html",
        mime_type="text/html",
        url="https://www.omh.mg/communique_2026_06.html",
        is_new=True,
        published_at=datetime(2026, 5, 30, 14, 0, tzinfo=UTC),
    )

    connector = OmhPublicConnector()
    mock_store = MagicMock()
    mock_store.get.return_value = content
    ctx = RunContext(source_id="omh_public", bronze_store=mock_store)

    result = connector.parse(artifact, ctx)

    assert len(result.issues) == 0
    assert len(result.records) == 3

    records_by_ind = {r.indicator_code: r for r in result.records if isinstance(r, MacroRecord)}

    # Diesel: 5200 (former 4900, diff +300)
    diesel = records_by_ind["FUEL_DIESEL_CEILING_MGA"]
    assert diesel.value == 5200.0
    assert diesel.evidence["former_price"] == 4900.0
    assert diesel.evidence["price_change"] == 300.0
    assert diesel.evidence["is_administered"] is True
    assert diesel.period_start == date(2026, 6, 1)

    # Super 95: 6250 (former 5900, diff +350)
    super95 = records_by_ind["FUEL_SUPER95_CEILING_MGA"]
    assert super95.value == 6250.0
    assert super95.evidence["former_price"] == 5900.0
    assert super95.evidence["price_change"] == 350.0

    # Kerosene: 2430 (frozen)
    kerosene = records_by_ind["FUEL_KEROSENE_CEILING_MGA"]
    assert kerosene.value == 2430.0
    assert kerosene.evidence["former_price"] == 2430.0
    assert kerosene.evidence["price_change"] == 0.0


# ============================================================================
# 5. Discovery, Fetch and Robustness Tests
# ============================================================================


def test_omh_catalog_discovery(
    monkeypatch: pytest.MonkeyPatch,
    httpserver: HTTPServer,
) -> None:
    """Verify dynamic discovery of OMH fuel price datasets via HTML catalog."""
    monkeypatch.setenv("KETRIKA_ALLOW_TEST_LOOPBACK", "1")
    httpserver.expect_request("/robots.txt").respond_with_data(
        "User-agent: *\nDisallow:\n", status=200
    )

    catalog_html = """
    <html>
      <head><title>Office Malgache des Hydrocarbures</title></head>
      <body>
        <h1>Prix des Carburants</h1>
        <ul>
          <li><a href="/downloads/omh_bareme_carburants_2026.csv">Barème Officiel 2026 (CSV)</a></li>
          <li><a href="/communique_juin_2026.html">Communiqué de Révision Tarifaire</a></li>
          <li><a href="/contact">Contact</a></li>
        </ul>
      </body>
    </html>
    """
    httpserver.expect_request("/prix-des-carburants").respond_with_data(
        catalog_html, content_type="text/html"
    )

    policy = PolicyEngine()
    policy.set_robots_txt(httpserver.url_for("/"), "User-agent: *\nDisallow:\n")
    http_client = PoliteHttpClient(
        policy_engine=policy,
        budget_backend=MemoryBudgetBackend(),
        allow_loopback=True,
    )
    http_client.bind_source("omh_public", daily_request_budget=100, max_rps=10.0)

    connector = OmhPublicConnector()
    ctx = RunContext(
        source_id="omh_public",
        http_client=http_client,
        policy_engine=policy,
        metadata={
            "catalog_url": httpserver.url_for("/prix-des-carburants"),
            "allow_loopback": True,
        },
    )

    discovered = list(connector.discover(ctx))
    assert len(discovered) == 2
    urls = [d.url for d in discovered]
    assert any("omh_bareme_carburants_2026.csv" in u for u in urls)
    assert any("communique_juin_2026.html" in u for u in urls)
    assert all(d.partition_key == "omh_prices" for d in discovered)


def test_omh_discovery_fallback():
    """Verify discovery gracefully falls back when catalog retrieval fails."""
    connector = OmhPublicConnector()
    ctx = RunContext(
        source_id="omh_public",
        metadata={"catalog_url": "http://invalid-omh-non-existent.mg/catalog"},
    )

    discovered = list(connector.discover(ctx))
    assert len(discovered) == 1
    assert discovered[0].partition_key == "omh_prices"
    assert discovered[0].hints.get("fallback") == "true"


def test_omh_fetch():
    """Verify fetch delegates to ctx.fetch_and_store with proper mime type."""
    connector = OmhPublicConnector()
    item = DiscoveredItem(
        url="https://www.omh.mg/bareme_2026.csv",
        partition_key="omh_prices",
        published_at=datetime.now(UTC),
        hints={"format": "csv"},
    )
    mock_ctx = MagicMock(spec=RunContext)
    expected_artifact = RawArtifact(
        source_record_id="rec_test",
        object_key="bronze/omh_public/test.csv",
        content_sha256="fake_sha",
        mime_type="text/csv",
        url=item.url,
        is_new=True,
    )
    mock_ctx.fetch_and_store.return_value = expected_artifact

    art = connector.fetch(item, mock_ctx)
    assert art == expected_artifact
    mock_ctx.fetch_and_store.assert_called_once_with(item, mime_type="text/csv")


def test_omh_parse_missing_content():
    """Verify parse reports issue when bronze store returns None."""
    connector = OmhPublicConnector()
    mock_store = MagicMock()
    mock_store.get.return_value = None
    ctx = RunContext(source_id="omh_public", bronze_store=mock_store)

    artifact = RawArtifact(
        source_record_id="rec_missing",
        object_key="bronze/omh_public/missing.csv",
        content_sha256="fake_sha",
        mime_type="text/csv",
        url="https://omh.mg/missing.csv",
        is_new=True,
    )

    res = connector.parse(artifact, ctx)
    assert len(res.issues) == 1
    assert res.issues[0]["kind"] == "bronze_artifact_not_found"
    assert len(res.records) == 0


def test_omh_parse_requires_bronze_store_when_no_content():
    """Verify ValueError is raised when artifact has no content and RunContext has no bronze store."""
    connector = OmhPublicConnector()
    ctx = RunContext(source_id="omh_public", bronze_store=None)
    artifact = RawArtifact(
        source_record_id="rec_none",
        object_key="bronze/omh_public/test.csv",
        content_sha256="fake_sha",
        mime_type="text/csv",
        url="https://omh.mg/test.csv",
        is_new=True,
    )
    with pytest.raises(ValueError, match="Bronze store is required"):
        connector.parse(artifact, ctx)


def test_omh_csv_edge_cases_skipped():
    """Verify CSV parser skips comments, unknown products and malformed rows."""
    csv_content = """# Comment line
date_effet,date_publication,acte_reglementaire,produit,prix_ancien,prix_plafond
2026-06-01,2026-05-30,Arrêté,UNKNOWN_FUEL,1000,2000
2026-06-01,2026-05-30,Arrêté,DIESEL,4900,invalid_price
invalid_date,2026-05-30,Arrêté,DIESEL,4900,5200
,2026-05-30,Arrêté,DIESEL,4900,5200
2026-06-01,2026-05-30,Arrêté,DIESEL,4900,5200
"""
    artifact = RawArtifact(
        source_record_id="rec_edge",
        object_key="bronze/omh_public/edge.csv",
        content_sha256="fake_sha",
        mime_type="text/csv",
        url="https://omh.mg/edge.csv",
        is_new=True,
    )
    mock_store = MagicMock()
    mock_store.get.return_value = csv_content.encode("utf-8")
    ctx = RunContext(source_id="omh_public", bronze_store=mock_store)

    connector = OmhPublicConnector()
    res = connector.parse(artifact, ctx)
    assert len(res.records) == 1
    assert res.records[0].indicator_code == "FUEL_DIESEL_CEILING_MGA"
    assert res.records[0].value == 5200.0


# ============================================================================
# 6. Database Mock Ingestion and Supersession
# ============================================================================


def test_omh_load_macro_record_insertion_and_idempotence():
    """Verify load_macro_record_with_supersession inserts and idempotently skips for OMH fuel ceiling."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None

    rec = MacroRecord(
        indicator_code="FUEL_DIESEL_CEILING_MGA",
        indicator_name="Prix Plafond Réglementé Gazole (MGA/L)",
        frequency="event",
        unit="MGA/L",
        geo_scope="national",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 1),
        value=5200.0,
        vintage="final",
    )

    import uuid

    sr_id = uuid.uuid4()
    action, obs_id = load_macro_record_with_supersession(
        session=mock_session,
        record=rec,
        source_id="omh_public",
        source_record_id=sr_id,
    )

    assert action == "inserted"
    assert obs_id is not None
    assert mock_session.add.called
    assert mock_session.flush.called

    # Idempotent skip
    mock_current = MagicMock()
    mock_current.value = 5200.0
    mock_current.vintage = "final"
    mock_current.observation_id = obs_id
    mock_session.execute.return_value.scalar_one_or_none.return_value = mock_current

    action2, obs_id2 = load_macro_record_with_supersession(
        session=mock_session,
        record=rec,
        source_id="omh_public",
        source_record_id=sr_id,
    )

    assert action2 == "idempotent_skipped"
    assert obs_id2 == obs_id
