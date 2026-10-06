"""Dummy CSV connector for acceptance testing (MVP_EXECUTION_PLAN T2.3)."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import date
from typing import ClassVar

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.records import PriceRecord


class DummyCsvConnector:
    """A minimal CSV price connector used to verify pipeline execution and supersession."""

    source_id: ClassVar[str] = "dummy_csv"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover dummy CSV target."""
        url = ctx.metadata.get("csv_url", "http://localhost:8000/dummy.csv")
        yield DiscoveredItem(url=url, partition_key="test_2025")

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch CSV and store in Bronze."""
        return ctx.fetch_and_store(item, mime_type="text/csv")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse CSV bytes from Bronze store into PriceRecord objects."""
        if ctx.bronze_store is None:
            raise ValueError("Bronze store is required in RunContext")

        raw_bytes = ctx.bronze_store.get(artifact.object_key)
        text_content = raw_bytes.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text_content))

        records: list[PriceRecord] = []
        for row in reader:
            p_start = date.fromisoformat(row["period_start"])
            p_end = date.fromisoformat(row["period_end"])
            p_raw = row["price"]
            p_val = float(p_raw)

            records.append(
                PriceRecord(
                    product_raw=row["product"],
                    location_raw=row.get("market"),
                    actor_level=row.get("actor_level", "retail"),
                    period_start=p_start,
                    period_end=p_end,
                    price_raw=p_raw,
                    price_value=p_val,
                    unit_raw=row["unit"],
                    currency_raw=row.get("currency", "MGA"),
                    extraction_method="deterministic",
                    evidence={"row": row},
                    confidence=1.0,
                )
            )

        return ParseResult(records=records, issues=[], parser_version=self.parser_version)
