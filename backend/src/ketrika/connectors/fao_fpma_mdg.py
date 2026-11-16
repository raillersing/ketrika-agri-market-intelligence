"""FAO FPMA (Food Price Monitoring and Analysis) Madagascar connector (IA-DATA-07).

Collects and parses food price monitoring data published by the Food and Agriculture
Organization of the United Nations (FAO GIEWS FPMA Tool) for Madagascar.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import ClassVar

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.records import PriceRecord
from ketrika.core.policy import PolicyStop
from ketrika.core.registry import find_repo_root

logger = logging.getLogger(__name__)

# Default FAO GIEWS FPMA endpoint for Madagascar
FAO_FPMA_API_URL = "https://fpma.fao.org/giews/fpma/api/v1/prices?country=MDG"


class FaoFpmaConnector:
    """Connector for FAO FPMA Food Price Monitoring dataset in Madagascar."""

    source_id: ClassVar[str] = "fao_fpma_mdg"
    source_family: ClassVar[str] = "un_fao"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover FAO FPMA price monitoring targets for Madagascar."""
        url = ctx.metadata.get("fpma_url") or FAO_FPMA_API_URL
        yield DiscoveredItem(
            url=url,
            partition_key="fpma_prices_mdg",
            hints={"publisher": "FAO GIEWS", "format": "json", "api": "fpma_v1"},
        )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch FAO FPMA JSON payload respecting offline/policy rules."""
        # Policy verification if online
        if not ctx.offline:
            root = find_repo_root()
            sources_yaml = root / "registry" / "sources.yaml"
            if sources_yaml.exists():
                import yaml

                data = yaml.safe_load(sources_yaml.read_text(encoding="utf-8"))
                for s in data:
                    if s.get("source_id") == self.source_id and s.get("status") == "disabled":
                        raise PolicyStop(
                            f"Source '{self.source_id}' is marked disabled in sources.yaml"
                        )

        # Offline fixture fallback for reproducible validation
        if ctx.offline:
            root = find_repo_root()
            base_dir = root / "backend" if (root / "backend").exists() else root
            fixture_path = (
                base_dir / "tests" / "fixtures" / "fao_fpma_mdg" / "fpma_prices_mdg_sample.json"
            )
            if not fixture_path.exists():
                raise FileNotFoundError(f"Offline fixture not found at {fixture_path}")

            content_bytes = fixture_path.read_bytes()
            content_sha256 = hashlib.sha256(content_bytes).hexdigest()
            now = datetime.now(UTC)
            object_key = f"{self.source_id}/{now.year}/{now.month:02d}/{content_sha256}.json"
            is_new = True

            if ctx.bronze_store:
                art = ctx.bronze_store.put(
                    source_id=self.source_id,
                    content=content_bytes,
                    mime_type="application/json",
                    url=item.url,
                )
                object_key = art.object_key
                is_new = art.is_new

            return RawArtifact(
                source_record_id="",
                object_key=object_key,
                content_sha256=content_sha256,
                mime_type="application/json",
                url=item.url,
                is_new=is_new,
                published_at=item.published_at,
            )

        return ctx.fetch_and_store(item, mime_type="application/json")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse FAO FPMA JSON artifact into normalized PriceRecord objects."""
        if ctx.bronze_store is None:
            raise ValueError("Bronze store is required in RunContext")

        raw_bytes = ctx.bronze_store.get(artifact.object_key)
        text_content = raw_bytes.decode("utf-8", errors="replace").strip()

        try:
            data = json.loads(text_content)
        except Exception as e:
            return ParseResult(
                records=[],
                issues=[{"kind": "json_decode_error", "error": str(e)}],
                parser_version=self.parser_version,
            )

        items = data.get("data", []) if isinstance(data, dict) else data
        records: list[PriceRecord] = []
        issues: list[dict] = []

        for row_idx, item in enumerate(items):
            try:
                commodity = str(item.get("commodity") or item.get("commodity_name") or "").strip()
                if not commodity:
                    continue

                market = str(item.get("market") or item.get("market_name") or "").strip()
                # Strict no_arbitrary_default rule: missing market goes to review queue
                if not market:
                    issues.append(
                        {
                            "kind": "unresolved_market_needs_review",
                            "row_index": row_idx,
                            "commodity": commodity,
                            "details": (
                                "Market name missing in FAO FPMA record, sent to human "
                                "review queue without defaulting to region or capital"
                            ),
                        }
                    )
                    continue

                date_str = str(item.get("date") or item.get("period_start") or "").strip()
                if not date_str:
                    continue
                obs_date = date.fromisoformat(date_str[:10])

                price_raw_val = item.get("price")
                if price_raw_val is not None:
                    try:
                        price_val = float(price_raw_val)
                        price_raw = str(price_raw_val)
                    except (ValueError, TypeError):
                        price_val = None
                        price_raw = str(price_raw_val)
                else:
                    price_val = None
                    price_raw = ""

                price_type = (
                    str(item.get("price_type") or item.get("pricetype") or "Retail").strip().lower()
                )
                actor_level = "wholesale" if "wholesale" in price_type else "retail"

                unit_raw = str(item.get("unit") or "KG").strip()
                currency_raw = str(
                    item.get("currency") or item.get("currency_code") or "MGA"
                ).strip()

                flag = str(item.get("flag") or "").strip().lower()
                is_imputed = flag in ("forecast", "imputed", "estimated")
                observed_or_imputed = "imputed" if is_imputed else "observed"

                evidence = {
                    "source_family": self.source_family,
                    "provider": "FAO GIEWS FPMA Tool",
                    "market": market,
                    "market_id": item.get("market_id"),
                    "commodity": commodity,
                    "commodity_id": item.get("commodity_id"),
                    "data_source": item.get("data_source"),
                    "period": item.get("period", "monthly"),
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
            "Parsed %d price records from FAO FPMA artifact (issues: %d)",
            len(records),
            len(issues),
        )
        return ParseResult(
            records=records,
            issues=issues,
            parser_version=self.parser_version,
        )
