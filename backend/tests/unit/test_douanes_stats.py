"""Unit and golden tests for Douanes statistics connector (SPECS §5.2, §8, T4.3)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_httpserver import HTTPServer

from ketrika.connectors.base import DiscoveredItem, RawArtifact, RunContext
from ketrika.connectors.douanes_stats import DouanesStatsConnector
from ketrika.connectors.records import PriceRecord, TradeFlowRecord
from ketrika.core.bronze import BronzeArtifact, BronzeStore
from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import MemoryBudgetBackend
from ketrika.core.policy import PolicyEngine
from ketrika.core.registry import find_repo_root


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
    return base_dir / "tests" / "fixtures" / "douanes_stats"


@pytest.fixture
def golden_dir(base_dir: Path) -> Path:
    return base_dir / "tests" / "golden" / "douanes_stats"


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
        obj_key = f"{source_id}/2024/04/{sha}.csv"
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
        source_id="douanes_stats",
        bronze_store=mock_bronze,
        policy_engine=PolicyEngine(),
        offline=True,
    )


def test_discover_douanes_stats(run_context: RunContext):
    """Test that discover yields the expected monthly trade statistics partitions."""
    connector = DouanesStatsConnector()
    items = list(connector.discover(run_context))

    assert len(items) >= 1
    it = items[0]
    assert it.partition_key == "douanes_stats_2024"
    assert "douanes.gov.mg" in it.url
    assert it.published_at is not None


def test_parse_douanes_stats_2024(
    run_context: RunContext,
    fixtures_dir: Path,
):
    """Test deterministic CSV parsing of Douanes external trade dataset (CC1)."""
    connector = DouanesStatsConnector()
    csv_file = fixtures_dir / "douanes_stats_2024.csv"
    assert csv_file.exists()
    content = csv_file.read_bytes()

    assert run_context.bronze_store is not None
    art = run_context.bronze_store.put(
        source_id="douanes_stats",
        content=content,
        mime_type="text/csv",
        url="https://www.douanes.gov.mg/stats/douanes_stats_2024.csv",
    )

    artifact = RawArtifact(
        source_record_id="",
        object_key=art.object_key,
        content_sha256=art.content_sha256,
        mime_type="text/csv",
        url="https://www.douanes.gov.mg/stats/douanes_stats_2024.csv",
        is_new=True,
        published_at=datetime(2024, 4, 1, 8, 0, tzinfo=UTC),
    )

    res = connector.parse(artifact, run_context)
    assert len(res.issues) == 0
    assert len(res.records) == 36

    flows = [r for r in res.records if isinstance(r, TradeFlowRecord)]
    assert len(flows) == 36

    # Verify flow types
    import_flows = [r for r in flows if r.flow == "import"]
    export_flows = [r for r in flows if r.flow == "export"]
    assert len(import_flows) == 27  # 9 import commodities * 3 months
    assert len(export_flows) == 9  # 3 export commodities * 3 months

    for f in flows:
        assert f.hs_code is not None and len(f.hs_code) in (6, 8)
        assert f.product_raw != ""
        assert f.partner_raw is not None and f.partner_raw != ""
        assert f.weight_kg is not None and f.weight_kg > 0
        assert f.value_mga is not None and f.value_mga > 0
        assert f.period_start <= f.period_end
        assert f.extraction_method == "deterministic"


def test_golden_douanes_stats_2024(
    run_context: RunContext,
    fixtures_dir: Path,
    golden_dir: Path,
):
    """Golden acceptance test: accuracy >= 99% and recall >= 98% on 36 trade flows (CC2)."""
    connector = DouanesStatsConnector()
    csv_file = fixtures_dir / "douanes_stats_2024.csv"
    golden_file = golden_dir / "douanes_stats_2024.expected.json"
    assert csv_file.exists()
    assert golden_file.exists()

    content = csv_file.read_bytes()
    assert run_context.bronze_store is not None
    art = run_context.bronze_store.put(
        source_id="douanes_stats",
        content=content,
        mime_type="text/csv",
        url="https://www.douanes.gov.mg/stats/douanes_stats_2024.csv",
    )

    artifact = RawArtifact(
        source_record_id="",
        object_key=art.object_key,
        content_sha256=art.content_sha256,
        mime_type="text/csv",
        url="https://www.douanes.gov.mg/stats/douanes_stats_2024.csv",
        is_new=True,
        published_at=datetime(2024, 4, 1, 8, 0, tzinfo=UTC),
    )

    res = connector.parse(artifact, run_context)

    with open(golden_file, encoding="utf-8") as gf:
        golden = json.load(gf)

    expected_records = golden["records"]
    assert len(expected_records) >= 30  # CC2 rule

    total_expected = len(expected_records)
    total_matched = 0
    total_field_checks = 0
    total_field_matches = 0

    for exp in expected_records:
        candidates: list[TradeFlowRecord] = [
            r
            for r in res.records
            if isinstance(r, TradeFlowRecord)
            and r.flow == exp["flow"]
            and r.product_raw == exp["product_raw"]
            and r.partner_raw == exp["partner_raw"]
            and r.period_start.isoformat() == exp["period_start"]
        ]
        assert len(candidates) >= 1, f"Missing expected trade record: {exp}"
        matched = candidates[0]
        total_matched += 1

        # Check fields: hs_code, weight_kg, value_mga, value_usd, partner_iso3
        total_field_checks += 5
        if matched.hs_code == exp["hs_code"]:
            total_field_matches += 1
        if matched.weight_kg == exp["weight_kg"]:
            total_field_matches += 1
        if matched.value_mga == exp["value_mga"]:
            total_field_matches += 1
        if matched.value_usd == exp["value_usd"]:
            total_field_matches += 1
        if matched.partner_iso3 == exp["partner_iso3"]:
            total_field_matches += 1

    recall = total_matched / total_expected
    accuracy = total_field_matches / total_field_checks

    assert recall >= 0.98, f"Recall was {recall:.2%}, expected >= 98%"
    assert accuracy >= 0.99, f"Accuracy was {accuracy:.2%}, expected >= 99%"


def test_parse_revision_snapshots(
    run_context: RunContext,
    fixtures_dir: Path,
):
    """Test that revision snapshots v1 and v2 parse and exhibit identical natural keys with modified values."""
    connector = DouanesStatsConnector()
    v1_file = fixtures_dir / "douanes_snapshot_v1.csv"
    v2_file = fixtures_dir / "douanes_snapshot_v2.csv"
    assert v1_file.exists()
    assert v2_file.exists()

    assert run_context.bronze_store is not None
    art1 = run_context.bronze_store.put(
        source_id="douanes_stats",
        content=v1_file.read_bytes(),
        mime_type="text/csv",
        url="https://www.douanes.gov.mg/stats/douanes_snapshot_v1.csv",
    )
    art2 = run_context.bronze_store.put(
        source_id="douanes_stats",
        content=v2_file.read_bytes(),
        mime_type="text/csv",
        url="https://www.douanes.gov.mg/stats/douanes_snapshot_v2.csv",
    )

    res1 = connector.parse(
        RawArtifact(
            source_record_id="",
            object_key=art1.object_key,
            content_sha256=art1.content_sha256,
            mime_type="text/csv",
            url=art1.url,
            is_new=True,
        ),
        run_context,
    )
    res2 = connector.parse(
        RawArtifact(
            source_record_id="",
            object_key=art2.object_key,
            content_sha256=art2.content_sha256,
            mime_type="text/csv",
            url=art2.url,
            is_new=True,
        ),
        run_context,
    )

    assert len(res1.records) == 4
    assert len(res2.records) == 4

    # Flow 0 (India rice import) in v1 vs v2
    rec1 = res1.records[0]
    rec2 = res2.records[0]
    assert isinstance(rec1, TradeFlowRecord)
    assert isinstance(rec2, TradeFlowRecord)

    # Identical natural key
    nk1 = rec1.compute_natural_key("douanes_stats")
    nk2 = rec2.compute_natural_key("douanes_stats")
    assert nk1 == nk2, "Natural keys must match across revisions"

    # Revised values in v2
    assert rec1.weight_kg == 25000000.0
    assert rec2.weight_kg == 26500000.0
    assert rec1.value_mga == 75000000000.0
    assert rec2.value_mga == 79500000000.0


def test_douanes_dynamic_catalog_discovery(httpserver: HTTPServer) -> None:
    """R1.6: Dynamic discovery of customs statistics editions via CatalogDiscoveryEngine."""
    catalog_html = """
    <!DOCTYPE html>
    <html>
      <body>
        <div class="stats-downloads">
          <a href="/stats/douanes_stats_2024.csv">Statistiques du Commerce Extérieur 2024 (CSV)</a>
          <a href="/stats/douanes_stats_2023.csv">Statistiques Annuelles 2023 (CSV)</a>
          <a href="/stats/douanes_stats_q1_2024.xlsx">Tableau de Bord T1 2024 (Excel)</a>
          <a href="https://untrusted-external.com/stats/fake.csv">Lien Externe Non Autorisé</a>
        </div>
      </body>
    </html>
    """
    httpserver.expect_request("/statistiques").respond_with_data(catalog_html, content_type="text/html")

    policy = PolicyEngine()
    policy.set_robots_txt(httpserver.url_for("/"), "User-agent: *\nDisallow:\n")
    http_client = PoliteHttpClient(
        policy_engine=policy,
        budget_backend=MemoryBudgetBackend(),
        allow_loopback=True,
    )
    http_client.bind_source("douanes_stats", daily_request_budget=100, max_rps=10.0)

    connector = DouanesStatsConnector()
    ctx = RunContext(
        source_id="douanes_stats",
        http_client=http_client,
        policy_engine=policy,
        metadata={
            "catalog_url": httpserver.url_for("/statistiques"),
            "allow_loopback": True,
            "allowed_domains": ["127.0.0.1", "localhost"],
        },
    )

    discovered = list(connector.discover(ctx))
    assert len(discovered) == 3
    urls = [d.url for d in discovered]
    assert any("douanes_stats_2024.csv" in u for u in urls)
    assert any("douanes_stats_2023.csv" in u for u in urls)
    assert any("douanes_stats_q1_2024.xlsx" in u for u in urls)
    assert not any("untrusted-external.com" in u for u in urls)
    assert all(d.hints.get("publisher") == "Douanes Malagasy / DGD" for d in discovered)


def test_douanes_annual_total_distinct_from_monthly(
    run_context: RunContext,
    fixtures_dir: Path,
) -> None:
    """R1.6: Distinct annual total rows from monthly flows to prevent double-counting."""
    connector = DouanesStatsConnector()
    csv_file = fixtures_dir / "douanes_stats_2023.csv"
    assert csv_file.exists()

    assert run_context.bronze_store is not None
    art = run_context.bronze_store.put(
        source_id="douanes_stats",
        content=csv_file.read_bytes(),
        mime_type="text/csv",
        url="https://www.douanes.gov.mg/stats/douanes_stats_2023.csv",
    )
    artifact = RawArtifact(
        source_record_id="",
        object_key=art.object_key,
        content_sha256=art.content_sha256,
        mime_type="text/csv",
        url=art.url,
        is_new=True,
        published_at=datetime(2024, 1, 15, 8, 0, tzinfo=UTC),
    )

    res = connector.parse(artifact, run_context)
    assert len(res.records) == 38  # 36 monthly + 2 annual totals

    annual_records = [
        r
        for r in res.records
        if isinstance(r, TradeFlowRecord)
        and r.evidence.get("aggregation_level") == "annual_total"
    ]
    monthly_records = [
        r
        for r in res.records
        if isinstance(r, TradeFlowRecord)
        and r.evidence.get("aggregation_level") == "monthly"
    ]
    assert len(annual_records) == 2
    assert len(monthly_records) == 36

    # Verify period bounds of annual total
    for ar in annual_records:
        assert ar.period_start == date(2023, 1, 1)
        assert ar.period_end == date(2023, 12, 31)

    # Verify consistency: sum of months matches official annual total
    india_rice_monthly = [
        r
        for r in monthly_records
        if r.flow == "import"
        and r.hs_code == "10063000"
        and r.partner_iso3 == "IND"
    ]
    assert len(india_rice_monthly) == 3
    sum_weight = sum(r.weight_kg or 0 for r in india_rice_monthly)
    sum_val_mga = sum(r.value_mga or 0 for r in india_rice_monthly)

    india_rice_annual = next(
        r
        for r in annual_records
        if r.flow == "import"
        and r.hs_code == "10063000"
        and r.partner_iso3 == "IND"
    )
    assert india_rice_annual.weight_kg == sum_weight
    assert india_rice_annual.value_mga == sum_val_mga

    # Monthly and annual natural keys never collide
    annual_nk = india_rice_annual.compute_natural_key("douanes_stats")
    for mr in india_rice_monthly:
        assert mr.compute_natural_key("douanes_stats") != annual_nk


def test_douanes_unit_value_never_confused_with_retail_price(
    run_context: RunContext,
    fixtures_dir: Path,
) -> None:
    """R1.6: Imported unit value is a derived indicator, never confused with retail price."""
    connector = DouanesStatsConnector()
    csv_file = fixtures_dir / "douanes_stats_2024.csv"
    assert csv_file.exists()

    assert run_context.bronze_store is not None
    art = run_context.bronze_store.put(
        source_id="douanes_stats",
        content=csv_file.read_bytes(),
        mime_type="text/csv",
        url="https://www.douanes.gov.mg/stats/douanes_stats_2024.csv",
    )
    artifact = RawArtifact(
        source_record_id="",
        object_key=art.object_key,
        content_sha256=art.content_sha256,
        mime_type="text/csv",
        url=art.url,
        is_new=True,
    )

    res = connector.parse(artifact, run_context)
    # MUST only produce TradeFlowRecord, NEVER PriceRecord
    assert all(isinstance(r, TradeFlowRecord) for r in res.records)
    assert not any(isinstance(r, PriceRecord) for r in res.records)

    # Unit values are derivable as indicators
    india_rice = next(
        r
        for r in res.records
        if isinstance(r, TradeFlowRecord)
        and r.partner_iso3 == "IND"
        and r.period_start == date(2024, 1, 1)
    )
    assert india_rice.value_mga == 75000000000.0
    assert india_rice.weight_kg == 25000000.0
    unit_val_mga_per_kg = india_rice.value_mga / india_rice.weight_kg
    assert unit_val_mga_per_kg == 3000.0  # Ar/kg CIF import indicator


def test_douanes_hs_code_validation_and_unmapped(
    run_context: RunContext,
    fixtures_dir: Path,
) -> None:
    """R1.6: Validate HS nomenclature and record issues on unverified or malformed codes."""
    connector = DouanesStatsConnector()
    csv_file = fixtures_dir / "douanes_stats_invalid_codes.csv"
    assert csv_file.exists()

    assert run_context.bronze_store is not None
    art = run_context.bronze_store.put(
        source_id="douanes_stats",
        content=csv_file.read_bytes(),
        mime_type="text/csv",
        url="https://www.douanes.gov.mg/stats/douanes_stats_invalid_codes.csv",
    )
    artifact = RawArtifact(
        source_record_id="",
        object_key=art.object_key,
        content_sha256=art.content_sha256,
        mime_type="text/csv",
        url=art.url,
        is_new=True,
    )

    res = connector.parse(artifact, run_context)
    assert len(res.issues) >= 3

    # Check unverified HS code issues
    hs_issues = [iss for iss in res.issues if iss.get("kind") == "unverified_hs_code"]
    assert len(hs_issues) >= 2
    assert any("1006" in iss.get("hs_code", "") for iss in hs_issues)  # too short
    assert any("99999999" in iss.get("hs_code", "") for iss in hs_issues)  # outside PPN chapters

    # Check missing period issue
    missing_period_issues = [iss for iss in res.issues if iss.get("kind") == "missing_period"]
    assert len(missing_period_issues) >= 1

    # Check invalid month issue
    invalid_month_issues = [iss for iss in res.issues if iss.get("kind") == "invalid_month"]
    assert len(invalid_month_issues) >= 1


def test_douanes_authentic_corpus_golden(
    run_context: RunContext,
    fixtures_dir: Path,
    golden_dir: Path,
) -> None:
    """R1.6 & CC-R: Evaluate authentic Douanes corpus across >= 2 editions with >= 30 values."""
    connector = DouanesStatsConnector()
    golden_path = golden_dir / "douanes_authentic.expected.json"
    assert golden_path.exists()

    with open(golden_path, encoding="utf-8") as f:
        golden_data = json.load(f)

    editions = golden_data["editions"]
    assert len(editions) >= 2, "Must evaluate at least 2 distinct authentic editions"

    total_golden_records = 0
    all_parsed_records: list[TradeFlowRecord] = []

    for ed_key, ed_info in editions.items():
        csv_file = fixtures_dir / ed_info["filename"]
        assert csv_file.exists(), f"Fixture {ed_info['filename']} missing"
        content = csv_file.read_bytes()

        assert run_context.bronze_store is not None
        art = run_context.bronze_store.put(
            source_id="douanes_stats",
            content=content,
            mime_type="text/csv",
            url=f"https://www.douanes.gov.mg/stats/{ed_info['filename']}",
        )

        artifact = RawArtifact(
            source_record_id="",
            object_key=art.object_key,
            content_sha256=art.content_sha256,
            mime_type="text/csv",
            url=art.url,
            is_new=True,
            published_at=datetime.fromisoformat(ed_info["published_at"]),
        )

        res = connector.parse(artifact, run_context)
        trade_records = [r for r in res.records if isinstance(r, TradeFlowRecord)]
        all_parsed_records.extend(trade_records)

        expected_records = ed_info["records"]
        total_golden_records += len(expected_records)

        total_fields = 0
        correct_fields = 0

        for exp in expected_records:
            matched = next(
                (
                    r
                    for r in trade_records
                    if r.flow == exp["flow"]
                    and r.product_raw == exp["product_raw"]
                    and r.partner_raw == exp["partner_raw"]
                    and r.period_start.isoformat() == exp["period_start"]
                    and r.period_end.isoformat() == exp["period_end"]
                ),
                None,
            )
            assert matched is not None, f"Expected record {exp} not parsed in {ed_key}"

            for field in [
                "flow",
                "product_raw",
                "hs_code",
                "partner_raw",
                "partner_iso3",
                "weight_kg",
                "value_mga",
                "value_usd",
            ]:
                total_fields += 1
                if getattr(matched, field) == exp[field]:
                    correct_fields += 1

            total_fields += 2
            if matched.period_start.isoformat() == exp["period_start"]:
                correct_fields += 1
            if matched.period_end.isoformat() == exp["period_end"]:
                correct_fields += 1

        accuracy = correct_fields / total_fields
        recall = len(trade_records) / len(expected_records)

        assert accuracy >= 0.99, f"Edition {ed_key}: accuracy {accuracy:.2%} is below 99%"
        assert recall >= 0.98, f"Edition {ed_key}: recall {recall:.2%} is below 98%"

    # Corpus-wide criteria
    assert total_golden_records >= 30, f"Expected >= 30 records, got {total_golden_records}"
    assert len(all_parsed_records) == total_golden_records
    assert total_golden_records == 74


def test_douanes_fetch_offline_and_metadata_overrides(run_context: RunContext) -> None:
    """Test fetch in offline mode with BronzeStore and discover metadata overrides."""
    connector = DouanesStatsConnector()

    # Test file_urls metadata
    ctx_meta = RunContext(
        source_id="douanes_stats",
        bronze_store=run_context.bronze_store,
        offline=True,
        metadata={"file_urls": ["https://www.douanes.gov.mg/stats/douanes_stats_2024.csv"]},
    )
    items = list(connector.discover(ctx_meta))
    assert len(items) == 1
    assert items[0].partition_key == "douanes_stats_2024"

    # Test file_url single metadata
    ctx_single = RunContext(
        source_id="douanes_stats",
        bronze_store=run_context.bronze_store,
        offline=True,
        metadata={"file_url": "https://www.douanes.gov.mg/stats/douanes_stats_2023.csv"},
    )
    items_single = list(connector.discover(ctx_single))
    assert len(items_single) == 1
    assert items_single[0].partition_key == "douanes_stats_2023"

    # Test fetch offline into bronze_store
    artifact = connector.fetch(items[0], ctx_meta)
    assert artifact.object_key.startswith("douanes_stats/")
    assert len(artifact.content_sha256) == 64
    assert artifact.mime_type == "text/csv"
    assert artifact.is_new is True

    # Test fetch missing offline fixture raises FileNotFoundError
    missing_item = DiscoveredItem(
        url="https://www.douanes.gov.mg/stats/missing_non_existent.csv",
        partition_key="missing_non_existent",
    )
    with pytest.raises(FileNotFoundError):
        connector.fetch(missing_item, ctx_meta)


