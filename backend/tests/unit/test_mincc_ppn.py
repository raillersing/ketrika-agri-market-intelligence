"""Unit and golden tests for MinCC PPN price and stock connector (SPECS §5.2, §8, T4.2)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_httpserver import HTTPServer

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.mincc_ppn import MinccPpnConnector
from ketrika.connectors.records import PriceRecord, RecordBase, StockRecord
from ketrika.core.bronze import BronzeArtifact, BronzeStore
from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import MemoryBudgetBackend
from ketrika.core.policy import PolicyEngine
from ketrika.core.registry import find_repo_root
from ketrika.extraction.llm.replay import ReplayClient


@pytest.fixture
def repo_root() -> Path:
    return find_repo_root()


@pytest.fixture
def base_dir(repo_root: Path) -> Path:
    if (repo_root / "backend").exists():
        return repo_root / "backend"
    return repo_root


@pytest.fixture
def fixtures_dir(base_dir: Path) -> Path:
    return base_dir / "tests" / "fixtures" / "mincc_ppn"


@pytest.fixture
def golden_dir(base_dir: Path) -> Path:
    return base_dir / "tests" / "golden" / "mincc_ppn"


@pytest.fixture
def run_context() -> RunContext:
    mem_store: dict[str, bytes] = {}
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.side_effect = lambda k: mem_store[k]

    def _put(
        source_id: str,
        content: bytes,
        mime_type: str,
        url: str,
        retrieved_via: str = "direct",
        http_headers: dict[str, str] | None = None,
        http_status: int = 200,
        user_agent: str | None = None,
        fetched_at: datetime | None = None,
    ) -> BronzeArtifact:
        sha = hashlib.sha256(content).hexdigest()
        obj_key = f"{source_id}/2024/02/{sha}.html"
        is_new = obj_key not in mem_store
        mem_store[obj_key] = content
        return BronzeArtifact(
            object_key=obj_key,
            content_sha256=sha,
            mime_type=mime_type,
            url=url,
            fetched_at=fetched_at or datetime.now(UTC),
            is_new=is_new,
            size_bytes=len(content),
        )

    mock_bronze.put.side_effect = _put
    return RunContext(
        source_id="mincc_ppn",
        bronze_store=mock_bronze,
        policy_engine=PolicyEngine(),
        offline=True,
        llm_client=ReplayClient(),
    )


def test_discover_mincc_publications(run_context: RunContext):
    """Test that discover yields all 10 expected regional publications with distinct partition keys."""
    connector = MinccPpnConnector()
    items = list(connector.discover(run_context))

    assert len(items) == 10
    keys = [item.partition_key for item in items]
    assert len(set(keys)) == 10

    # Pinned domain
    for it in items:
        assert "commerce.gov.mg" in it.url
        assert it.published_at is not None


def test_parse_deterministic_html_tables(
    run_context: RunContext,
    fixtures_dir: Path,
):
    """Test deterministic HTML table parsing across all 6 tabular publications (CC1)."""
    connector = MinccPpnConnector()
    html_docs = [
        "mincc_pub_01_analamanga_html",
        "mincc_pub_02_atsinanana_html",
        "mincc_pub_03_boeny_html",
        "mincc_pub_04_vakinankaratra_html",
        "mincc_pub_05_atsimo_andrefana_html",
        "mincc_pub_06_diana_html",
    ]

    for doc_id in html_docs:
        html_file = fixtures_dir / f"{doc_id}.html"
        assert html_file.exists()
        content = html_file.read_bytes()

        assert run_context.bronze_store is not None
        art = run_context.bronze_store.put(
            source_id="mincc_ppn",
            content=content,
            mime_type="text/html",
            url=f"http://www.commerce.gov.mg/ppn/{doc_id}.html",
        )

        artifact = RawArtifact(
            source_record_id="",
            object_key=art.object_key,
            content_sha256=art.content_sha256,
            mime_type="text/html",
            url=f"http://www.commerce.gov.mg/ppn/{doc_id}.html",
            is_new=True,
            published_at=datetime(2024, 2, 5, 8, 0, tzinfo=UTC),
        )

        res = connector.parse(artifact, run_context)
        assert len(res.issues) == 0
        assert len(res.records) == 8  # 4 prices + 4 stocks

        prices = [r for r in res.records if isinstance(r, PriceRecord)]
        stocks = [r for r in res.records if isinstance(r, StockRecord)]
        assert len(prices) == 4
        assert len(stocks) == 4

        for p in prices:
            assert p.price_value is not None and p.price_value > 0
            assert p.actor_level in ("retail", "wholesale", "official_ppn")
            assert p.unit_raw in ("kg", "litre")
            assert p.currency_raw == "MGA"
            assert p.extraction_method == "deterministic"

        for s in stocks:
            assert s.quantity_value is not None and s.quantity_value > 0
            assert s.unit_raw == "tonne"
            assert s.stock_status in ("sufficient", "tight", "shortage", "unknown")
            assert s.coverage_days is not None and s.coverage_days > 0
            assert s.extraction_method == "deterministic"


def test_parse_llm_text_communiques(
    run_context: RunContext,
    fixtures_dir: Path,
):
    """Test LLM narrative extraction with verified evidence across 4 French/Malagasy communiques (CC1)."""
    connector = MinccPpnConnector()
    text_docs = [
        "mincc_pub_07_communique_analamanga_fr",
        "mincc_pub_08_communique_atsinanana_fr",
        "mincc_pub_09_filazana_boeny_mg",
        "mincc_pub_10_filazana_vakinankaratra_mg",
    ]

    for doc_id in text_docs:
        html_file = fixtures_dir / f"{doc_id}.html"
        assert html_file.exists()
        content = html_file.read_bytes()

        assert run_context.bronze_store is not None
        art = run_context.bronze_store.put(
            source_id="mincc_ppn",
            content=content,
            mime_type="text/html",
            url=f"http://www.commerce.gov.mg/ppn/{doc_id}.html",
        )

        artifact = RawArtifact(
            source_record_id="",
            object_key=art.object_key,
            content_sha256=art.content_sha256,
            mime_type="text/html",
            url=f"http://www.commerce.gov.mg/ppn/{doc_id}.html",
            is_new=True,
            published_at=datetime(2024, 2, 15, 8, 0, tzinfo=UTC),
        )

        res = connector.parse(artifact, run_context)
        assert len(res.issues) == 0
        assert len(res.records) == 4  # 2 prices + 2 stocks

        prices = [r for r in res.records if isinstance(r, PriceRecord)]
        stocks = [r for r in res.records if isinstance(r, StockRecord)]
        assert len(prices) == 2
        assert len(stocks) == 2

        for p in prices:
            assert p.extraction_method == "llm_verified"
            assert p.price_value is not None and p.price_value > 0
            assert "text" in p.evidence

        for s in stocks:
            assert s.extraction_method == "llm_verified"
            assert s.quantity_value is not None and s.quantity_value > 0
            assert s.stock_status in ("sufficient", "tight", "shortage", "unknown")
            assert s.coverage_days is not None and s.coverage_days > 0
            assert "text" in s.evidence


def test_golden_sets_all_10_publications(
    run_context: RunContext,
    fixtures_dir: Path,
    golden_dir: Path,
):
    """Golden acceptance test: accuracy >= 99% and recall >= 98% across all 10 publications (CC2)."""
    connector = MinccPpnConnector()
    golden_files = sorted(golden_dir.glob("mincc_pub_*.expected.json"))
    assert len(golden_files) == 10

    total_expected = 0
    total_matched = 0
    total_field_checks = 0
    total_field_matches = 0

    for g_path in golden_files:
        with open(g_path, encoding="utf-8") as f:
            golden = json.load(f)

        doc_id = golden["doc_id"]
        html_file = fixtures_dir / f"{doc_id}.html"
        content = html_file.read_bytes()

        assert run_context.bronze_store is not None
        art = run_context.bronze_store.put(
            source_id="mincc_ppn",
            content=content,
            mime_type="text/html",
            url=f"http://www.commerce.gov.mg/ppn/{doc_id}.html",
        )

        artifact = RawArtifact(
            source_record_id="",
            object_key=art.object_key,
            content_sha256=art.content_sha256,
            mime_type="text/html",
            url=f"http://www.commerce.gov.mg/ppn/{doc_id}.html",
            is_new=True,
            published_at=datetime.fromisoformat(golden["published_at"].replace("Z", "+00:00")),
        )

        res = connector.parse(artifact, run_context)
        expected_records = golden["records"]
        total_expected += len(expected_records)

        # Match each expected record
        for exp in expected_records:
            if exp["record_type"] == "price":
                price_candidates: list[PriceRecord] = [
                    r
                    for r in res.records
                    if isinstance(r, PriceRecord)
                    and r.product_raw == exp["product_raw"]
                    and r.actor_level == exp["actor_level"]
                ]
                assert len(price_candidates) >= 1, f"Missing expected record for {exp} in {doc_id}"
                matched_price = price_candidates[0]
                total_matched += 1

                # Field matches: price_value, unit_raw, currency_raw
                total_field_checks += 3
                if matched_price.price_value == exp["price_value"]:
                    total_field_matches += 1
                if matched_price.unit_raw == exp["unit_raw"]:
                    total_field_matches += 1
                if matched_price.currency_raw == exp["currency_raw"]:
                    total_field_matches += 1
            else:
                stock_candidates: list[StockRecord] = [
                    r
                    for r in res.records
                    if isinstance(r, StockRecord) and r.product_raw == exp["product_raw"]
                ]
                assert len(stock_candidates) >= 1, f"Missing expected record for {exp} in {doc_id}"
                matched_stock = stock_candidates[0]
                total_matched += 1

                # Field matches: quantity_value, stock_status, coverage_days
                total_field_checks += 3
                if matched_stock.quantity_value == exp["quantity_value"]:
                    total_field_matches += 1
                if matched_stock.stock_status == exp["stock_status"]:
                    total_field_matches += 1
                if matched_stock.coverage_days == exp["coverage_days"]:
                    total_field_matches += 1

    recall = total_matched / total_expected
    accuracy = total_field_matches / total_field_checks

    assert total_expected >= 60, f"Expected >= 60 values total, got {total_expected}"
    assert recall >= 0.98, f"Recall was {recall:.2%}, expected >= 98%"
    assert accuracy >= 0.99, f"Accuracy was {accuracy:.2%}, expected >= 99%"


def test_mincc_stock_records_regional_coverage(
    run_context: RunContext,
    fixtures_dir: Path,
):
    """Test acceptance criterion: >= 1 StockRecord for >= 3 distinct regions."""
    connector = MinccPpnConnector()
    items = list(connector.discover(run_context))

    regions_with_stocks: set[str] = set()

    for it in items:
        html_file = fixtures_dir / f"{it.partition_key}.html"
        content = html_file.read_bytes()

        assert run_context.bronze_store is not None
        art = run_context.bronze_store.put(
            source_id="mincc_ppn",
            content=content,
            mime_type="text/html",
            url=it.url,
        )

        artifact = RawArtifact(
            source_record_id="",
            object_key=art.object_key,
            content_sha256=art.content_sha256,
            mime_type="text/html",
            url=it.url,
            is_new=True,
            published_at=it.published_at,
        )

        res = connector.parse(artifact, run_context)
        for r in res.records:
            if isinstance(r, StockRecord) and r.location_raw:
                regions_with_stocks.add(r.location_raw)

    assert len(regions_with_stocks) >= 3, (
        f"Expected >= 3 regions with StockRecords, got {len(regions_with_stocks)}: {regions_with_stocks}"
    )
    # Check that major regions are among them
    assert "Analamanga" in regions_with_stocks
    assert "Atsinanana" in regions_with_stocks
    assert "Boeny" in regions_with_stocks


def test_mincc_dynamic_catalog_discovery(
    monkeypatch: pytest.MonkeyPatch,
    httpserver: HTTPServer,
) -> None:
    """R1.5 / R1.2: Dynamic catalog discovery following HTML links on commerce.gov.mg."""
    monkeypatch.setenv("KETRIKA_ALLOW_TEST_LOOPBACK", "1")
    httpserver.expect_request("/robots.txt").respond_with_data("User-agent: *\nDisallow:\n", status=200)

    catalog_html = """
    <html>
      <head><title>Ministère de l'Industrialisation et du Commerce - PPN</title></head>
      <body>
        <h1>Publications Officielles PPN</h1>
        <div class="articles">
          <a href="/ppn/mincc_pub_11_analamanga_2024.html">Relevé Hebdomadaire Analamanga - Mars 2024</a>
          <a href="/ppn/mincc_pub_12_atsinanana_2024.html">Relevé Hebdomadaire Atsinanana - Mars 2024</a>
          <a href="/ppn/mincc_pub_13_boeny_2024.pdf">Communiqué Stocks Boeny - Mars 2024</a>
          <a href="/mentions-legales">Mentions Légales</a>
        </div>
      </body>
    </html>
    """
    httpserver.expect_request("/ppn/actualites").respond_with_data(catalog_html, content_type="text/html")

    policy = PolicyEngine()
    policy.set_robots_txt(httpserver.url_for("/"), "User-agent: *\nDisallow:\n")
    http_client = PoliteHttpClient(
        policy_engine=policy,
        budget_backend=MemoryBudgetBackend(),
        allow_loopback=True,
    )
    http_client.bind_source("mincc_ppn", daily_request_budget=100, max_rps=10.0)

    connector = MinccPpnConnector()
    ctx = RunContext(
        source_id="mincc_ppn",
        http_client=http_client,
        policy_engine=policy,
        metadata={
            "catalog_url": httpserver.url_for("/ppn/actualites"),
            "allow_loopback": True,
            "allowed_domains": ["127.0.0.1", "localhost"],
        },
    )

    discovered = list(connector.discover(ctx))
    assert len(discovered) == 3
    urls = [d.url for d in discovered]
    assert any("mincc_pub_11_analamanga_2024.html" in u for u in urls)
    assert any("mincc_pub_12_atsinanana_2024.html" in u for u in urls)
    assert any("mincc_pub_13_boeny_2024.pdf" in u for u in urls)
    assert all(d.hints.get("publisher") == "MinCC/DRCC" for d in discovered)


def test_mincc_price_ceiling_vs_observed_separation(
    run_context: RunContext,
    fixtures_dir: Path,
) -> None:
    """R1.5: Verify strict separation between regulated price ceilings and observed market prices."""
    connector = MinccPpnConnector()
    html_file = fixtures_dir / "mincc_arrete_plafond_prix_2024_fr.html"
    content = html_file.read_bytes()

    assert run_context.bronze_store is not None
    art = run_context.bronze_store.put(
        source_id="mincc_ppn",
        content=content,
        mime_type="text/html",
        url="http://www.commerce.gov.mg/ppn/mincc_arrete_plafond_prix_2024_fr.html",
    )

    artifact = RawArtifact(
        source_record_id="",
        object_key=art.object_key,
        content_sha256=art.content_sha256,
        mime_type="text/html",
        url="http://www.commerce.gov.mg/ppn/mincc_arrete_plafond_prix_2024_fr.html",
        is_new=True,
        published_at=datetime(2024, 3, 1, 8, 0, tzinfo=UTC),
    )

    res = connector.parse(artifact, run_context)
    prices = [r for r in res.records if isinstance(r, PriceRecord)]

    # Ceiling prices (Riz blanc importé, Sucre blanc, Huile, Farine)
    ceiling_prices = [r for r in prices if r.value_kind == "max"]
    assert len(ceiling_prices) == 4
    for cp in ceiling_prices:
        assert cp.actor_level == "official_ppn"
        assert cp.value_kind == "max"

    # Observed prices (Riz blanc local, Maïs, Manioc, Haricot)
    observed_prices = [r for r in prices if r.value_kind == "point"]
    assert len(observed_prices) == 4
    for op in observed_prices:
        assert op.actor_level == "retail"
        assert op.value_kind == "point"

    # Natural keys must never collide
    cp_keys = {cp.compute_natural_key("mincc_ppn") for cp in ceiling_prices}
    op_keys = {op.compute_natural_key("mincc_ppn") for op in observed_prices}
    assert cp_keys.isdisjoint(op_keys)


def test_mincc_ordinal_stock_never_converted_to_tonnes(
    run_context: RunContext,
    fixtures_dir: Path,
) -> None:
    """R1.5: Déclaration de stock ordinal non transformée en tonnes."""
    connector = MinccPpnConnector()
    html_file = fixtures_dir / "mincc_arrete_plafond_prix_2024_fr.html"
    content = html_file.read_bytes()

    assert run_context.bronze_store is not None
    art = run_context.bronze_store.put(
        source_id="mincc_ppn",
        content=content,
        mime_type="text/html",
        url="http://www.commerce.gov.mg/ppn/mincc_arrete_plafond_prix_2024_fr.html",
    )

    artifact = RawArtifact(
        source_record_id="",
        object_key=art.object_key,
        content_sha256=art.content_sha256,
        mime_type="text/html",
        url="http://www.commerce.gov.mg/ppn/mincc_arrete_plafond_prix_2024_fr.html",
        is_new=True,
        published_at=datetime(2024, 3, 1, 8, 0, tzinfo=UTC),
    )

    res = connector.parse(artifact, run_context)
    stocks = [r for r in res.records if isinstance(r, StockRecord)]

    # Qualitative-only stock for Sucre blanc
    sucre_stock = next(r for r in stocks if r.product_raw == "Sucre blanc")
    assert sucre_stock.stock_status == "tight"
    assert sucre_stock.quantity_value is None, "Ordinal stock must never be converted to float quantity"
    assert sucre_stock.unit_raw is None, "Unit must be None when no physical volume is given"

    # Qualitative-only stock for Maïs grain sec
    mais_stock = next(r for r in stocks if r.product_raw == "Maïs grain sec")
    assert mais_stock.stock_status == "sufficient"
    assert mais_stock.quantity_value is None
    assert mais_stock.unit_raw is None

    # Quantitative stock for Riz blanc importé
    riz_stock = next(r for r in stocks if r.product_raw == "Riz blanc importé")
    assert riz_stock.quantity_value == 1800.0
    assert riz_stock.unit_raw == "tonne"
    assert riz_stock.stock_status == "sufficient"


def test_mincc_stock_silence_never_defaults_to_sufficient(
    run_context: RunContext,
) -> None:
    """R1.5: Aucun statut de stock déduit d'un silence (pas de stock_status par défaut)."""
    connector = MinccPpnConnector()
    silent_html = b"""
    <html><body>
      <p>R\xc3\xa9gion : Analamanga</p>
      <p>du 2024-03-01 au 2024-03-07</p>
      <table>
        <thead>
          <tr><th>Produit</th><th>Stade</th><th>Prix</th><th>Stock</th></tr>
        </thead>
        <tbody>
          <tr><td>Farine de bl\xc3\xa9</td><td>D\xc3\xa9tail</td><td>3 200</td><td>-</td></tr>
        </tbody>
      </table>
    </body></html>
    """
    assert run_context.bronze_store is not None
    art = run_context.bronze_store.put(
        source_id="mincc_ppn",
        content=silent_html,
        mime_type="text/html",
        url="http://www.commerce.gov.mg/ppn/silent_stock.html",
    )
    artifact = RawArtifact(
        source_record_id="",
        object_key=art.object_key,
        content_sha256=art.content_sha256,
        mime_type="text/html",
        url="http://www.commerce.gov.mg/ppn/silent_stock.html",
        is_new=True,
    )

    res = connector.parse(artifact, run_context)
    # Price should be extracted
    prices = [r for r in res.records if isinstance(r, PriceRecord)]
    assert len(prices) == 1

    # Stock must NOT be created with fake "sufficient" status
    stocks = [r for r in res.records if isinstance(r, StockRecord)]
    assert len(stocks) == 0, "No StockRecord should be created from pure silence (-)"


def test_mincc_no_observations_publication_documented(
    run_context: RunContext,
    fixtures_dir: Path,
) -> None:
    """R1.5: Publication sans observation utile donne résultat documenté sans crash."""
    connector = MinccPpnConnector()
    html_file = fixtures_dir / "mincc_communique_sensibilisation_sans_prix.html"
    content = html_file.read_bytes()

    assert run_context.bronze_store is not None
    art = run_context.bronze_store.put(
        source_id="mincc_ppn",
        content=content,
        mime_type="text/html",
        url="http://www.commerce.gov.mg/ppn/mincc_communique_sensibilisation_sans_prix.html",
    )

    artifact = RawArtifact(
        source_record_id="",
        object_key=art.object_key,
        content_sha256=art.content_sha256,
        mime_type="text/html",
        url="http://www.commerce.gov.mg/ppn/mincc_communique_sensibilisation_sans_prix.html",
        is_new=True,
        published_at=datetime(2024, 3, 20, 8, 0, tzinfo=UTC),
    )

    res = connector.parse(artifact, run_context)
    assert len(res.records) == 0
    assert len(res.issues) >= 1
    assert any(iss["kind"] == "no_observations_found" for iss in res.issues)


def test_mincc_no_pii_ingested(
    run_context: RunContext,
    fixtures_dir: Path,
) -> None:
    """R1.5 / H4: Aucun champ personnel ingéré (noms, téléphones, emails de particuliers)."""
    connector = MinccPpnConnector()
    html_file = fixtures_dir / "mincc_arrete_plafond_prix_2024_fr.html"
    content = html_file.read_bytes()

    assert run_context.bronze_store is not None
    art = run_context.bronze_store.put(
        source_id="mincc_ppn",
        content=content,
        mime_type="text/html",
        url="http://www.commerce.gov.mg/ppn/mincc_arrete_plafond_prix_2024_fr.html",
    )

    artifact = RawArtifact(
        source_record_id="",
        object_key=art.object_key,
        content_sha256=art.content_sha256,
        mime_type="text/html",
        url="http://www.commerce.gov.mg/ppn/mincc_arrete_plafond_prix_2024_fr.html",
        is_new=True,
    )

    res = connector.parse(artifact, run_context)
    assert len(res.records) > 0

    forbidden_pii_snippets = [
        "Jean-Claude Rakotomalala",
        "drcc.analamanga@commerce.gov.mg",
        "+261 34 22 123 45",
        "034 22 123 45",
    ]

    for rec in res.records:
        rec_str = json.dumps(rec.model_dump(), default=str)
        for snippet in forbidden_pii_snippets:
            assert snippet not in rec_str, f"Found PII snippet '{snippet}' in record {rec_str}"


def test_mincc_authentic_corpus_golden(
    run_context: RunContext,
    fixtures_dir: Path,
    golden_dir: Path,
) -> None:
    """CC-R / R1.5: Authentic corpus evaluation on 2 distinct editions (Français, Malagasy).

    Requirements:
    - >= 2 distinct authentic editions
    - >= 30 annotated values in golden set (36 here)
    - Accuracy >= 99%
    - Recall >= 98%
    - Regulated ceiling vs observed prices preserved
    - Physical volume in tonnes vs ordinal stocks preserved
    """
    connector = MinccPpnConnector()
    golden_path = golden_dir / "mincc_authentic.expected.json"
    with open(golden_path, encoding="utf-8") as f:
        golden_data = json.load(f)

    editions = golden_data["editions"]
    assert len(editions) >= 2, "Must evaluate at least 2 distinct authentic editions"

    total_golden_records = 0
    all_parsed_records: list[RecordBase] = []

    for ed_key, ed_info in editions.items():
        html_file = fixtures_dir / ed_info["filename"]
        content = html_file.read_bytes()

        assert run_context.bronze_store is not None
        art = run_context.bronze_store.put(
            source_id="mincc_ppn",
            content=content,
            mime_type="text/html",
            url=f"http://www.commerce.gov.mg/ppn/{ed_info['filename']}",
        )

        artifact = RawArtifact(
            source_record_id=f"test-rec-{ed_key}",
            object_key=art.object_key,
            content_sha256=ed_info["content_sha256"],
            mime_type="text/html",
            url=f"http://www.commerce.gov.mg/ppn/{ed_info['filename']}",
            is_new=True,
            published_at=datetime.fromisoformat(ed_info["published_at"].replace("Z", "+00:00")),
        )

        res = connector.parse(artifact, run_context)
        assert len(res.issues) == 0, f"Unexpected issues in {ed_key}: {res.issues}"

        expected_records = ed_info["records"]
        total_golden_records += len(expected_records)
        assert len(res.records) == len(expected_records)
        all_parsed_records.extend(res.records)

        # Match and verify fields
        correct_fields = 0
        total_fields = 0

        for exp in expected_records:
            if exp["record_type"] == "price":
                matched_p = next(
                    (
                        r
                        for r in res.records
                        if isinstance(r, PriceRecord)
                        and r.product_raw == exp["product_raw"]
                        and r.actor_level == exp["actor_level"]
                    ),
                    None,
                )
                assert matched_p is not None, f"Expected price record {exp} not parsed in {ed_key}"

                for field in [
                    "product_raw",
                    "actor_level",
                    "location_raw",
                    "value_kind",
                    "price_raw",
                    "price_value",
                    "unit_raw",
                    "currency_raw",
                    "observed_or_imputed",
                ]:
                    total_fields += 1
                    if getattr(matched_p, field) == exp[field]:
                        correct_fields += 1

                total_fields += 2
                if matched_p.period_start.isoformat() == exp["period_start"]:
                    correct_fields += 1
                if matched_p.period_end.isoformat() == exp["period_end"]:
                    correct_fields += 1

            elif exp["record_type"] == "stock":
                matched_s = next(
                    (
                        r
                        for r in res.records
                        if isinstance(r, StockRecord) and r.product_raw == exp["product_raw"]
                    ),
                    None,
                )
                assert matched_s is not None, f"Expected stock record {exp} not parsed in {ed_key}"

                for field in [
                    "product_raw",
                    "location_raw",
                    "quantity_raw",
                    "quantity_value",
                    "unit_raw",
                    "stock_status",
                    "coverage_days",
                ]:
                    total_fields += 1
                    if getattr(matched_s, field) == exp[field]:
                        correct_fields += 1

                total_fields += 2
                if matched_s.period_start.isoformat() == exp["period_start"]:
                    correct_fields += 1
                if matched_s.period_end.isoformat() == exp["period_end"]:
                    correct_fields += 1

        accuracy = correct_fields / total_fields
        recall = len(res.records) / len(expected_records)

        assert accuracy >= 0.99, f"Edition {ed_key}: accuracy {accuracy:.2%} is below 99%"
        assert recall >= 0.98, f"Edition {ed_key}: recall {recall:.2%} is below 98%"

    # Corpus-wide criteria
    assert total_golden_records >= 30, f"Expected >= 30 records, got {total_golden_records}"
    assert len(all_parsed_records) == total_golden_records

    # Preserves ceiling prices vs observed prices
    price_kinds = {r.value_kind for r in all_parsed_records if isinstance(r, PriceRecord)}
    assert price_kinds == {"point", "max"}

    # Preserves physical volume in tonnes and ordinal stock
    stocks = [r for r in all_parsed_records if isinstance(r, StockRecord)]
    has_tonnes = any(s.unit_raw == "tonne" and s.quantity_value is not None for s in stocks)
    has_ordinal = any(s.unit_raw is None and s.quantity_value is None for s in stocks)
    assert has_tonnes is True
    assert has_ordinal is True

