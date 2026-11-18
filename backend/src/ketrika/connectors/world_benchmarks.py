"""World Commodity Benchmarks & Maritime Freight connector (ADR-164 / SPECS §27).

Ingests international FOB benchmarks for key food commodities (White Rice 25% FOB,
Crude Palm Oil MDEX FOB, Wheat HRW FOB, Raw Sugar #11 FOB) and maritime container
freight indices (SCFI) to drive the dynamic Import Parity Price (IPP) and multivariate
causal price forecasts.
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

WORLD_BENCHMARKS_SOURCE_ID = "world_benchmarks"
WORLD_BENCHMARKS_URL = "https://databank.worldbank.org/data/download/Pink_Sheet.csv"

# Map commodity codes to normative macro indicator definitions
COMMODITY_INDICATOR_MAP = {
    "RICE_WHITE_25_FOB": {
        "code": "WORLD_FOB_RICE_WHITE_25_USD_MT",
        "name": "Cours Mondial Riz Blanc 25% Brisures FOB Asie (USD/MT)",
        "unit": "USD/MT",
        "category": "world_commodity_fob",
    },
    "PALM_OIL_CPO_FOB": {
        "code": "WORLD_FOB_PALM_OIL_USD_MT",
        "name": "Cours Mondial Huile de Palme Brute CPO FOB Malaisie (USD/MT)",
        "unit": "USD/MT",
        "category": "world_commodity_fob",
    },
    "WHEAT_HRW_FOB": {
        "code": "WORLD_FOB_WHEAT_HRW_USD_MT",
        "name": "Cours Mondial Blé Meunier US HRW FOB (USD/MT)",
        "unit": "USD/MT",
        "category": "world_commodity_fob",
    },
    "SUGAR_RAW_FOB": {
        "code": "WORLD_FOB_SUGAR_RAW_USD_MT",
        "name": "Cours Mondial Sucre Brut n°11 FOB (USD/MT)",
        "unit": "USD/MT",
        "category": "world_commodity_fob",
    },
}


def parse_world_benchmarks_csv(
    content: str | bytes,
    source_record_id: str | None = None,
) -> list[MacroRecord]:
    """Parse raw CSV text or bytes into normalized MacroRecord observations."""
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig", errors="replace")
    else:
        text = content

    reader = csv.DictReader(io.StringIO(text))
    records: list[MacroRecord] = []

    for row_idx, row in enumerate(reader):
        date_str = (row.get("date") or "").strip()
        comm_code = (row.get("commodity_code") or "").strip()
        price_str = (row.get("price_fob_usd_mt") or "").strip()
        freight_str = (row.get("freight_scfi_index") or "").strip()
        source_ref = (row.get("source_reference") or "").strip()

        if not date_str or not comm_code or not price_str:
            continue

        try:
            obs_date = date.fromisoformat(date_str)
        except ValueError:
            continue

        try:
            fob_val = float(price_str.replace(" ", "").replace(",", "."))
        except ValueError:
            continue

        meta = COMMODITY_INDICATOR_MAP.get(comm_code)
        if meta:
            ind_code = meta["code"]
            ind_name = meta["name"]
            unit = meta["unit"]
        else:
            ind_code = f"WORLD_FOB_{comm_code}_USD_MT"
            ind_name = (row.get("commodity_name") or comm_code).strip()
            unit = (row.get("unit") or "USD/MT").strip()

        # End of month date
        if obs_date.month == 12:
            period_end = date(obs_date.year, 12, 31)
        else:
            # First day of next month minus 1 day
            next_m = date(obs_date.year, obs_date.month + 1, 1)
            period_end = date.fromordinal(next_m.toordinal() - 1)

        # 1. FOB Commodity Record
        rec = MacroRecord(
            indicator_code=ind_code,
            indicator_name=ind_name,
            frequency="monthly",
            unit=unit,
            geo_scope="global",
            period_start=obs_date,
            period_end=period_end,
            value_raw=price_str,
            value=fob_val,
            vintage="final",
            observed_or_imputed="observed",
            published_at=datetime.combine(period_end, datetime.min.time(), tzinfo=UTC),
            evidence={
                "row_index": row_idx,
                "commodity_code": comm_code,
                "source_reference": source_ref,
                "source_record_id": source_record_id,
            },
        )
        records.append(rec)

        # 2. Freight Index Record (if provided and only once per unique date/row)
        if freight_str and comm_code == "RICE_WHITE_25_FOB":
            try:
                freight_val = float(freight_str.replace(" ", "").replace(",", "."))
                freight_rec = MacroRecord(
                    indicator_code="FREIGHT_SCFI_CONTAINER_INDEX",
                    indicator_name="Shanghai Containerized Freight Index (SCFI)",
                    frequency="monthly",
                    unit="index",
                    geo_scope="global",
                    period_start=obs_date,
                    period_end=period_end,
                    value_raw=freight_str,
                    value=freight_val,
                    vintage="final",
                    observed_or_imputed="observed",
                    published_at=datetime.combine(period_end, datetime.min.time(), tzinfo=UTC),
                    evidence={
                        "row_index": row_idx,
                        "metric": "scfi_freight",
                        "source_record_id": source_record_id,
                    },
                )
                records.append(freight_rec)
            except ValueError:
                pass

    return records


class WorldBenchmarksConnector:
    """Connector for international FOB benchmarks and maritime freight."""

    source_id: ClassVar[str] = WORLD_BENCHMARKS_SOURCE_ID
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, run_ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover the monthly world commodity price feed."""
        yield DiscoveredItem(
            url=WORLD_BENCHMARKS_URL,
            partition_key="latest",
            published_at=datetime.now(UTC),
        )

    def fetch(self, item: DiscoveredItem, run_ctx: RunContext) -> RawArtifact:
        """Fetch world benchmarks feed or load offline fixture."""
        if run_ctx.offline:
            from pathlib import Path

            fixture_path = (
                Path(__file__).parent.parent.parent.parent
                / "tests"
                / "fixtures"
                / "world_benchmarks"
                / "world_fob_benchmarks_2024_2026.csv"
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
        records = parse_world_benchmarks_csv(content, source_record_id=artifact.source_record_id)

        return ParseResult(
            records=records,
            issues=[],
            parser_version="1.0.0",
        )
