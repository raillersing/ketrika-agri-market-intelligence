"""World Bank Real-Time Food Prices Madagascar (RTFP) connector (SPECS §5.2, MVP_EXECUTION_PLAN T3.2).

Ingests World Bank RTFP dataset for Madagascar with strict mapping of value_kind to observed_or_imputed.
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Iterable
from datetime import date
from typing import ClassVar, Literal

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.records import PriceRecord

logger = logging.getLogger(__name__)

WB_RTFP_CSV_URL = (
    "https://microdata.worldbank.org/index.php/catalog/food-prices/download/mdg_rtfp.csv"
)


class WbRtfpMdgConnector:
    """Connector for World Bank Real-Time Food Prices (RTFP) Madagascar dataset."""

    source_id: ClassVar[str] = "wb_rtfp_mdg"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover WB RTFP price dataset download target."""
        url = ctx.metadata.get("csv_url") or WB_RTFP_CSV_URL
        yield DiscoveredItem(
            url=url,
            partition_key="full_series",
            hints={"publisher": "World Bank", "format": "csv"},
        )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch WB RTFP CSV and store in Bronze."""
        return ctx.fetch_and_store(item, mime_type="text/csv")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse WB RTFP CSV bytes from Bronze store into PriceRecord objects."""
        if ctx.bronze_store is None:
            raise ValueError("Bronze store is required in RunContext")

        raw_bytes = ctx.bronze_store.get(artifact.object_key)
        text_content = raw_bytes.decode("utf-8", errors="replace")

        records: list[PriceRecord] = []
        issues: list[dict] = []

        reader = csv.reader(io.StringIO(text_content))
        header: list[str] | None = None

        n_observed = 0
        n_imputed = 0

        for row_idx, row in enumerate(reader):
            if not row or not any(cell.strip() for cell in row):
                continue

            # Skip comment lines starting with #
            if row[0].strip().startswith("#"):
                continue

            # First non-empty, non-comment row is header
            if header is None:
                header = [h.strip().lower() for h in row]
                continue

            row_dict = dict(zip(header, [c.strip() for c in row], strict=False))

            try:
                date_str = row_dict.get("date", "")
                if not date_str:
                    continue
                obs_date = date.fromisoformat(date_str)

                commodity = row_dict.get("commodity", "")
                if not commodity:
                    continue

                market = row_dict.get("market_name", "") or row_dict.get("market", "")
                adm1 = row_dict.get("adm1_name", "") or row_dict.get("admin1", "")
                unit_raw = row_dict.get("unit", "kg")
                currency_raw = row_dict.get("currency", "MGA")

                raw_kind = row_dict.get("value_kind", "").strip().lower()
                obs_price_str = row_dict.get("price_observed", "").strip()
                imp_price_str = row_dict.get("price_imputed", "").strip()

                # Rule for observed vs imputed (SPECS §5.2, MVP_EXECUTION_PLAN T3.2):
                # If value_kind is explicitly 'imputed' or price_observed is missing/null/ND,
                # the price is imputed. Otherwise, it is observed.
                # Under NO circumstances may an imputed value be marked 'observed'.
                is_imputed = (
                    raw_kind == "imputed"
                    or not obs_price_str
                    or obs_price_str.lower() in ("null", "none", "nd", "na", "nan")
                )

                if is_imputed:
                    observed_or_imputed: Literal["observed", "imputed", "nowcasted"] = "imputed"
                    price_raw = imp_price_str
                    n_imputed += 1
                else:
                    observed_or_imputed = "observed"
                    price_raw = obs_price_str
                    n_observed += 1

                try:
                    price_val = float(price_raw.replace(",", ".").replace(" ", ""))
                except (ValueError, TypeError):
                    price_val = None

                evidence = {
                    "adm1_name": adm1,
                    "market_name": market,
                    "country": row_dict.get("country"),
                    "country_code": row_dict.get("country_code"),
                    "price_observed_raw": row_dict.get("price_observed"),
                    "price_imputed_raw": row_dict.get("price_imputed"),
                    "value_kind_raw": row_dict.get("value_kind"),
                    "row_index": row_idx,
                }

                records.append(
                    PriceRecord(
                        product_raw=commodity,
                        location_raw=market or adm1 or "Madagascar",
                        actor_level="retail",
                        period_start=obs_date,
                        period_end=obs_date,
                        price_raw=price_raw,
                        price_value=price_val,
                        unit_raw=unit_raw,
                        currency_raw=currency_raw,
                        observed_or_imputed=observed_or_imputed,
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

        imputed_share = (
            n_imputed / (n_observed + n_imputed) if (n_observed + n_imputed) > 0 else 0.0
        )
        logger.info(
            "Parsed %d price records from WB RTFP (observed: %d, imputed: %d, imputed_share: %.2f%%, issues: %d)",
            len(records),
            n_observed,
            n_imputed,
            imputed_share * 100,
            len(issues),
        )

        return ParseResult(
            records=records,
            issues=issues,
            parser_version=self.parser_version,
        )
