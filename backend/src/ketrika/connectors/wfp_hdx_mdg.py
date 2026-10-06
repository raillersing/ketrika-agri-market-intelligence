"""WFP Food Prices Madagascar HDX connector (SPECS §5.2, MVP_EXECUTION_PLAN T3.1).

Collects and parses monthly food price monitoring data published by the World Food Programme on HDX.
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Iterable
from datetime import date
from typing import ClassVar

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.records import PriceRecord

logger = logging.getLogger(__name__)

# Default HDX direct download URL for WFP Madagascar food prices
WFP_HDX_CSV_URL = (
    "https://data.humdata.org/dataset/02b28c05-b076-4d0c-a9f4-279262e3d368/resource/"
    "b8c3fdfb-59d8-4f81-a64b-14dcf7d6be2f/download/wfp_food_prices_mdg.csv"
)


class WfpHdxMdgConnector:
    """Connector for WFP HDX Food Prices dataset in Madagascar."""

    source_id: ClassVar[str] = "wfp_hdx_mdg"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover WFP HDX price dataset download target."""
        url = ctx.metadata.get("csv_url") or WFP_HDX_CSV_URL
        yield DiscoveredItem(
            url=url,
            partition_key="full_series",
            hints={"publisher": "WFP", "format": "csv"},
        )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch WFP prices CSV and store in Bronze."""
        return ctx.fetch_and_store(item, mime_type="text/csv")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse WFP CSV bytes from Bronze store into PriceRecord objects."""
        if ctx.bronze_store is None:
            raise ValueError("Bronze store is required in RunContext")

        raw_bytes = ctx.bronze_store.get(artifact.object_key)
        text_content = raw_bytes.decode("utf-8", errors="replace")

        records: list[PriceRecord] = []
        issues: list[dict] = []

        reader = csv.reader(io.StringIO(text_content))
        header: list[str] | None = None

        for row_idx, row in enumerate(reader):
            if not row or not any(cell.strip() for cell in row):
                continue

            # Skip comments and HXL tag row (starts with #)
            if row[0].strip().startswith("#"):
                continue

            # First non-empty, non-comment row is header
            if header is None:
                header = [h.strip().lower() for h in row]
                continue

            # Map row by header column
            row_dict = dict(zip(header, [c.strip() for c in row], strict=False))

            try:
                date_str = row_dict.get("date", "")
                if not date_str:
                    continue
                obs_date = date.fromisoformat(date_str)

                commodity = row_dict.get("commodity", "")
                if not commodity:
                    continue

                market = row_dict.get("market", "")
                admin1 = row_dict.get("admin1", "")
                admin2 = row_dict.get("admin2", "")
                unit_raw = row_dict.get("unit", "KG")
                pricetype = row_dict.get("pricetype", "Retail").strip().lower()
                actor_level = "wholesale" if "wholesale" in pricetype else "retail"
                currency_raw = row_dict.get("currency", "MGA")

                price_raw = row_dict.get("price", "")
                try:
                    price_val = float(price_raw.replace(",", ".").replace(" ", ""))
                except (ValueError, TypeError):
                    price_val = None

                evidence = {
                    "admin1": admin1,
                    "admin2": admin2,
                    "market": market,
                    "latitude": row_dict.get("latitude"),
                    "longitude": row_dict.get("longitude"),
                    "priceflag": row_dict.get("priceflag"),
                    "row_index": row_idx,
                }

                records.append(
                    PriceRecord(
                        product_raw=commodity,
                        location_raw=market or admin2 or admin1,
                        actor_level=actor_level,
                        period_start=obs_date,
                        period_end=obs_date,
                        price_raw=price_raw,
                        price_value=price_val,
                        unit_raw=unit_raw,
                        currency_raw=currency_raw,
                        extraction_method="deterministic",
                        evidence=evidence,
                        confidence=1.0,
                    )
                )
            except Exception as e:
                issues.append(
                    {
                        "kind": "row_parse_error",
                        "row_index": row_idx,
                        "error": str(e),
                    }
                )

        logger.info(
            "Parsed %d price records from WFP HDX artifact (issues: %d)",
            len(records),
            len(issues),
        )

        return ParseResult(
            records=records,
            issues=issues,
            parser_version=self.parser_version,
        )
