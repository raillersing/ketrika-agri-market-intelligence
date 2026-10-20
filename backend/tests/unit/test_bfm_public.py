"""Unit and CC-R qualification tests for Banky Foiben'i Madagasikara (BFM) connector (R2.6)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_httpserver import HTTPServer

from ketrika.connectors.base import DiscoveredItem, RawArtifact, RunContext
from ketrika.connectors.bfm_public import (
    Connector as BfmPublicConnector,
)
from ketrika.connectors.bfm_public import (
    clean_rate_number,
    compute_inverse_exchange_rate,
    is_business_trading_day,
    parse_french_date_text,
)
from ketrika.connectors.records import MacroRecord
from ketrika.connectors.registry import get_connector_class, list_registered_connectors
from ketrika.connectors.runner import load_macro_record_with_supersession
from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import MemoryBudgetBackend
from ketrika.core.policy import PolicyEngine
from ketrika.core.registry import load_sources

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "bfm_public"
GOLDEN_PATH = (
    Path(__file__).resolve().parent.parent / "golden" / "bfm_public" / "bfm_sample.expected.json"
)


# ============================================================================
# 1. Metadata and Registry Governance Tests
# ============================================================================


def test_bfm_public_registered_in_registry():
    """Verify bfm_public is registered in connector registry and sources.yaml."""
    cls = get_connector_class("bfm_public")
    assert cls is not None
    assert cls is BfmPublicConnector
    assert "bfm_public" in list_registered_connectors()

    sources = {s.source_id: s for s in load_sources()}
    assert "bfm_public" in sources
    spec = sources["bfm_public"]
    assert spec.source_id == "bfm_public"
    assert spec.source_family == "bfm"
    assert spec.priority == "P1"
    assert spec.status == "active"
    assert spec.data_kinds == ["macro"]
    assert spec.cadence == "daily"


def test_bfm_public_connector_constants():
    """Verify connector class attributes."""
    connector = BfmPublicConnector()
    assert connector.source_id == "bfm_public"
    assert connector.source_family == "bfm"
    assert connector.parser_version == "1.0.0"


# ============================================================================
# 2. Helpers and Business Day Rules (Anti-Interpolation)
# ============================================================================


def test_is_business_trading_day():
    """Verify business days are strictly Monday-Friday (0-4), weekends are False."""
    assert is_business_trading_day(date(2026, 5, 4)) is True  # Monday
    assert is_business_trading_day(date(2026, 5, 5)) is True  # Tuesday
    assert is_business_trading_day(date(2026, 5, 6)) is True  # Wednesday
    assert is_business_trading_day(date(2026, 5, 7)) is True  # Thursday
    assert is_business_trading_day(date(2026, 5, 8)) is True  # Friday
    assert is_business_trading_day(date(2026, 5, 9)) is False  # Saturday
    assert is_business_trading_day(date(2026, 5, 10)) is False  # Sunday


def test_clean_rate_number():
    """Verify parsing French formatted numbers with spaces and commas."""
    assert clean_rate_number("4 625,50") == 4625.50
    assert clean_rate_number("5000,00") == 5000.00
    assert clean_rate_number("4645.50") == 4645.50
    assert clean_rate_number(4620) == 4620.0

    with pytest.raises(ValueError):
        clean_rate_number(None)


def test_compute_inverse_exchange_rate():
    """Verify documentary inverse rate computation and precision."""
    # 1 USD = 4620.50 MGA => 1 MGA = 1 / 4620.50 ≈ 0.00021643 USD
    rate = 4620.50
    inv = compute_inverse_exchange_rate(rate)
    assert inv == pytest.approx(1.0 / rate, rel=1e-8)
    assert round(inv, 8) == 0.00021643

    # Refuse non-positive rates
    with pytest.raises(ValueError, match="must be positive"):
        compute_inverse_exchange_rate(0)

    with pytest.raises(ValueError, match="must be positive"):
        compute_inverse_exchange_rate(-100)


def test_parse_french_date_text():
    """Verify French date string extraction in multiple formats."""
    assert parse_french_date_text("Séance du 18 Mai 2026") == date(2026, 5, 18)
    assert parse_french_date_text("Cotation du 04 mai 2026") == date(2026, 5, 4)
    assert parse_french_date_text("Date: 2026-05-18") == date(2026, 5, 18)
    assert parse_french_date_text("18/05/2026") == date(2026, 5, 18)
    assert parse_french_date_text("Texte sans aucune date") is None


# ============================================================================
# 3. Authentic CSV Ingestion, Golden Matching and Invariant Verification
# ============================================================================


def test_parse_authentic_csv_fixture_and_golden_match():
    """Parse BFM CSV fixture and verify exact match with expected golden values."""
    csv_path = FIXTURES_DIR / "bfm_cours_de_change_2026_mai.csv"
    assert csv_path.exists(), f"Missing fixture {csv_path}"

    with open(csv_path, "rb") as f:
        content = f.read()

    artifact = RawArtifact(
        source_record_id="rec_bfm_csv",
        object_key="bronze/bfm_public/cours_2026_05.csv",
        content_sha256="fake_sha_bfm",
        mime_type="text/csv",
        url="https://www.banky-foibe.mg/cours_2026_05.csv",
        is_new=True,
        published_at=datetime(2026, 5, 19, 9, 0, tzinfo=UTC),
    )

    connector = BfmPublicConnector()
    mock_store = MagicMock()
    mock_store.get.return_value = content
    ctx = RunContext(source_id="bfm_public", bronze_store=mock_store)

    result = connector.parse(artifact, ctx)

    assert len(result.issues) == 0
    assert len(result.records) > 0

    # Read golden expectations
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        golden = json.load(f)

    # 1. Verify all sample golden records are present with exact values
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
        assert matched.period_end.isoformat() == sample["period_start"]  # daily
        assert matched.evidence["primary_institution"] == sample["primary_institution"]

    # 2. Invariant: weekends and holidays must never be present (no silent forward-fill)
    all_observed_dates = {
        r.period_start.isoformat() for r in result.records if isinstance(r, MacroRecord)
    }
    for missing_date in golden["weekend_and_holiday_dates_must_be_missing"]:
        assert missing_date not in all_observed_dates, (
            f"Date {missing_date} was found in observations but should be absent (weekend/holiday)"
        )


def test_inverse_rate_calculation_in_parsed_records():
    """Verify evidence includes proven inverse exchange rate for USD/MGA."""
    csv_path = FIXTURES_DIR / "bfm_cours_de_change_2026_mai.csv"
    with open(csv_path, "rb") as f:
        content = f.read()

    artifact = RawArtifact(
        source_record_id="rec_bfm_csv",
        object_key="bronze/bfm_public/cours_2026_05.csv",
        content_sha256="fake_sha",
        mime_type="text/csv",
        url="https://www.banky-foibe.mg/cours_2026_05.csv",
        is_new=True,
    )

    connector = BfmPublicConnector()
    mock_store = MagicMock()
    mock_store.get.return_value = content
    ctx = RunContext(source_id="bfm_public", bronze_store=mock_store)

    result = connector.parse(artifact, ctx)

    usd_mid_recs = [
        r
        for r in result.records
        if isinstance(r, MacroRecord) and r.indicator_code == "EXCHANGE_RATE_USD_MGA"
    ]
    assert len(usd_mid_recs) > 0

    for rec in usd_mid_recs:
        assert "inverse_rate_usd_per_mga" in rec.evidence
        inv = rec.evidence["inverse_rate_usd_per_mga"]
        assert inv * rec.value == pytest.approx(1.0, rel=1e-5)


# ============================================================================
# 4. Authentic Daily HTML Bulletin Ingestion
# ============================================================================


def test_parse_authentic_html_daily_bulletin():
    """Parse BFM daily HTML bulletin and verify date and rates extraction."""
    html_path = FIXTURES_DIR / "bfm_bulletin_journalier_2026_05_18.html"
    assert html_path.exists(), f"Missing fixture {html_path}"

    with open(html_path, "rb") as f:
        content = f.read()

    artifact = RawArtifact(
        source_record_id="rec_bfm_html",
        object_key="bronze/bfm_public/bulletin_2026_05_18.html",
        content_sha256="fake_sha_html",
        mime_type="text/html",
        url="https://www.banky-foibe.mg/cours-du-jour",
        is_new=True,
        published_at=datetime(2026, 5, 18, 17, 0, tzinfo=UTC),
    )

    connector = BfmPublicConnector()
    mock_store = MagicMock()
    mock_store.get.return_value = content
    ctx = RunContext(source_id="bfm_public", bronze_store=mock_store)

    result = connector.parse(artifact, ctx)

    assert len(result.issues) == 0
    assert len(result.records) == 6  # USD (moyen, achat, vente) + EUR (moyen, achat, vente)

    records_by_ind = {r.indicator_code: r for r in result.records if isinstance(r, MacroRecord)}

    # Check USD values from HTML
    assert records_by_ind["EXCHANGE_RATE_USD_MGA"].value == 4645.50
    assert records_by_ind["EXCHANGE_RATE_USD_MGA_BUY"].value == 4625.00
    assert records_by_ind["EXCHANGE_RATE_USD_MGA_SELL"].value == 4666.00
    assert records_by_ind["EXCHANGE_RATE_USD_MGA"].period_start == date(2026, 5, 18)

    # Check EUR values from HTML
    assert records_by_ind["EXCHANGE_RATE_EUR_MGA"].value == 5030.00
    assert records_by_ind["EXCHANGE_RATE_EUR_MGA_BUY"].value == 5005.00
    assert records_by_ind["EXCHANGE_RATE_EUR_MGA_SELL"].value == 5055.00
    assert records_by_ind["EXCHANGE_RATE_EUR_MGA"].period_start == date(2026, 5, 18)


# ============================================================================
# 5. Discovery, Fetch and Robustness Tests
# ============================================================================


def test_bfm_catalog_discovery(
    monkeypatch: pytest.MonkeyPatch,
    httpserver: HTTPServer,
) -> None:
    """Verify dynamic discovery of BFM exchange rate datasets via HTML catalog."""
    monkeypatch.setenv("KETRIKA_ALLOW_TEST_LOOPBACK", "1")
    httpserver.expect_request("/robots.txt").respond_with_data(
        "User-agent: *\nDisallow:\n", status=200
    )

    catalog_html = """
    <html>
      <head><title>Marché Interbancaire de Devises - BFM</title></head>
      <body>
        <h1>Cours de Change BFM</h1>
        <ul>
          <li><a href="/downloads/bfm_cours_de_change_2026_mai.csv">Historique Mai 2026 (CSV)</a></li>
          <li><a href="/cours_du_jour.html">Séance du Jour</a></li>
          <li><a href="/a-propos">À propos</a></li>
        </ul>
      </body>
    </html>
    """
    httpserver.expect_request("/cours-de-change").respond_with_data(
        catalog_html, content_type="text/html"
    )

    policy = PolicyEngine()
    policy.set_robots_txt(httpserver.url_for("/"), "User-agent: *\nDisallow:\n")
    http_client = PoliteHttpClient(
        policy_engine=policy,
        budget_backend=MemoryBudgetBackend(),
        allow_loopback=True,
    )
    http_client.bind_source("bfm_public", daily_request_budget=100, max_rps=10.0)

    connector = BfmPublicConnector()
    ctx = RunContext(
        source_id="bfm_public",
        http_client=http_client,
        policy_engine=policy,
        metadata={
            "catalog_url": httpserver.url_for("/cours-de-change"),
            "allow_loopback": True,
        },
    )

    discovered = list(connector.discover(ctx))
    assert len(discovered) == 2
    urls = [d.url for d in discovered]
    assert any("bfm_cours_de_change_2026_mai.csv" in u for u in urls)
    assert any("cours_du_jour.html" in u for u in urls)
    assert all(d.partition_key == "bfm_rates" for d in discovered)


def test_bfm_discovery_fallback():
    """Verify discovery gracefully falls back when catalog retrieval fails."""
    connector = BfmPublicConnector()
    ctx = RunContext(
        source_id="bfm_public",
        metadata={"catalog_url": "http://invalid-non-existent-banky.mg/catalog"},
    )

    discovered = list(connector.discover(ctx))
    assert len(discovered) == 1
    assert discovered[0].partition_key == "bfm_rates"
    assert discovered[0].hints.get("fallback") == "true"


def test_bfm_fetch():
    """Verify fetch delegates to ctx.fetch_and_store with appropriate mime type."""
    connector = BfmPublicConnector()
    item = DiscoveredItem(
        url="https://www.banky-foibe.mg/cours_mai_2026.csv",
        partition_key="bfm_rates",
        published_at=datetime.now(UTC),
        hints={"format": "csv"},
    )
    mock_ctx = MagicMock(spec=RunContext)
    expected_artifact = RawArtifact(
        source_record_id="rec_test",
        object_key="bronze/bfm_public/test.csv",
        content_sha256="fake_sha",
        mime_type="text/csv",
        url=item.url,
        is_new=True,
    )
    mock_ctx.fetch_and_store.return_value = expected_artifact

    art = connector.fetch(item, mock_ctx)
    assert art == expected_artifact
    mock_ctx.fetch_and_store.assert_called_once_with(item, mime_type="text/csv")


def test_bfm_parse_missing_content():
    """Verify parse reports issue when bronze store returns None."""
    connector = BfmPublicConnector()
    mock_store = MagicMock()
    mock_store.get.return_value = None
    ctx = RunContext(source_id="bfm_public", bronze_store=mock_store)

    artifact = RawArtifact(
        source_record_id="rec_missing",
        object_key="bronze/bfm_public/missing.csv",
        content_sha256="fake_sha",
        mime_type="text/csv",
        url="https://banky-foibe.mg/missing.csv",
        is_new=True,
    )

    res = connector.parse(artifact, ctx)
    assert len(res.issues) == 1
    assert res.issues[0]["kind"] == "bronze_artifact_not_found"
    assert len(res.records) == 0


# ============================================================================
# 6. Database Mock Ingestion and Supersession
# ============================================================================


def test_bfm_load_macro_record_insertion_and_idempotence():
    """Verify load_macro_record_with_supersession inserts and idempotently skips for daily BFM rate."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None

    rec = MacroRecord(
        indicator_code="EXCHANGE_RATE_USD_MGA",
        indicator_name="Cours de Change USD/MGA Moyen",
        frequency="daily",
        unit="MGA",
        geo_scope="national",
        period_start=date(2026, 5, 4),
        period_end=date(2026, 5, 4),
        value=4620.50,
        vintage="final",
    )

    import uuid

    sr_id = uuid.uuid4()
    action, obs_id = load_macro_record_with_supersession(
        session=mock_session,
        record=rec,
        source_id="bfm_public",
        source_record_id=sr_id,
    )

    assert action == "inserted"
    assert obs_id is not None
    assert mock_session.add.called
    assert mock_session.flush.called

    # Idempotent skip
    mock_current = MagicMock()
    mock_current.value = 4620.50
    mock_current.vintage = "final"
    mock_current.observation_id = obs_id
    mock_session.execute.return_value.scalar_one_or_none.return_value = mock_current

    action2, obs_id2 = load_macro_record_with_supersession(
        session=mock_session,
        record=rec,
        source_id="bfm_public",
        source_record_id=sr_id,
    )

    assert action2 == "idempotent_skipped"
    assert obs_id2 == obs_id


def test_bfm_parse_requires_bronze_store_when_no_content():
    """Verify ValueError is raised when artifact has no content and RunContext has no bronze store."""
    connector = BfmPublicConnector()
    ctx = RunContext(source_id="bfm_public", bronze_store=None)
    artifact = RawArtifact(
        source_record_id="rec_none",
        object_key="bronze/bfm_public/test.csv",
        content_sha256="fake_sha",
        mime_type="text/csv",
        url="https://banky-foibe.mg/test.csv",
        is_new=True,
    )
    with pytest.raises(ValueError, match="Bronze store is required"):
        connector.parse(artifact, ctx)


def test_bfm_csv_parsing_weekend_and_unsupported_currency_skipped():
    """Verify CSV parser skips weekend rows and unsupported currencies (JPY, GBP)."""
    csv_content = """# Comment line
date,devise,cours_achat,cours_vente,cours_moyen
2026-05-09,USD,4600.00,4641.00,4620.50
2026-05-04,JPY,30.00,32.00,31.00
2026-05-04,USD,invalid_achat,4641.00,4620.50
invalid_date_format,USD,4600.00,4641.00,4620.50
,USD,4600.00,4641.00,4620.50
"""
    artifact = RawArtifact(
        source_record_id="rec_test_csv",
        object_key="bronze/bfm_public/edge.csv",
        content_sha256="fake_sha",
        mime_type="text/csv",
        url="https://banky-foibe.mg/edge.csv",
        is_new=True,
    )
    mock_store = MagicMock()
    mock_store.get.return_value = csv_content.encode("utf-8")
    ctx = RunContext(source_id="bfm_public", bronze_store=mock_store)

    connector = BfmPublicConnector()
    res = connector.parse(artifact, ctx)
    # Only the valid USD row on 2026-05-04 (moyen & vente) should be emitted
    assert len(res.records) == 2
    ind_codes = {r.indicator_code for r in res.records if isinstance(r, MacroRecord)}
    assert "EXCHANGE_RATE_USD_MGA" in ind_codes
    assert "EXCHANGE_RATE_USD_MGA_SELL" in ind_codes
    assert (
        "EXCHANGE_RATE_USD_MGA_BUY" not in ind_codes
    )  # because invalid_achat failed float conversion


def test_bfm_html_parsing_weekend_and_empty():
    """Verify HTML parser skips weekend bulletin date."""
    html_weekend = """
    <html>
      <body>
        <p class="date-cotation">Séance du 09 Mai 2026</p>
        <table>
          <tr><td>USD</td><td>Dollar</td><td>4600</td><td>4640</td><td>4620</td></tr>
        </table>
      </body>
    </html>
    """
    artifact = RawArtifact(
        source_record_id="rec_weekend",
        object_key="bronze/bfm_public/weekend.html",
        content_sha256="fake_sha",
        mime_type="text/html",
        url="https://banky-foibe.mg/weekend.html",
        is_new=True,
    )
    mock_store = MagicMock()
    mock_store.get.return_value = html_weekend.encode("utf-8")
    ctx = RunContext(source_id="bfm_public", bronze_store=mock_store)

    connector = BfmPublicConnector()
    res = connector.parse(artifact, ctx)
    assert len(res.records) == 0
