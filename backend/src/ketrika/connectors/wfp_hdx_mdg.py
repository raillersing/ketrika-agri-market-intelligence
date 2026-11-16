"""WFP Food Prices Madagascar HDX connector (SPECS §5.2, MVP_EXECUTION_PLAN T3.1).

Collects and parses monthly food price monitoring data published by the World Food Programme on HDX.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import ClassVar

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.records import PriceRecord
from ketrika.core.policy import PolicyStop
from ketrika.core.registry import find_repo_root

logger = logging.getLogger(__name__)

# Default HDX direct download URL for WFP Madagascar food prices (legacy CSV)
WFP_HDX_CSV_URL = (
    "https://data.humdata.org/dataset/02b28c05-b076-4d0c-a9f4-279262e3d368/resource/"
    "b8c3fdfb-59d8-4f81-a64b-14dcf7d6be2f/download/wfp_food_prices_mdg.csv"
)

# Modern OCHA HDX HAPI v2 endpoint for Madagascar food price monitoring
HDX_HAPI_API_URL = (
    "https://hapi.humdata.org/api/v2/food-security-nutrition-poverty/food-prices-market-monitor"
)


class WfpHdxMdgConnector:
    """Connector for WFP HDX Food Prices dataset in Madagascar under strict policy rules."""

    source_id: ClassVar[str] = "wfp_hdx_mdg"
    parser_version: ClassVar[str] = "1.3.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover WFP HDX price dataset download target (CSV or HAPI v2)."""
        app_id = os.getenv("HDX_HAPI_APP_IDENTIFIER") or ctx.metadata.get("app_identifier")
        hapi_url = ctx.metadata.get("hapi_url")
        use_hapi = bool(
            hapi_url
            or ctx.metadata.get("api_type") == "hapi"
            or app_id
            or ctx.metadata.get("use_hapi")
        )
        if use_hapi:
            base_url = hapi_url or HDX_HAPI_API_URL
            limit = int(ctx.metadata.get("limit", 1000))
            offset = int(ctx.metadata.get("offset", 0))
            max_pages = int(ctx.metadata.get("max_pages", 1))

            for page_idx in range(max_pages):
                current_offset = offset + (page_idx * limit)
                query_url = (
                    f"{base_url}?location_code=MDG&output_format=json&limit={limit}&offset={current_offset}"
                    + (f"&app_identifier={app_id}" if app_id else "")
                )
                yield DiscoveredItem(
                    url=query_url,
                    partition_key=f"hdx_hapi_v2_mdg_p{page_idx}"
                    if max_pages > 1
                    else "hdx_hapi_v2_mdg",
                    hints={
                        "publisher": "WFP",
                        "format": "json",
                        "api": "hapi_v2",
                        "limit": str(limit),
                        "offset": str(current_offset),
                        "page": str(page_idx),
                    },
                )
            return

        url = ctx.metadata.get("csv_url") or WFP_HDX_CSV_URL
        yield DiscoveredItem(
            url=url,
            partition_key="full_series",
            hints={"publisher": "WFP", "format": "csv"},
        )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch WFP prices CSV or HAPI JSON respecting policy engine and disabled status."""
        is_json = item.hints.get("format") == "json" or "hapi.humdata.org" in item.url
        target_mime = "application/json" if is_json else "text/csv"

        # 1. Enforce strict policy check: refuse network access when source is disabled or legacy CSV
        if not ctx.offline:
            if "data.humdata.org" in item.url:
                raise PolicyStop(
                    f"Source '{self.source_id}' is marked disabled in sources.yaml (HDX 403)"
                )

            root = find_repo_root()
            sources_yaml = root / "registry" / "sources.yaml"
            if sources_yaml.exists():
                import yaml

                data = yaml.safe_load(sources_yaml.read_text(encoding="utf-8"))
                for s in data:
                    if s.get("source_id") == self.source_id and s.get("status") == "disabled":
                        raise PolicyStop(
                            f"Source '{self.source_id}' is marked disabled in sources.yaml (HDX 403)"
                        )

        # 2. Offline fixture fallback for reproducible validation
        if ctx.offline:
            root = find_repo_root()
            base_dir = root / "backend" if (root / "backend").exists() else root
            fixtures_dir = base_dir / "tests" / "fixtures" / "wfp_hdx_mdg"

            if is_json and (fixtures_dir / "wfp_hapi_mdg_sample.json").exists():
                fixture_path = fixtures_dir / "wfp_hapi_mdg_sample.json"
                mime = "application/json"
                ext = "json"
            else:
                fixture_path = fixtures_dir / "wfp_food_prices_mdg_sample.csv"
                mime = "text/csv"
                ext = "csv"

            if not fixture_path.exists():
                raise FileNotFoundError(f"Offline fixture not found at {fixture_path}")
            content_bytes = fixture_path.read_bytes()
            content_sha256 = hashlib.sha256(content_bytes).hexdigest()
            now = datetime.now(UTC)
            object_key = f"{self.source_id}/{now.year}/{now.month:02d}/{content_sha256}.{ext}"
            is_new = True

            if ctx.bronze_store:
                art = ctx.bronze_store.put(
                    source_id=self.source_id,
                    content=content_bytes,
                    mime_type=mime,
                    url=item.url,
                )
                object_key = art.object_key
                is_new = art.is_new

            return RawArtifact(
                source_record_id="",
                object_key=object_key,
                content_sha256=content_sha256,
                mime_type=mime,
                url=item.url,
                is_new=is_new,
                published_at=item.published_at,
            )

        return ctx.fetch_and_store(item, mime_type=target_mime)

    def _parse_hapi_json(self, text_content: str, issues: list[dict]) -> list[PriceRecord]:
        """Parse OCHA HDX HAPI v2 JSON payload into PriceRecord objects."""
        try:
            data = json.loads(text_content)
        except Exception as e:
            issues.append({"kind": "json_decode_error", "error": str(e)})
            return []

        rows = data.get("data", []) if isinstance(data, dict) else data
        records: list[PriceRecord] = []

        for row_idx, item in enumerate(rows):
            try:
                commodity = str(item.get("commodity_name") or item.get("commodity") or "").strip()
                if not commodity:
                    continue

                market = str(item.get("market_name") or item.get("market") or "").strip()
                if not market:
                    issues.append(
                        {
                            "kind": "unresolved_market_needs_review",
                            "row_index": row_idx,
                            "commodity": commodity,
                            "details": "Market name missing, row sent to human review queue without defaulting to region",
                        }
                    )
                    continue

                date_str = item.get("reference_period_start") or item.get("date")
                if not date_str:
                    continue
                obs_date = date.fromisoformat(str(date_str)[:10])

                end_date_str = item.get("reference_period_end")
                end_date = date.fromisoformat(str(end_date_str)[:10]) if end_date_str else obs_date

                unit_raw = str(item.get("unit") or "KG").strip()
                pricetype = (
                    str(item.get("price_type") or item.get("pricetype") or "Retail").strip().lower()
                )
                actor_level = "wholesale" if "wholesale" in pricetype else "retail"
                currency_raw = str(
                    item.get("currency_code") or item.get("currency") or "MGA"
                ).strip()

                priceflag = (
                    str(item.get("price_flag") or item.get("priceflag") or "actual").strip().lower()
                )
                is_imputed = priceflag in ("forecast", "imputed", "estimated")
                observed_or_imputed = "imputed" if is_imputed else "observed"

                price_val_raw = item.get("price")
                if price_val_raw is not None:
                    try:
                        price_val = float(price_val_raw)
                        price_raw = str(price_val_raw)
                    except (ValueError, TypeError):
                        price_val = None
                        price_raw = str(price_val_raw)
                else:
                    price_val = None
                    price_raw = ""

                evidence = {
                    "source_family": "un_wfp",
                    "underlying_collector": "WFP VAM",
                    "admin1_code": item.get("admin1_code"),
                    "admin1_name": item.get("admin1_name"),
                    "admin2_code": item.get("admin2_code"),
                    "admin2_name": item.get("admin2_name"),
                    "market_code": item.get("market_code"),
                    "market": market,
                    "commodity_code": item.get("commodity_code"),
                    "commodity_category": item.get("commodity_category"),
                    "latitude": item.get("lat") or item.get("latitude"),
                    "longitude": item.get("lon") or item.get("longitude"),
                    "price_flag": priceflag,
                    "resource_hdx_id": item.get("resource_hdx_id"),
                    "row_index": row_idx,
                }

                records.append(
                    PriceRecord(
                        product_raw=commodity,
                        location_raw=market,
                        actor_level=actor_level,
                        period_start=obs_date,
                        period_end=end_date,
                        price_raw=price_raw,
                        price_value=price_val,
                        unit_raw=unit_raw,
                        currency_raw=currency_raw,
                        observed_or_imputed=observed_or_imputed,
                        value_kind="avg" if priceflag == "aggregate" else "point",
                        extraction_method="deterministic",
                        evidence=evidence,
                        confidence=1.0 if not is_imputed else 0.8,
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

        return records

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse WFP CSV or HAPI JSON bytes from Bronze store into PriceRecord objects."""
        if ctx.bronze_store is None:
            raise ValueError("Bronze store is required in RunContext")

        raw_bytes = ctx.bronze_store.get(artifact.object_key)
        text_content = raw_bytes.decode("utf-8", errors="replace").strip()

        records: list[PriceRecord] = []
        issues: list[dict] = []

        if text_content.startswith("{") or text_content.startswith("["):
            records = self._parse_hapi_json(text_content, issues)
            logger.info(
                "Parsed %d price records from WFP HDX HAPI JSON artifact (issues: %d)",
                len(records),
                len(issues),
            )
            return ParseResult(
                records=records,
                issues=issues,
                parser_version=self.parser_version,
            )

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
                date_str = row_dict.get("date", "").strip()
                if not date_str:
                    continue
                obs_date = date.fromisoformat(date_str)

                commodity = row_dict.get("commodity", "").strip()
                if not commodity:
                    continue

                market = row_dict.get("market", "").strip()
                admin1 = row_dict.get("admin1", "").strip()
                admin2 = row_dict.get("admin2", "").strip()

                # Market resolution rule (R1.7):
                # Never invent a P-code and never arbitrarily assign an unresolved market to a region by default
                if not market:
                    issues.append(
                        {
                            "kind": "unresolved_market_needs_review",
                            "row_index": row_idx,
                            "commodity": commodity,
                            "details": "Market name missing, row sent to human review queue without defaulting to region",
                        }
                    )
                    continue

                unit_raw = row_dict.get("unit", "KG").strip()
                pricetype = row_dict.get("pricetype", "Retail").strip().lower()
                actor_level = "wholesale" if "wholesale" in pricetype else "retail"
                currency_raw = row_dict.get("currency", "MGA").strip()

                priceflag = row_dict.get("priceflag", "actual").strip().lower()
                is_imputed = priceflag in ("forecast", "imputed", "estimated")
                observed_or_imputed = "imputed" if is_imputed else "observed"

                price_raw = row_dict.get("price", "").strip()
                try:
                    price_val = float(price_raw.replace(",", ".").replace(" ", ""))
                except (ValueError, TypeError):
                    price_val = None

                evidence = {
                    "source_family": "un_wfp",
                    "underlying_collector": "WFP VAM",
                    "admin1": admin1,
                    "admin2": admin2,
                    "market": market,
                    "latitude": row_dict.get("latitude"),
                    "longitude": row_dict.get("longitude"),
                    "priceflag": priceflag,
                    "row_index": row_idx,
                }

                records.append(
                    PriceRecord(
                        product_raw=commodity,
                        location_raw=market,
                        actor_level=actor_level,
                        period_start=obs_date,
                        period_end=obs_date,
                        price_raw=price_raw,
                        price_value=price_val,
                        unit_raw=unit_raw,
                        currency_raw=currency_raw,
                        observed_or_imputed=observed_or_imputed,
                        value_kind="point",
                        extraction_method="deterministic",
                        evidence=evidence,
                        confidence=1.0 if not is_imputed else 0.8,
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
