"""Unit tests and Golden validation for MiASA ODR connector (CC1, CC2, T4.1)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_httpserver import HTTPServer

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.miasa_odr import MiasaOdrConnector
from ketrika.connectors.records import PriceRecord
from ketrika.core.bronze import BronzeStore
from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import MemoryBudgetBackend
from ketrika.core.policy import PolicyEngine
from ketrika.core.registry import find_repo_root
from ketrika.extraction.evidence import verify_evidence
from ketrika.extraction.llm.replay import ReplayClient

FIXTURES_DIR = find_repo_root() / "backend" / "tests" / "fixtures" / "miasa_odr"
GOLDEN_DIR = find_repo_root() / "backend" / "tests" / "golden" / "miasa_odr"
AUTHENTIC_GOLDEN_PATH = GOLDEN_DIR / "odr_authentic.expected.json"


@pytest.fixture
def authentic_golden_data() -> dict[str, Any]:
    with open(AUTHENTIC_GOLDEN_PATH, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


@pytest.fixture
def odr_pdf_bytes_mai_2025() -> bytes:
    with open(FIXTURES_DIR / "odr_bulletin_authentique_mai_2025.pdf", "rb") as f:
        return f.read()


@pytest.fixture
def odr_pdf_bytes_fev_2024() -> bytes:
    with open(FIXTURES_DIR / "odr_bulletin_authentique_fev_2024.pdf", "rb") as f:
        return f.read()


@pytest.fixture
def odr_pdf_bytes_drift() -> bytes:
    with open(FIXTURES_DIR / "odr_bulletin_drift_layout.pdf", "rb") as f:
        return f.read()


@pytest.fixture
def odr_pdf_bytes_scanned() -> bytes:
    with open(FIXTURES_DIR / "odr_bulletin_scanned_unverifiable.pdf", "rb") as f:
        return f.read()


@pytest.fixture
def odr_pdf_bytes_520() -> bytes:
    with open(FIXTURES_DIR / "odr_bulletin_520.pdf", "rb") as f:
        return f.read()


@pytest.fixture
def odr_pdf_bytes_710() -> bytes:
    with open(FIXTURES_DIR / "odr_bulletin_710.pdf", "rb") as f:
        return f.read()


@pytest.fixture
def odr_pdf_bytes_850() -> bytes:
    with open(FIXTURES_DIR / "odr_bulletin_850.pdf", "rb") as f:
        return f.read()


@pytest.fixture
def golden_520() -> dict[str, Any]:
    with open(GOLDEN_DIR / "odr_bulletin_520.expected.json", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


@pytest.fixture
def golden_710() -> dict[str, Any]:
    with open(GOLDEN_DIR / "odr_bulletin_710.expected.json", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


@pytest.fixture
def golden_850() -> dict[str, Any]:
    with open(GOLDEN_DIR / "odr_bulletin_850.expected.json", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


def test_miasa_odr_parse_bulletin_850(odr_pdf_bytes_850: bytes, golden_850: dict[str, Any]) -> None:
    """CC1: Unit test verifying PDF parsing on modern epoch (Bulletin 850, 2024)."""
    connector = MiasaOdrConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = odr_pdf_bytes_850
    ctx = RunContext(
        source_id="miasa_odr",
        bronze_store=mock_bronze,
        llm_client=ReplayClient(),
    )

    artifact = RawArtifact(
        source_record_id="test-rec-850",
        object_key="bronze/miasa_odr/850.pdf",
        content_sha256=golden_850["metadata"]["content_sha256"],
        mime_type="application/pdf",
        url="http://www.agriculture.gov.mg/odr/bulletin_850.pdf",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    assert len(result.issues) == 0
    assert len(result.records) == 60
    assert len(result.records) == golden_850["metadata"]["total_records"]

    price_records = [r for r in result.records if isinstance(r, PriceRecord)]
    assert len(price_records) == 60

    # Observation period = observation month (Jan 2024), not publication date (T4.1 rule)
    assert all(r.period_start.isoformat() == "2024-01-01" for r in price_records)
    assert all(r.period_end.isoformat() == "2024-01-31" for r in price_records)

    # All three actor levels present
    actor_levels = {r.actor_level for r in price_records}
    assert actor_levels == {"producer", "wholesale", "retail"}

    # Producer paddy records
    paddy_recs = [r for r in price_records if r.actor_level == "producer"]
    assert len(paddy_recs) == 12
    assert all(r.product_raw == "Riz paddy" for r in paddy_recs)

    # Wholesale records
    wh_recs = [r for r in price_records if r.actor_level == "wholesale"]
    assert len(wh_recs) == 24

    # Retail records
    ret_recs = [r for r in price_records if r.actor_level == "retail"]
    assert len(ret_recs) == 24


@pytest.mark.parametrize(
    ("bulletin_num", "pdf_fixture_name", "golden_fixture_name"),
    [
        (520, "odr_pdf_bytes_520", "golden_520"),
        (710, "odr_pdf_bytes_710", "golden_710"),
        (850, "odr_pdf_bytes_850", "golden_850"),
    ],
)
def test_miasa_odr_golden_evaluation(
    bulletin_num: int,
    pdf_fixture_name: str,
    golden_fixture_name: str,
    request: pytest.FixtureRequest,
) -> None:
    """CC2: Golden dataset validation on 3 epochs (exactitude >= 99%, rappel >= 98%, >= 50 values)."""
    pdf_bytes: bytes = request.getfixturevalue(pdf_fixture_name)
    golden_data: dict[str, Any] = request.getfixturevalue(golden_fixture_name)

    connector = MiasaOdrConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = pdf_bytes
    ctx = RunContext(
        source_id="miasa_odr",
        bronze_store=mock_bronze,
        llm_client=ReplayClient(),
    )

    content_sha = golden_data["metadata"]["content_sha256"]
    artifact = RawArtifact(
        source_record_id=f"test-rec-{bulletin_num}",
        object_key=f"bronze/miasa_odr/{bulletin_num}.pdf",
        content_sha256=content_sha,
        mime_type="application/pdf",
        url=f"http://www.agriculture.gov.mg/odr/bulletin_{bulletin_num}.pdf",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    expected_records = golden_data["records"]

    # Criterion: >= 50 values per bulletin
    assert len(expected_records) >= 50
    assert len(result.records) == len(expected_records)

    parsed_map = {
        (r.product_raw, r.location_raw, r.actor_level): r
        for r in result.records
        if isinstance(r, PriceRecord)
    }

    correct_fields = 0
    total_fields = 0

    for expected in expected_records:
        key = (expected["product_raw"], expected["location_raw"], expected["actor_level"])
        parsed = parsed_map.get(key)
        assert parsed is not None, f"Expected record with key {key} was not parsed"

        # product_raw
        total_fields += 1
        if parsed.product_raw == expected["product_raw"]:
            correct_fields += 1

        # variety
        total_fields += 1
        if parsed.variety == expected["variety"]:
            correct_fields += 1

        # actor_level
        total_fields += 1
        if parsed.actor_level == expected["actor_level"]:
            correct_fields += 1

        # location_raw
        total_fields += 1
        if parsed.location_raw == expected["location_raw"]:
            correct_fields += 1

        # price_raw
        total_fields += 1
        if parsed.price_raw == expected["price_raw"]:
            correct_fields += 1

        # price_value
        total_fields += 1
        if parsed.price_value == expected["price_value"]:
            correct_fields += 1

        # unit_raw
        total_fields += 1
        if parsed.unit_raw == expected["unit_raw"]:
            correct_fields += 1

        # currency_raw
        total_fields += 1
        if parsed.currency_raw == expected["currency_raw"]:
            correct_fields += 1

        # missing_code
        total_fields += 1
        if parsed.missing_code == expected["missing_code"]:
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
    recall = len(parsed_map) / len(expected_records)

    assert accuracy >= 0.99, f"Bulletin {bulletin_num}: accuracy {accuracy:.2%} is below 99%"
    assert recall >= 0.98, f"Bulletin {bulletin_num}: recall {recall:.2%} is below 98%"


def test_miasa_odr_missing_codes_never_zero(
    odr_pdf_bytes_850: bytes, golden_850: dict[str, Any]
) -> None:
    """T4.1 strict rule: 0 valeur ND ou NA convertie en 0."""
    connector = MiasaOdrConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = odr_pdf_bytes_850
    ctx = RunContext(
        source_id="miasa_odr",
        bronze_store=mock_bronze,
        llm_client=ReplayClient(),
    )

    artifact = RawArtifact(
        source_record_id="test-rec-850",
        object_key="bronze/miasa_odr/850.pdf",
        content_sha256=golden_850["metadata"]["content_sha256"],
        mime_type="application/pdf",
        url="http://www.agriculture.gov.mg/odr/bulletin_850.pdf",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    missing_records = [
        r for r in result.records if isinstance(r, PriceRecord) and r.missing_code is not None
    ]
    # At least 2 missing codes in bulletin 850
    assert len(missing_records) >= 2

    for rec in missing_records:
        assert rec.missing_code in ("ND", "NA")
        assert rec.price_value is None, f"Expected None for missing code, got {rec.price_value}"
        assert rec.price_value != 0, "ND/NA must NEVER be converted to 0"


def test_miasa_odr_dual_extraction_agreement(
    odr_pdf_bytes_850: bytes, golden_850: dict[str, Any]
) -> None:
    """SPECS §11.1: Verify dual_agree extraction method and 0.99 confidence when deterministic and LLM agree."""
    connector = MiasaOdrConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = odr_pdf_bytes_850
    ctx = RunContext(
        source_id="miasa_odr",
        bronze_store=mock_bronze,
        llm_client=ReplayClient(),
    )

    artifact = RawArtifact(
        source_record_id="test-rec-850",
        object_key="bronze/miasa_odr/850.pdf",
        content_sha256=golden_850["metadata"]["content_sha256"],
        mime_type="application/pdf",
        url="http://www.agriculture.gov.mg/odr/bulletin_850.pdf",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    # When both deterministic and LLM replay match, extraction_method is dual_agree with 0.99 confidence
    numeric_records = [
        r for r in result.records if isinstance(r, PriceRecord) and r.price_value is not None
    ]
    assert len(numeric_records) > 0
    assert all(r.extraction_method == "dual_agree" for r in numeric_records)
    assert all(r.confidence == 0.99 for r in numeric_records)


def test_miasa_odr_authentic_corpus_golden(
    authentic_golden_data: dict[str, Any],
    odr_pdf_bytes_mai_2025: bytes,
    odr_pdf_bytes_fev_2024: bytes,
) -> None:
    """CC-R / R1.4: Authentic corpus evaluation on 2 distinct editions (Mai 2025, Fév 2024).

    Requirements:
    - >= 2 distinct editions
    - >= 30 annotated values in golden set (75 total here)
    - Accuracy >= 99%
    - Recall >= 98%
    - Producer, wholesale, and retail actor levels
    - Rice varieties: Vary gasy, Makalioka, Tsipala, 25% brisures, Riz paddy
    - Strict handling of ND/NA missing values (never converted to 0)
    """
    connector = MiasaOdrConnector()
    connector.dual_extraction = False

    editions = authentic_golden_data["editions"]
    assert len(editions) >= 2, "Must evaluate at least 2 distinct authentic editions"

    pdf_map = {
        "mai_2025": odr_pdf_bytes_mai_2025,
        "fev_2024": odr_pdf_bytes_fev_2024,
    }

    all_parsed_records: list[PriceRecord] = []
    total_golden_records = 0

    for ed_key, ed_info in editions.items():
        pdf_bytes = pdf_map[ed_key]
        mock_bronze = MagicMock(spec=BronzeStore)
        mock_bronze.get.return_value = pdf_bytes
        ctx = RunContext(source_id="miasa_odr", bronze_store=mock_bronze, offline=True)

        artifact = RawArtifact(
            source_record_id=f"test-rec-{ed_key}",
            object_key=f"bronze/miasa_odr/{ed_info['filename']}",
            content_sha256=ed_info["content_sha256"],
            mime_type="application/pdf",
            url=f"http://www.agriculture.gov.mg/odr/{ed_info['filename']}",
            is_new=True,
        )

        result = connector.parse(artifact, ctx)
        assert len(result.issues) == 0, f"Unexpected issues in {ed_key}: {result.issues}"

        expected_records = ed_info["records"]
        total_golden_records += len(expected_records)

        price_recs = [r for r in result.records if isinstance(r, PriceRecord)]
        assert len(price_recs) == len(expected_records)
        all_parsed_records.extend(price_recs)

        parsed_map = {(r.product_raw, r.location_raw, r.actor_level): r for r in price_recs}

        correct_fields = 0
        total_fields = 0

        for expected in expected_records:
            key = (expected["product_raw"], expected["location_raw"], expected["actor_level"])
            parsed = parsed_map.get(key)
            assert parsed is not None, f"Expected record {key} not parsed in {ed_key}"

            for field in [
                "product_raw",
                "variety",
                "actor_level",
                "location_raw",
                "price_raw",
                "price_value",
                "unit_raw",
                "currency_raw",
                "missing_code",
            ]:
                total_fields += 1
                if getattr(parsed, field) == expected[field]:
                    correct_fields += 1

            total_fields += 2
            if parsed.period_start.isoformat() == expected["period_start"]:
                correct_fields += 1
            if parsed.period_end.isoformat() == expected["period_end"]:
                correct_fields += 1

        accuracy = correct_fields / total_fields
        recall = len(parsed_map) / len(expected_records)

        assert accuracy >= 0.99, f"Edition {ed_key}: accuracy {accuracy:.2%} is below 99%"
        assert recall >= 0.98, f"Edition {ed_key}: recall {recall:.2%} is below 98%"

    # Corpus-wide criteria
    assert total_golden_records >= 30, f"Expected >= 30 golden records, got {total_golden_records}"
    assert len(all_parsed_records) == total_golden_records

    # Check actor levels diversity
    actor_levels = {r.actor_level for r in all_parsed_records}
    assert actor_levels == {"producer", "wholesale", "retail"}

    # Check varieties diversity
    varieties = {r.variety for r in all_parsed_records if r.variety is not None}
    assert {"Vary gasy", "Makalioka", "Tsipala", "25% brisures"}.issubset(varieties)

    # Missing codes never converted to 0
    missing = [r for r in all_parsed_records if r.missing_code is not None]
    assert len(missing) >= 2
    for m in missing:
        assert m.price_value is None
        assert m.missing_code in ("ND", "NA")


def test_miasa_odr_neighboring_cell_evidence_rejected() -> None:
    """R1.4: Refus mécanique d'une cellule du tableau ou de la ligne voisine comme preuve valide."""
    page_text = (
        "OBSERVATOIRE DU RIZ - BULLETIN DE MAI 2025\n"
        "TABLEAU DES PRIX DE GROS (Ar/kg)\n"
        "Zone de collecte / marché | Vary gasy | Makalioka | Tsipala | 25% brisures\n"
        "Boeny (Mahajanga Tsaramandroso) | 3 150 | NA | 3 100 | 2 920\n"
        "Diana (Antsiranana Bazar) | 3 250 | 3 400 | 3 200 | 3 050\n"
        "Atsinanana (Toamasina I) | 3 450 | 3 600 | 3 400 | 3 100\n"
    )

    # 1. Correct evidence with expected location matching -> Verified
    assert (
        verify_evidence(
            value=3150.0,
            evidence={"page": 1, "text": "Boeny (Mahajanga Tsaramandroso) 3 150"},
            page_text=page_text,
            expected_location="Boeny (Mahajanga Tsaramandroso)",
        )
        is True
    )

    # 2. Neighboring row/cell: price 3 150 attributed to Diana -> Rejected
    assert (
        verify_evidence(
            value=3150.0,
            evidence={"page": 1, "text": "Boeny (Mahajanga Tsaramandroso) 3 150"},
            page_text=page_text,
            expected_location="Diana (Antsiranana Bazar)",
        )
        is False
    )

    # 3. Neighboring row/cell: price 3 250 with evidence snippet from Atsinanana -> Rejected
    assert (
        verify_evidence(
            value=3250.0,
            evidence={"page": 1, "text": "Atsinanana (Toamasina I) 3 450"},
            page_text=page_text,
            expected_location="Diana (Antsiranana Bazar)",
        )
        is False
    )

    # 4. Wrong numeric value even if location matches -> Rejected
    assert (
        verify_evidence(
            value=4000.0,
            evidence={"page": 1, "text": "Boeny (Mahajanga Tsaramandroso) 3 150"},
            page_text=page_text,
            expected_location="Boeny (Mahajanga Tsaramandroso)",
        )
        is False
    )


def test_miasa_odr_scanned_pdf_needs_review(odr_pdf_bytes_scanned: bytes) -> None:
    """R1.4: Scanned raster PDF without selectable vector text -> scanned_pdf_needs_review."""
    connector = MiasaOdrConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = odr_pdf_bytes_scanned
    ctx = RunContext(source_id="miasa_odr", bronze_store=mock_bronze, offline=True)

    artifact = RawArtifact(
        source_record_id="test-scanned",
        object_key="bronze/miasa_odr/scanned.pdf",
        content_sha256="scanned-sha",
        mime_type="application/pdf",
        url="http://www.agriculture.gov.mg/odr/bulletin_scanned.pdf",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.records) == 0
    assert len(result.issues) == 1
    assert result.issues[0]["kind"] == "scanned_pdf_needs_review"
    assert "OCR is not authorized" in result.issues[0]["detail"]


def test_miasa_odr_layout_drift_detected(odr_pdf_bytes_drift: bytes) -> None:
    """R1.4: Document layout drift (no recognized ODR price tables) -> layout_changed issue, no empty silent success."""
    connector = MiasaOdrConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = odr_pdf_bytes_drift
    ctx = RunContext(source_id="miasa_odr", bronze_store=mock_bronze, offline=True)

    artifact = RawArtifact(
        source_record_id="test-drift",
        object_key="bronze/miasa_odr/drift.pdf",
        content_sha256="drift-sha",
        mime_type="application/pdf",
        url="http://www.agriculture.gov.mg/odr/bulletin_drift.pdf",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.records) == 0
    assert len(result.issues) == 1
    assert result.issues[0]["kind"] == "layout_changed"
    assert "layout or schema drift detected" in result.issues[0]["detail"]


def test_miasa_odr_dynamic_catalog_discovery(
    monkeypatch: pytest.MonkeyPatch,
    httpserver: HTTPServer,
) -> None:
    """R1.4 / R1.2: Dynamic catalog discovery following HTML links on agriculture.gov.mg."""
    monkeypatch.setenv("KETRIKA_ALLOW_TEST_LOOPBACK", "1")
    httpserver.expect_request("/robots.txt").respond_with_data(
        "User-agent: *\nDisallow:\n", status=200
    )

    catalog_html = """
    <html>
      <head><title>Observatoire du Riz - Bulletins Hebdomadaires et Mensuels</title></head>
      <body>
        <h1>Publications Officielles ODR</h1>
        <div class="bulletins-list">
          <a href="/odr/bulletin_905.pdf">Bulletin Mensuel n° 905 - Avril 2025</a>
          <a href="/odr/bulletin_904.pdf">Bulletin Mensuel n° 904 - Mars 2025</a>
          <a href="/odr/bulletin_903.pdf">Bulletin Mensuel n° 903 - Février 2025</a>
          <a href="/a-propos">À propos de l'ODR</a>
        </div>
      </body>
    </html>
    """
    httpserver.expect_request("/odr/bulletins").respond_with_data(
        catalog_html, content_type="text/html"
    )

    policy = PolicyEngine()
    policy.set_robots_txt(httpserver.url_for("/"), "User-agent: *\nDisallow:\n")
    http_client = PoliteHttpClient(
        policy_engine=policy,
        budget_backend=MemoryBudgetBackend(),
        allow_loopback=True,
    )
    http_client.bind_source("miasa_odr", daily_request_budget=100, max_rps=10.0)

    connector = MiasaOdrConnector()
    ctx = RunContext(
        source_id="miasa_odr",
        http_client=http_client,
        policy_engine=policy,
        metadata={
            "catalog_url": httpserver.url_for("/odr/bulletins"),
            "allow_loopback": True,
            "allowed_domains": ["127.0.0.1", "localhost"],
        },
    )

    discovered = list(connector.discover(ctx))
    assert len(discovered) == 3
    urls = [d.url for d in discovered]
    assert any("bulletin_905.pdf" in u for u in urls)
    assert any("bulletin_904.pdf" in u for u in urls)
    assert any("bulletin_903.pdf" in u for u in urls)
    assert all(
        d.partition_key is not None and d.partition_key.startswith("odr_bulletin_")
        for d in discovered
    )
    assert all(d.hints.get("publisher") == "MiASA/ODR" for d in discovered)
    assert all(d.hints.get("format") == "pdf" for d in discovered)
