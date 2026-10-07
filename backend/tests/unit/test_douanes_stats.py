"""Unit and golden tests for Douanes statistics connector (SPECS §5.2, §8, T4.3)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.douanes_stats import DouanesStatsConnector
from ketrika.connectors.records import TradeFlowRecord
from ketrika.core.bronze import BronzeArtifact, BronzeStore
from ketrika.core.policy import PolicyEngine
from ketrika.core.registry import find_repo_root


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
