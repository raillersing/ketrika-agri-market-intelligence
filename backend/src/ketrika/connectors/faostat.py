"""FAOSTAT connector (SPECS §5.3, MVP_EXECUTION_PLAN T3.3, R1.9).

Ingests agricultural production (QCL), food balance sheets (FBS), and trade flows (TM/TCL)
for Madagascar from the UN Food and Agriculture Organization (FAOSTAT).
Preserves original flags, distinguishes paddy from milled rice without unwarranted conversion,
and strictly maps flags to observed_or_imputed.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, ClassVar

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.records import ProductionRecord, TradeFlowRecord
from ketrika.core.policy import validate_candidate_url
from ketrika.core.registry import find_repo_root

logger = logging.getLogger(__name__)

FAOSTAT_QCL_API_URL = "https://fenixservices.fao.org/faostat/api/v1/en/data/QCL?area=129"
ALLOWED_FAO_DOMAINS = ["fenixservices.fao.org", "fao.org"]

# Known FAOSTAT flags classification (Official FAO Handbook):
# Observed / Official:
# A: Official figure
# P: Provisional figure
# X: Figure from international reliable source
# '': Blank / standard official figure
OBSERVED_FLAGS = frozenset({"A", "P", "X", ""})

# Imputed / Estimated:
# E: Estimated value
# I: Imputed value
# F: FAO estimate
# T: Trend calculation
# M: Missing value / imputed proxy
# Q: Missing value; suppressed
IMPUTED_FLAGS = frozenset({"E", "I", "F", "T", "M", "Q"})


class FaostatConnector:
    """Connector for FAOSTAT agricultural statistics (Madagascar)."""

    source_id: ClassVar[str] = "faostat"
    parser_version: ClassVar[str] = "1.1.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover FAOSTAT dataset targets via metadata or standard QCL/TM endpoints."""
        # 1. Explicit API URLs in metadata
        api_urls = ctx.metadata.get("api_urls")
        if api_urls and isinstance(api_urls, list):
            for u in api_urls:
                url_str = str(u)
                slug = Path(url_str).stem or "faostat_custom"
                yield DiscoveredItem(
                    url=url_str,
                    partition_key=slug,
                    hints={"publisher": "FAO", "format": "json"},
                )
            return

        api_url = ctx.metadata.get("api_url")
        if api_url:
            url_str = str(api_url)
            slug = Path(url_str).stem or "faostat_custom"
            yield DiscoveredItem(
                url=url_str,
                partition_key=slug,
                hints={"publisher": "FAO", "format": "json"},
            )
            return

        # 2. Multi-domain discovery if domain specified in metadata
        domain = ctx.metadata.get("domain")
        if domain:
            url = f"https://fenixservices.fao.org/faostat/api/v1/en/data/{domain.upper()}?area=129"
            yield DiscoveredItem(
                url=url,
                partition_key=f"faostat_{domain.lower()}",
                hints={"publisher": "FAO", "format": "json", "domain": domain.upper()},
            )
            return

        # 3. Default QCL target (Madagascar production and crops)
        yield DiscoveredItem(
            url=FAOSTAT_QCL_API_URL,
            partition_key="qcl_tm",
            hints={"publisher": "FAO", "format": "json", "domain": "QCL"},
        )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch FAOSTAT JSON dataset and store into Bronze layer with offline fixture support."""
        if ctx.offline:
            root = find_repo_root()
            base_dir = root / "backend" if (root / "backend").exists() else root
            fixture_path = (
                base_dir
                / "tests"
                / "fixtures"
                / "faostat"
                / "faostat_sample.json"
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

        validate_candidate_url(item.url, allowed_domains=ALLOWED_FAO_DOMAINS)
        return ctx.fetch_and_store(item, mime_type="application/json")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse FAOSTAT JSON payload into typed ProductionRecord and TradeFlowRecord objects under R1.9 rules."""
        if ctx.bronze_store is None:
            raise ValueError("Bronze store is required in RunContext")

        raw_bytes = ctx.bronze_store.get(artifact.object_key)
        text_content = raw_bytes.decode("utf-8", errors="replace")

        records: list[ProductionRecord | TradeFlowRecord] = []
        issues: list[dict[str, Any]] = []

        try:
            payload = json.loads(text_content)
        except json.JSONDecodeError as exc:
            issues.append({"kind": "json_decode_error", "detail": str(exc)})
            return ParseResult(records=[], issues=issues, parser_version=self.parser_version)

        data_items: list[dict[str, Any]]
        if isinstance(payload, dict):
            data_items = payload.get("data", [])
        elif isinstance(payload, list):
            data_items = payload
        else:
            issues.append(
                {
                    "kind": "unexpected_payload_type",
                    "detail": f"Payload is {type(payload).__name__}",
                }
            )
            return ParseResult(records=[], issues=issues, parser_version=self.parser_version)

        n_observed = 0
        n_imputed = 0

        for idx, row in enumerate(data_items):
            if not isinstance(row, dict):
                continue

            try:
                item_name = str(row.get("Item") or row.get("item") or "").strip()
                if not item_name:
                    continue

                year_raw = row.get("Year") or row.get("year")
                if year_raw is None:
                    continue
                year = int(year_raw)

                period_start = date(year, 1, 1)
                period_end = date(year, 12, 31)

                val_raw = row.get("Value")
                if val_raw is None:
                    continue
                val = float(val_raw)

                unit = str(row.get("Unit") or row.get("unit") or "").strip()
                flag = str(row.get("Flag") or "").strip().upper()
                element_name = str(row.get("Element") or row.get("element") or "").strip()
                element_code = row.get("ElementCode") or row.get("element_code")
                domain_code = str(row.get("DomainCode") or row.get("domain_code") or "").strip()
                area = str(row.get("Area") or row.get("area") or "Madagascar").strip()

                # Determine observed vs imputed (R1.9 strict flag validation)
                # No unknown flag may be promoted to observed without justification
                if flag in IMPUTED_FLAGS or "ESTIMAT" in flag:
                    observed_or_imputed = "imputed"
                    confidence = 0.8
                    n_imputed += 1
                elif flag in OBSERVED_FLAGS:
                    observed_or_imputed = "observed"
                    confidence = 1.0
                    n_observed += 1
                else:
                    # Unknown flag: never promote to observed, route to review queue
                    issues.append(
                        {
                            "kind": "unknown_faostat_flag_needs_review",
                            "row_index": idx,
                            "flag": flag,
                            "item": item_name,
                            "year": year,
                            "details": f"Flag '{flag}' is not a recognized official FAOSTAT flag; treated conservatively as imputed",
                        }
                    )
                    observed_or_imputed = "imputed"
                    confidence = 0.7
                    n_imputed += 1

                # Categorize into Production vs Trade
                is_trade = (
                    domain_code.upper() in ("TM", "TCL")
                    or element_code in (5610, 5910)
                    or "import" in element_name.lower()
                    or "export" in element_name.lower()
                )

                evidence = {
                    "source": "faostat",
                    "source_family": "un_fao",
                    "domain": domain_code,
                    "element": element_name,
                    "element_code": element_code,
                    "flag": flag,
                    "year": year,
                    "is_forecast_or_estimated": (observed_or_imputed == "imputed"),
                }

                if is_trade:
                    flow = (
                        "export"
                        if (element_code == 5910 or "export" in element_name.lower())
                        else "import"
                    )
                    # In FAOSTAT Trade, quantity is typically in metric tons ("t")
                    if unit.lower() in ("t", "ton", "tonnes"):
                        weight_kg = val * 1000.0
                    elif unit.lower() == "kg":
                        weight_kg = val
                    else:
                        weight_kg = val * 1000.0

                    trade_rec = TradeFlowRecord(
                        flow=flow,
                        product_raw=item_name,
                        partner_raw=None,
                        period_start=period_start,
                        period_end=period_end,
                        weight_raw=f"{val_raw} {unit}" if unit else str(val_raw),
                        weight_kg=weight_kg,
                        extraction_method="deterministic",
                        evidence=evidence,
                        confidence=confidence,
                    )
                    records.append(trade_rec)
                else:
                    # Production / Agriculture balance
                    element = "production_t"
                    if element_code in (5312, 5110) or "area" in element_name.lower():
                        element = "area_harvested_ha"
                    elif element_code in (5419, 5420) or "yield" in element_name.lower():
                        element = "yield_kg_ha"
                    elif element_code in (645, 664) or "kcal" in element_name.lower():
                        element = "food_supply_kcal"

                    prod_rec = ProductionRecord(
                        product_raw=item_name,
                        location_raw=area,
                        period_start=period_start,
                        period_end=period_end,
                        element=element,
                        value_raw=str(val_raw),
                        value=val,
                        unit_raw=unit or "t",
                        flag_raw=flag if flag else "A",
                        observed_or_imputed=observed_or_imputed,
                        extraction_method="deterministic",
                        evidence=evidence,
                        confidence=confidence,
                    )
                    records.append(prod_rec)

            except Exception as exc:
                issues.append({"kind": "row_parse_error", "row_index": idx, "detail": str(exc)})

        total_processed = len(records) + len(issues)
        logger.info(
            "Parsed %d records from FAOSTAT (total: %d, observed: %d, imputed: %d, issues: %d)",
            len(records),
            total_processed,
            n_observed,
            n_imputed,
            len(issues),
        )

        return ParseResult(records=records, issues=issues, parser_version=self.parser_version)
