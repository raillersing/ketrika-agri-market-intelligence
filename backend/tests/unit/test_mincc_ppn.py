"""Unit and golden tests for MinCC PPN price and stock connector (SPECS §5.2, §8, T4.2)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.mincc_ppn import MinccPpnConnector
from ketrika.connectors.records import PriceRecord, StockRecord
from ketrika.core.bronze import BronzeArtifact, BronzeStore
from ketrika.core.policy import PolicyEngine
from ketrika.core.registry import find_repo_root
from ketrika.extraction.llm.replay import ReplayClient


@pytest.fixture
def repo_root() -> Path:
    return find_repo_root()


@pytest.fixture
def base_dir(repo_root: Path) -> Path:
    if Path("/app/tests").exists():
        return Path("/app")
    elif (repo_root / "backend").exists():
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
    golden_files = sorted(golden_dir.glob("*.expected.json"))
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
