"""World Bank Real-Time Food Prices Madagascar (RTFP) connector (SPECS §5.2, R1.8).

Ingests World Bank RTFP dataset for Madagascar with strict mapping of value_kind to observed_or_imputed,
traceability of source dependency (WFP/FAO), and explicit denominator calculations.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import ClassVar, Literal

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.discovery import CatalogDiscoveryEngine
from ketrika.connectors.records import PriceRecord
from ketrika.core.policy import validate_candidate_url
from ketrika.core.registry import find_repo_root

logger = logging.getLogger(__name__)

WB_RTFP_CSV_URL = (
    "https://microdata.worldbank.org/index.php/catalog/food-prices/download/mdg_rtfp.csv"
)
ALLOWED_WB_DOMAINS = ["microdata.worldbank.org", "worldbank.org"]


class WbRtfpMdgConnector:
    """Connector for World Bank Real-Time Food Prices (RTFP) Madagascar dataset."""

    source_id: ClassVar[str] = "wb_rtfp_mdg"
    parser_version: ClassVar[str] = "1.1.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover WB RTFP price dataset download targets via metadata, dynamic catalog or direct URL."""
        # 1. Explicit file URLs in metadata
        file_urls = ctx.metadata.get("file_urls")
        if file_urls and isinstance(file_urls, list):
            for u in file_urls:
                url_str = str(u)
                slug = Path(url_str).stem
                yield DiscoveredItem(
                    url=url_str,
                    partition_key=slug,
                    hints={"publisher": "World Bank", "format": "csv"},
                )
            return

        file_url = ctx.metadata.get("file_url") or ctx.metadata.get("csv_url")
        if file_url:
            url_str = str(file_url)
            slug = Path(url_str).stem
            yield DiscoveredItem(
                url=url_str,
                partition_key=slug,
                hints={"publisher": "World Bank", "format": "csv"},
            )
            return

        # 2. Dynamic catalog discovery if catalog_url or live http_client provided
        catalog_url = ctx.metadata.get("catalog_url")
        if catalog_url or (
            not ctx.offline and ctx.http_client is not None and ctx.metadata.get("use_catalog")
        ):
            target_cat_url = (
                catalog_url or "https://microdata.worldbank.org/index.php/catalog/food-prices"
            )
            allow_loopback = ctx.metadata.get("allow_loopback", False)
            engine = CatalogDiscoveryEngine(
                http_client=ctx.http_client,
                source_id=self.source_id,
                allowed_domains=list(ALLOWED_WB_DOMAINS),
                allow_loopback=allow_loopback,
                max_pages=10,
            )
            discovery_res = engine.discover_html_editions(
                start_url=target_cat_url,
                link_pattern=r".*(?:mdg.*\.csv|food-prices.*\.csv)",
            )
            for edition in discovery_res.editions:
                slug = Path(edition.url).stem
                hints = {"publisher": "World Bank", "format": "csv"}
                if edition.title:
                    hints["title"] = edition.title
                yield DiscoveredItem(
                    url=edition.url,
                    partition_key=slug,
                    hints=hints,
                    published_at=edition.published_at,
                )
            if discovery_res.editions:
                return

        # 3. Default direct URL
        yield DiscoveredItem(
            url=WB_RTFP_CSV_URL,
            partition_key="mdg_rtfp",
            hints={"publisher": "World Bank", "format": "csv"},
        )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch WB RTFP CSV and store in Bronze with offline fixture support."""
        if ctx.offline:
            root = find_repo_root()
            base_dir = root / "backend" if (root / "backend").exists() else root
            fixture_path = (
                base_dir
                / "tests"
                / "fixtures"
                / "wb_rtfp_mdg"
                / "wb_rtfp_mdg_sample.csv"
            )
            if not fixture_path.exists():
                raise FileNotFoundError(f"Offline fixture not found at {fixture_path}")
            content_bytes = fixture_path.read_bytes()
            content_sha256 = hashlib.sha256(content_bytes).hexdigest()
            now = datetime.now(UTC)
            object_key = f"{self.source_id}/{now.year}/{now.month:02d}/{content_sha256}.csv"
            is_new = True

            if ctx.bronze_store:
                art = ctx.bronze_store.put(
                    source_id=self.source_id,
                    content=content_bytes,
                    mime_type="text/csv",
                    url=item.url,
                )
                object_key = art.object_key
                is_new = art.is_new

            return RawArtifact(
                source_record_id="",
                object_key=object_key,
                content_sha256=content_sha256,
                mime_type="text/csv",
                url=item.url,
                is_new=is_new,
                published_at=item.published_at,
            )

        validate_candidate_url(item.url, allowed_domains=ALLOWED_WB_DOMAINS)
        return ctx.fetch_and_store(item, mime_type="text/csv")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse WB RTFP CSV bytes from Bronze store into PriceRecord objects under C3 rules."""
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
                date_str = row_dict.get("date", "").strip()
                if not date_str:
                    continue
                obs_date = date.fromisoformat(date_str)

                commodity = row_dict.get("commodity", "").strip()
                if not commodity:
                    continue

                market = (
                    row_dict.get("market_name", "").strip()
                    or row_dict.get("market", "").strip()
                )
                adm1 = (
                    row_dict.get("adm1_name", "").strip()
                    or row_dict.get("admin1", "").strip()
                )

                # Geographic resolution (R1.8, C3):
                # If neither market nor adm1 is available, issue unresolved_location_needs_review
                # Never invent a P-code and never assign arbitrary default location
                if not market and not adm1:
                    issues.append(
                        {
                            "kind": "unresolved_location_needs_review",
                            "row_index": row_idx,
                            "commodity": commodity,
                            "details": (
                                "Both market_name and adm1_name are missing; "
                                "sent to review queue without default fallback"
                            ),
                        }
                    )
                    continue

                location_raw = market if market else adm1

                unit_raw = row_dict.get("unit", "kg").strip()
                currency_raw = row_dict.get("currency", "MGA").strip()

                raw_kind = row_dict.get("value_kind", "").strip().lower()
                obs_price_str = row_dict.get("price_observed", "").strip()
                imp_price_str = row_dict.get("price_imputed", "").strip()

                # Rule for value_kind and observed vs imputed (SPECS §5.2, R1.8, C3):
                # Unknown value_kind must NEVER be promoted to observed: send to review!
                if raw_kind and raw_kind not in ("observed", "imputed"):
                    issues.append(
                        {
                            "kind": "unknown_value_kind_needs_review",
                            "row_index": row_idx,
                            "raw_value_kind": raw_kind,
                            "commodity": commodity,
                            "details": (
                                f"Unknown value_kind '{raw_kind}' cannot be safely mapped; "
                                "never promoted to observed"
                            ),
                        }
                    )
                    continue

                is_imputed = (
                    raw_kind == "imputed"
                    or not obs_price_str
                    or obs_price_str.lower() in ("null", "none", "nd", "na", "nan")
                )

                if is_imputed:
                    observed_or_imputed: Literal["observed", "imputed"] = "imputed"
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
                    "source_family": "world_bank",
                    "source_dependency": "wfp_fao",  # Schema C3: WB RTFP relies on WFP/FAO primary data
                    "is_forecast_or_estimated": is_imputed,  # For prediction ground-truth exclusion
                    "row_index": row_idx,
                }

                records.append(
                    PriceRecord(
                        product_raw=commodity,
                        location_raw=location_raw,
                        actor_level="retail",
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

        total_processed = len(records) + len(issues)
        imputed_share = n_imputed / len(records) if records else 0.0
        logger.info(
            "Parsed %d price records from WB RTFP (total: %d, observed: %d, imputed: %d, "
            "imputed_share: %.2f%%, issues: %d)",
            len(records),
            total_processed,
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
