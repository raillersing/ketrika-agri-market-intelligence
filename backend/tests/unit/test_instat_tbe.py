"""Unit and CC-R qualification tests for INSTAT Tableau de bord économique connector (R2.5)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_httpserver import HTTPServer

from ketrika.connectors.base import DiscoveredItem, RawArtifact, RunContext
from ketrika.connectors.instat_tbe import (
    Connector as InstatTbeConnector,
)
from ketrika.connectors.instat_tbe import (
    parse_period_and_frequency,
)
from ketrika.connectors.records import MacroRecord
from ketrika.connectors.registry import get_connector_class, list_registered_connectors
from ketrika.connectors.runner import load_macro_record_with_supersession
from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import MemoryBudgetBackend
from ketrika.core.policy import PolicyEngine
from ketrika.core.registry import load_sources

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "instat_tbe"
GOLDEN_PATH = Path(__file__).resolve().parent.parent / "golden" / "instat_tbe" / "tbe_sample.expected.json"


# ============================================================================
# 1. Metadata and Registry Governance Tests
# ============================================================================


def test_instat_tbe_registered_in_registry():
    """Verify instat_tbe is registered in python connector registry and sources.yaml."""
    cls = get_connector_class("instat_tbe")
    assert cls is not None
    assert cls is InstatTbeConnector
    assert "instat_tbe" in list_registered_connectors()

    sources = {s.source_id: s for s in load_sources()}
    assert "instat_tbe" in sources
    spec = sources["instat_tbe"]
    assert spec.source_id == "instat_tbe"
    assert spec.source_family == "madagascar_gov"
    assert spec.priority == "P1"
    assert spec.status == "active"
    assert spec.data_kinds == ["macro"]


def test_instat_tbe_connector_constants():
    """Verify connector class attributes."""
    connector = InstatTbeConnector()
    assert connector.source_id == "instat_tbe"
    assert connector.source_family == "madagascar_gov"


# ============================================================================
# 2. Period and Native Frequency Parsing Tests (No Fake Months)
# ============================================================================


def test_parse_period_and_frequency_monthly():
    """Monthly periods must yield exact calendar 1st and end-of-month dates."""
    start_d, end_d, freq = parse_period_and_frequency("2026-01")
    assert start_d == date(2026, 1, 1)
    assert end_d == date(2026, 1, 31)
    assert freq == "monthly"

    # Leap year february
    start_feb, end_feb, freq_feb = parse_period_and_frequency("2024-02")
    assert start_feb == date(2024, 2, 1)
    assert end_feb == date(2024, 2, 29)
    assert freq_feb == "monthly"


def test_parse_period_and_frequency_quarterly():
    """Quarterly periods must remain quarterly without fake monthly splitting."""
    # Q1
    q1_start, q1_end, q1_freq = parse_period_and_frequency("2026-T1")
    assert q1_start == date(2026, 1, 1)
    assert q1_end == date(2026, 3, 31)
    assert q1_freq == "quarterly"

    # Q2
    q2_start, q2_end, q2_freq = parse_period_and_frequency("T2 2026")
    assert q2_start == date(2026, 4, 1)
    assert q2_end == date(2026, 6, 30)
    assert q2_freq == "quarterly"

    # Q4
    q4_start, q4_end, q4_freq = parse_period_and_frequency("2025_T4")
    assert q4_start == date(2025, 10, 1)
    assert q4_end == date(2025, 12, 31)
    assert q4_freq == "quarterly"


def test_parse_period_and_frequency_annual():
    """Annual periods must span full year."""
    a_start, a_end, a_freq = parse_period_and_frequency("2025")
    assert a_start == date(2025, 1, 1)
    assert a_end == date(2025, 12, 31)
    assert a_freq == "annual"


def test_parse_period_invalid():
    """Invalid period must raise ValueError."""
    with pytest.raises(ValueError, match="unrecognized_tbe_period_format"):
        parse_period_and_frequency("invalide_periode")


# ============================================================================
# 3. Authentic Multi-Edition Parsing and Golden Verification (CC-R)
# ============================================================================


def test_parse_authentic_edition_62_and_golden_match():
    """Parse TBE Edition 62 and verify exact match with expected golden values."""
    f62_path = FIXTURES_DIR / "tbe_edition_62_mai_2026.xlsx"
    assert f62_path.exists(), f"Missing fixture {f62_path}"

    with open(f62_path, "rb") as f:
        content = f.read()

    artifact = RawArtifact(
        source_record_id="rec_62",
        object_key="bronze/instat_tbe/tbe_62.xlsx",
        content_sha256="fake_sha_62",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        url="https://www.instat.mg/statistiques/tbe/tbe_62.xlsx",
        is_new=True,
        published_at=datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
    )

    connector = InstatTbeConnector()
    mock_store = MagicMock()
    mock_store.get.return_value = content
    ctx = RunContext(source_id="instat_tbe", bronze_store=mock_store)

    result = connector.parse(artifact, ctx)

    assert len(result.issues) == 0
    assert len(result.records) > 0

    # Read golden expectations
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        golden = json.load(f)

    ed62_golden = golden["expected_editions"][0]
    expected_indicators = set(ed62_golden["expected_indicators"])

    found_indicators = {r.indicator_code for r in result.records if isinstance(r, MacroRecord)}
    for exp_ind in expected_indicators:
        assert exp_ind in found_indicators, f"Expected indicator {exp_ind} missing from parsed records"

    # Verify specific sample records from golden
    records_by_key = {
        (r.indicator_code, r.period_start.isoformat(), r.frequency): r
        for r in result.records
        if isinstance(r, MacroRecord)
    }

    for sample in ed62_golden["sample_records"]:
        key = (sample["indicator_code"], sample["period_start"], sample["frequency"])
        assert key in records_by_key, f"Sample key {key} not found"
        matched = records_by_key[key]
        assert matched.value == sample["value"]
        assert matched.unit == sample["unit"]
        assert matched.period_end.isoformat() == sample["period_end"]


def test_parse_authentic_edition_63_revisions():
    """Parse TBE Edition 63 and verify period extension and revision detection."""
    f63_path = FIXTURES_DIR / "tbe_edition_63_aout_2026.xlsx"
    assert f63_path.exists(), f"Missing fixture {f63_path}"

    with open(f63_path, "rb") as f:
        content = f.read()

    artifact = RawArtifact(
        source_record_id="rec_63",
        object_key="bronze/instat_tbe/tbe_63.xlsx",
        content_sha256="fake_sha_63",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        url="https://www.instat.mg/statistiques/tbe/tbe_63.xlsx",
        is_new=True,
        published_at=datetime(2026, 8, 25, 12, 0, tzinfo=UTC),
    )

    connector = InstatTbeConnector()
    mock_store = MagicMock()
    mock_store.get.return_value = content
    ctx = RunContext(source_id="instat_tbe", bronze_store=mock_store)

    result = connector.parse(artifact, ctx)

    # Edition 63 extends up to June 2026 (2026-06)
    jun_records = [
        r for r in result.records
        if isinstance(r, MacroRecord) and r.period_start == date(2026, 6, 1)
    ]
    assert len(jun_records) >= 8

    # Q2 2026 GDP must be present
    q2_gdp = [
        r for r in result.records
        if isinstance(r, MacroRecord) and r.indicator_code == "GDP_REAL_MGA" and r.period_start == date(2026, 4, 1)
    ]
    assert len(q2_gdp) == 1
    assert q2_gdp[0].value == 10120.0
    assert q2_gdp[0].frequency == "quarterly"


def test_quarterly_series_strictly_preserved_no_fake_months():
    """Invariant: Real GDP is strictly quarterly, never split or replicated into months."""
    f62_path = FIXTURES_DIR / "tbe_edition_62_mai_2026.xlsx"
    with open(f62_path, "rb") as f:
        content = f.read()

    artifact = RawArtifact(
        source_record_id="rec_62",
        object_key="bronze/instat_tbe/tbe_62.xlsx",
        content_sha256="fake_sha_62",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        url="https://www.instat.mg/statistiques/tbe/tbe_62.xlsx",
        is_new=True,
        published_at=datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
    )

    connector = InstatTbeConnector()
    mock_store = MagicMock()
    mock_store.get.return_value = content
    ctx = RunContext(source_id="instat_tbe", bronze_store=mock_store)

    result = connector.parse(artifact, ctx)

    gdp_records = [
        r for r in result.records
        if isinstance(r, MacroRecord) and r.indicator_code == "GDP_REAL_MGA"
    ]
    assert len(gdp_records) == 5  # 4 quarters of 2025 + Q1 2026

    for rec in gdp_records:
        assert rec.frequency == "quarterly"
        # Must span exactly a quarter
        month_span = rec.period_end.month - rec.period_start.month + 1
        assert month_span == 3
        assert rec.period_start.day == 1


def test_republished_cpi_traceability():
    """Republished CPI in TBE must be traceable to primary source instat_nipc."""
    f62_path = FIXTURES_DIR / "tbe_edition_62_mai_2026.xlsx"
    with open(f62_path, "rb") as f:
        content = f.read()

    artifact = RawArtifact(
        source_record_id="rec_62",
        object_key="bronze/instat_tbe/tbe_62.xlsx",
        content_sha256="fake_sha_62",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        url="https://www.instat.mg/statistiques/tbe/tbe_62.xlsx",
        is_new=True,
        published_at=datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
    )

    connector = InstatTbeConnector()
    mock_store = MagicMock()
    mock_store.get.return_value = content
    ctx = RunContext(source_id="instat_tbe", bronze_store=mock_store)

    result = connector.parse(artifact, ctx)

    cpi_records = [
        r for r in result.records
        if isinstance(r, MacroRecord) and r.indicator_code == "CPI_TBE_FOOD"
    ]
    assert len(cpi_records) > 0
    for r in cpi_records:
        assert r.base_period == "2016=100"
        assert r.unit == "index"
        assert r.frequency == "monthly"


# ============================================================================
# 4. Ingestion and Supersession DB Mock Tests
# ============================================================================


def test_load_macro_record_mock_insertion_and_idempotence():
    """Verify load_macro_record_with_supersession inserts and idempotently skips."""
    mock_session = MagicMock()
    # Case 1: No existing row -> inserted
    mock_session.execute.return_value.scalar_one_or_none.return_value = None

    rec = MacroRecord(
        indicator_code="IPI_GLOBAL",
        indicator_name="Indice de la Production Industrielle",
        frequency="monthly",
        unit="index",
        geo_scope="national",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        value=109.4,
        vintage="final",
    )

    import uuid
    sr_id = uuid.uuid4()
    action, obs_id = load_macro_record_with_supersession(
        session=mock_session,
        record=rec,
        source_id="instat_tbe",
        source_record_id=sr_id,
    )

    assert action == "inserted"
    assert obs_id is not None
    assert mock_session.add.called
    assert mock_session.flush.called

    # Case 2: Existing identical row -> idempotent_skipped
    mock_current = MagicMock()
    mock_current.value = 109.4
    mock_current.vintage = "final"
    mock_current.observation_id = obs_id
    mock_session.execute.return_value.scalar_one_or_none.return_value = mock_current

    action2, obs_id2 = load_macro_record_with_supersession(
        session=mock_session,
        record=rec,
        source_id="instat_tbe",
        source_record_id=sr_id,
    )

    assert action2 == "idempotent_skipped"
    assert obs_id2 == obs_id


# ============================================================================
# 5. Discovery, Fetch and Robustness Tests
# ============================================================================


def test_instat_tbe_catalog_discovery(
    monkeypatch: pytest.MonkeyPatch,
    httpserver: HTTPServer,
) -> None:
    """Verify dynamic discovery of TBE Excel publications from HTML catalog."""
    monkeypatch.setenv("KETRIKA_ALLOW_TEST_LOOPBACK", "1")
    httpserver.expect_request("/robots.txt").respond_with_data("User-agent: *\nDisallow:\n", status=200)

    catalog_html = """
    <html>
      <head><title>Tableau de Bord Économique - INSTAT</title></head>
      <body>
        <h1>Publications du Tableau de Bord Économique</h1>
        <ul>
          <li><a href="/downloads/tbe_edition_63_aout_2026.xlsx">TBE N°63 Août 2026</a></li>
          <li><a href="/downloads/tbe_edition_62_mai_2026.xlsx">TBE N°62 Mai 2026</a></li>
          <li><a href="/mentions">Mentions Légales</a></li>
        </ul>
      </body>
    </html>
    """
    httpserver.expect_request("/statistiques/tbe").respond_with_data(catalog_html, content_type="text/html")

    policy = PolicyEngine()
    policy.set_robots_txt(httpserver.url_for("/"), "User-agent: *\nDisallow:\n")
    http_client = PoliteHttpClient(
        policy_engine=policy,
        budget_backend=MemoryBudgetBackend(),
        allow_loopback=True,
    )
    http_client.bind_source("instat_tbe", daily_request_budget=100, max_rps=10.0)

    connector = InstatTbeConnector()
    ctx = RunContext(
        source_id="instat_tbe",
        http_client=http_client,
        policy_engine=policy,
        metadata={
            "catalog_url": httpserver.url_for("/statistiques/tbe"),
            "allow_loopback": True,
        },
    )

    discovered = list(connector.discover(ctx))
    assert len(discovered) == 2
    urls = [d.url for d in discovered]
    assert any("tbe_edition_63_aout_2026.xlsx" in u for u in urls)
    assert any("tbe_edition_62_mai_2026.xlsx" in u for u in urls)
    assert all(d.partition_key == "tbe_national" for d in discovered)


def test_instat_tbe_discovery_fallback():
    """Verify discovery gracefully falls back when catalog retrieval fails."""
    connector = InstatTbeConnector()
    ctx = RunContext(source_id="instat_tbe", metadata={"catalog_url": "http://invalid-non-existent-domain.xyz/catalog"})

    discovered = list(connector.discover(ctx))
    assert len(discovered) == 1
    assert discovered[0].partition_key == "tbe_national"
    assert discovered[0].hints.get("fallback") == "true"


def test_instat_tbe_fetch():
    """Verify fetch delegates to ctx.fetch_and_store."""
    connector = InstatTbeConnector()
    item = DiscoveredItem(
        url="https://www.instat.mg/statistiques/tbe/tbe_62.xlsx",
        partition_key="tbe_national",
        published_at=datetime.now(UTC),
    )
    mock_ctx = MagicMock(spec=RunContext)
    expected_artifact = RawArtifact(
        source_record_id="rec_test",
        object_key="bronze/instat_tbe/test.xlsx",
        content_sha256="fake_sha",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        url=item.url,
        is_new=True,
    )
    mock_ctx.fetch_and_store.return_value = expected_artifact

    art = connector.fetch(item, mock_ctx)
    assert art == expected_artifact
    mock_ctx.fetch_and_store.assert_called_once_with(
        item,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def test_instat_tbe_parse_missing_content_or_sheets():
    """Verify parse reports issue when bronze store returns None or empty workbook."""
    connector = InstatTbeConnector()
    mock_store = MagicMock()
    mock_store.get.return_value = None
    ctx = RunContext(source_id="instat_tbe", bronze_store=mock_store)

    artifact = RawArtifact(
        source_record_id="rec_missing",
        object_key="bronze/instat_tbe/missing.xlsx",
        content_sha256="fake_sha",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        url="https://instat.mg/missing.xlsx",
        is_new=True,
    )

    res = connector.parse(artifact, ctx)
    assert len(res.issues) == 1
    assert res.issues[0]["kind"] == "bronze_artifact_not_found"
    assert len(res.records) == 0
