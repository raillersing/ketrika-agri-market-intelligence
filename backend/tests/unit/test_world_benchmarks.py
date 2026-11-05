"""Unit tests for World Commodity Benchmarks & Maritime Freight connector (Lot 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.records import MacroRecord
from ketrika.connectors.world_benchmarks import (
    WORLD_BENCHMARKS_SOURCE_ID,
    WorldBenchmarksConnector,
    parse_world_benchmarks_csv,
)


@pytest.fixture
def raw_benchmarks_csv() -> bytes:
    fixture_path = (
        Path(__file__).parent.parent
        / "fixtures"
        / "world_benchmarks"
        / "world_fob_benchmarks_2024_2026.csv"
    )
    return fixture_path.read_bytes()


def test_parse_world_benchmarks_csv(raw_benchmarks_csv: bytes) -> None:
    records = parse_world_benchmarks_csv(raw_benchmarks_csv, source_record_id="test-source-record")
    assert len(records) > 0

    # Separate records by indicator
    rice_records = [r for r in records if r.indicator_code == "WORLD_FOB_RICE_WHITE_25_USD_MT"]
    oil_records = [r for r in records if r.indicator_code == "WORLD_FOB_PALM_OIL_USD_MT"]
    freight_records = [r for r in records if r.indicator_code == "FREIGHT_SCFI_CONTAINER_INDEX"]

    assert len(rice_records) == 34  # 34 months (2024-01 to 2026-10)
    assert len(oil_records) == 34
    assert len(freight_records) == 34

    # Check value ranges
    for r in rice_records:
        assert isinstance(r, MacroRecord)
        assert 400.0 <= r.value <= 700.0
        assert r.frequency == "monthly"
        assert r.geo_scope == "global"
        assert r.unit == "USD/MT"
        assert r.observed_or_imputed == "observed"
        assert r.period_start <= r.period_end

    for r in freight_records:
        assert isinstance(r, MacroRecord)
        assert 1500.0 <= r.value <= 4000.0
        assert r.unit == "index"
        assert r.geo_scope == "global"

    # Natural key determinism and uniqueness
    natural_keys = {r.compute_natural_key(WORLD_BENCHMARKS_SOURCE_ID) for r in records}
    assert len(natural_keys) == len(records)


def test_connector_discover_and_fetch_offline(raw_benchmarks_csv: bytes) -> None:
    connector = WorldBenchmarksConnector()
    ctx = RunContext(source_id=WORLD_BENCHMARKS_SOURCE_ID, offline=True)

    items = list(connector.discover(ctx))
    assert len(items) == 1
    assert items[0].url.endswith("Pink_Sheet.csv")

    # In-memory mock artifact
    artifact = RawArtifact(
        source_record_id="sr-1234",
        object_key="bronze/world_benchmarks/latest.csv",
        content_sha256="abc123sha",
        mime_type="text/csv",
        url=items[0].url,
        is_new=True,
    )

    class MockBronzeStore:
        def get(self, key: str) -> bytes:
            return raw_benchmarks_csv

        def get_bytes(self, key: str) -> bytes:
            return raw_benchmarks_csv

    ctx.bronze_store = MockBronzeStore()  # type: ignore[assignment]
    result = connector.parse(artifact, ctx)

    assert len(result.issues) == 0
    assert len(result.records) == 102  # 34 * 3 series
    assert result.parser_version == "1.0.0"
