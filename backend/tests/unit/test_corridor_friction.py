"""Unit tests for Corridor Friction & Transport Logistics connector (Lot 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.corridor_friction import (
    CORRIDOR_FRICTION_SOURCE_ID,
    CorridorFrictionConnector,
    parse_corridor_friction_csv,
)
from ketrika.connectors.records import MacroRecord


@pytest.fixture
def raw_corridors_csv() -> bytes:
    fixture_path = (
        Path(__file__).parent.parent
        / "fixtures"
        / "corridors"
        / "corridor_freight_benchmarks_2024_2026.csv"
    )
    return fixture_path.read_bytes()


def test_parse_corridor_friction_csv(raw_corridors_csv: bytes) -> None:
    records = parse_corridor_friction_csv(raw_corridors_csv, source_record_id="test-source-record")
    assert len(records) > 0

    # Separate records by corridor
    rn2_cost = [r for r in records if r.indicator_code == "CORRIDOR_BASE_COST_RN2_TON_MGA"]
    rn4_sec = [r for r in records if r.indicator_code == "CORRIDOR_SECURITY_FRICTION_RN4_PCT"]
    rn34_cost = [r for r in records if r.indicator_code == "CORRIDOR_BASE_COST_RN34_TON_MGA"]

    assert len(rn2_cost) == 34  # 34 months (2024-01 to 2026-10)
    assert len(rn4_sec) == 34
    assert len(rn34_cost) == 34

    # Check values and units
    for r in rn2_cost:
        assert isinstance(r, MacroRecord)
        assert r.value is not None
        assert 200000.0 <= r.value <= 400000.0
        assert r.unit == "MGA/Tonne"
        assert r.frequency == "monthly"
        assert r.observed_or_imputed == "observed"

    for r in rn4_sec:
        assert isinstance(r, MacroRecord)
        assert r.value is not None
        assert 0.05 <= r.value <= 0.35
        assert r.unit == "ratio"

    # Natural key determinism and uniqueness
    natural_keys = {r.compute_natural_key(CORRIDOR_FRICTION_SOURCE_ID) for r in records}
    assert len(natural_keys) == len(records)


def test_connector_discover_and_fetch_offline(raw_corridors_csv: bytes) -> None:
    connector = CorridorFrictionConnector()
    ctx = RunContext(source_id=CORRIDOR_FRICTION_SOURCE_ID, offline=True)

    items = list(connector.discover(ctx))
    assert len(items) == 1
    assert items[0].url.endswith("couts-corridors.csv")

    artifact = RawArtifact(
        source_record_id="sr-5678",
        object_key="bronze/corridor_friction/latest.csv",
        content_sha256="def456sha",
        mime_type="text/csv",
        url=items[0].url,
        is_new=True,
    )

    class MockBronzeStore:
        def get(self, key: str) -> bytes:
            return raw_corridors_csv

        def get_bytes(self, key: str) -> bytes:
            return raw_corridors_csv

    ctx.bronze_store = MockBronzeStore()  # type: ignore[assignment]
    result = connector.parse(artifact, ctx)

    assert len(result.issues) == 0
    # Each row has cost + security + road factor = 3 indicators * 34 months * 3 corridors = 306 records
    assert len(result.records) == 306
    assert result.parser_version == "1.0.0"
