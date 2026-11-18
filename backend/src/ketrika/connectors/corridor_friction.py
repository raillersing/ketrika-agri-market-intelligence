"""Corridor Friction & Transport Logistics connector (ADR-164 / SPECS §27).

Ingests transport baseline costs, fuel cost share, road condition multipliers and security
friction / risk surcharges across the 4 critical national corridors:
- RN2 (Toamasina - Antananarivo, Port transit corridor)
- RN4 (Marovoay / Mahajanga - Antananarivo, Rice granary corridor)
- RN7 (Fianarantsoa / Toliara - Antananarivo, South food corridor)
- RN34 (Bongolava / Tsiroanomandidy - Antananarivo, Maize / Bean granary corridor)
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import ClassVar

from ketrika.connectors.base import (
    DiscoveredItem,
    ParseResult,
    RawArtifact,
    RunContext,
)
from ketrika.connectors.records import MacroRecord

logger = logging.getLogger(__name__)

CORRIDOR_FRICTION_SOURCE_ID = "corridor_friction"
CORRIDOR_FRICTION_URL = "https://www.transports.gov.mg/donnees/couts-corridors.csv"


def parse_corridor_friction_csv(
    content: str | bytes,
    source_record_id: str | None = None,
) -> list[MacroRecord]:
    """Parse raw corridor friction CSV text into normalized MacroRecord observations."""
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig", errors="replace")
    else:
        text = content

    reader = csv.DictReader(io.StringIO(text))
    records: list[MacroRecord] = []

    for row_idx, row in enumerate(reader):
        date_str = (row.get("date") or "").strip()
        corridor = (row.get("corridor_code") or "").strip()
        base_cost_str = (row.get("base_cost_per_ton_mga") or "").strip()
        sec_fric_str = (row.get("security_friction_pct") or "").strip()
        road_fact_str = (row.get("road_condition_factor") or "").strip()
        dist_str = (row.get("distance_km") or "").strip()
        origin_pcode = (row.get("origin_pcode") or "").strip()
        dest_pcode = (row.get("destination_pcode") or "").strip()

        if not date_str or not corridor or not base_cost_str:
            continue

        try:
            obs_date = date.fromisoformat(date_str)
        except ValueError:
            continue

        try:
            base_cost = float(base_cost_str.replace(" ", "").replace(",", "."))
        except ValueError:
            continue

        # End of month date
        if obs_date.month == 12:
            period_end = date(obs_date.year, 12, 31)
        else:
            next_m = date(obs_date.year, obs_date.month + 1, 1)
            period_end = date.fromordinal(next_m.toordinal() - 1)

        pub_time = datetime.combine(period_end, datetime.min.time(), tzinfo=UTC)

        # 1. Base Freight Cost (MGA/Tonne)
        rec_cost = MacroRecord(
            indicator_code=f"CORRIDOR_BASE_COST_{corridor}_TON_MGA",
            indicator_name=f"Coût fret de base corridor {corridor} (MGA/Tonne)",
            frequency="monthly",
            unit="MGA/Tonne",
            geo_scope=origin_pcode or "national",
            period_start=obs_date,
            period_end=period_end,
            value_raw=base_cost_str,
            value=base_cost,
            vintage="final",
            observed_or_imputed="observed",
            published_at=pub_time,
            evidence={
                "row_index": row_idx,
                "corridor": corridor,
                "distance_km": float(dist_str) if dist_str else None,
                "origin_pcode": origin_pcode,
                "destination_pcode": dest_pcode,
                "source_record_id": source_record_id,
            },
        )
        records.append(rec_cost)

        # 2. Security Friction Surcharge (%)
        if sec_fric_str:
            try:
                sec_fric = float(sec_fric_str.replace(" ", "").replace(",", "."))
                rec_sec = MacroRecord(
                    indicator_code=f"CORRIDOR_SECURITY_FRICTION_{corridor}_PCT",
                    indicator_name=f"Surcharge friction sécuritaire corridor {corridor} (ratio)",
                    frequency="monthly",
                    unit="ratio",
                    geo_scope=origin_pcode or "national",
                    period_start=obs_date,
                    period_end=period_end,
                    value_raw=sec_fric_str,
                    value=sec_fric,
                    vintage="final",
                    observed_or_imputed="observed",
                    published_at=pub_time,
                    evidence={
                        "row_index": row_idx,
                        "corridor": corridor,
                        "metric": "security_friction",
                        "source_record_id": source_record_id,
                    },
                )
                records.append(rec_sec)
            except ValueError:
                pass

        # 3. Road Condition Multiplier
        if road_fact_str:
            try:
                road_fact = float(road_fact_str.replace(" ", "").replace(",", "."))
                rec_road = MacroRecord(
                    indicator_code=f"CORRIDOR_ROAD_FACTOR_{corridor}",
                    indicator_name=f"Facteur état routier corridor {corridor}",
                    frequency="monthly",
                    unit="multiplier",
                    geo_scope=origin_pcode or "national",
                    period_start=obs_date,
                    period_end=period_end,
                    value_raw=road_fact_str,
                    value=road_fact,
                    vintage="final",
                    observed_or_imputed="observed",
                    published_at=pub_time,
                    evidence={
                        "row_index": row_idx,
                        "corridor": corridor,
                        "metric": "road_condition_factor",
                        "source_record_id": source_record_id,
                    },
                )
                records.append(rec_road)
            except ValueError:
                pass

    return records


class CorridorFrictionConnector:
    """Connector for corridor transport costs and security friction."""

    source_id: ClassVar[str] = CORRIDOR_FRICTION_SOURCE_ID
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, run_ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover the monthly corridor transport feed."""
        yield DiscoveredItem(
            url=CORRIDOR_FRICTION_URL,
            partition_key="latest",
            published_at=datetime.now(UTC),
        )

    def fetch(self, item: DiscoveredItem, run_ctx: RunContext) -> RawArtifact:
        """Fetch corridor friction feed or load offline fixture."""
        if run_ctx.offline:
            from pathlib import Path

            fixture_path = (
                Path(__file__).parent.parent.parent.parent
                / "tests"
                / "fixtures"
                / "corridors"
                / "corridor_freight_benchmarks_2024_2026.csv"
            )
            data = fixture_path.read_bytes()
            if run_ctx.bronze_store is not None:
                art = run_ctx.bronze_store.put(
                    source_id=self.source_id,
                    content=data,
                    mime_type="text/csv",
                    url=item.url,
                )
                return RawArtifact(
                    source_record_id="",
                    object_key=art.object_key,
                    content_sha256=art.content_sha256,
                    mime_type="text/csv",
                    url=item.url,
                    is_new=True,
                )
        return run_ctx.fetch_and_store(item, mime_type="text/csv")

    def parse(self, artifact: RawArtifact, run_ctx: RunContext) -> ParseResult:
        """Parse raw artifact from Bronze into normalized MacroRecord observations."""
        if run_ctx.bronze_store is None:
            from ketrika.core.bronze import BronzeStore

            store = BronzeStore()
        else:
            store = run_ctx.bronze_store

        content = store.get(artifact.object_key)
        records = parse_corridor_friction_csv(content, source_record_id=artifact.source_record_id)

        return ParseResult(
            records=records,
            issues=[],
            parser_version="1.0.0",
        )
