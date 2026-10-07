"""FAOSTAT connector (SPECS §5.3, MVP_EXECUTION_PLAN T3.3).

Ingests agricultural production (QCL), food balance sheets (FBS), and trade flows (TM/TCL)
for Madagascar from the UN Food and Agriculture Organization (FAOSTAT).
Preserves original flags and accurately maps them to observed_or_imputed.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import date
from typing import Any, ClassVar

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.records import ProductionRecord, TradeFlowRecord

logger = logging.getLogger(__name__)

FAOSTAT_QCL_API_URL = "https://fenixservices.fao.org/faostat/api/v1/en/data/QCL?area=129"

# Known FAOSTAT flags classification
# Observed / Official:
# A: Official figure
# P: Provisional figure
# X: Figure from international reliable source
# '': Blank / standard official figure
OBSERVED_FLAGS = {"A", "P", "X", ""}

# Imputed / Estimated:
# E: Estimated value
# I: Imputed value
# F: FAO estimate
# T: Trend calculation
# M: Missing value / imputed proxy
IMPUTED_FLAGS = {"E", "I", "F", "T", "M"}


class FaostatConnector:
    """Connector for FAOSTAT agricultural statistics (Madagascar)."""

    source_id: ClassVar[str] = "faostat"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover FAOSTAT dataset target."""
        url = ctx.metadata.get("api_url") or FAOSTAT_QCL_API_URL
        yield DiscoveredItem(
            url=url,
            partition_key="qcl_tm",
            hints={"publisher": "FAO", "format": "json"},
        )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch FAOSTAT JSON dataset and store into Bronze layer."""
        return ctx.fetch_and_store(item, mime_type="application/json")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse FAOSTAT JSON payload into typed ProductionRecord and TradeFlowRecord objects."""
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

                # Determine observed vs imputed
                if flag in IMPUTED_FLAGS or "ESTIMAT" in flag:
                    observed_or_imputed = "imputed"
                else:
                    observed_or_imputed = "observed"

                # Categorize into Production vs Trade
                is_trade = (
                    domain_code.upper() in ("TM", "TCL")
                    or element_code in (5610, 5910)
                    or "import" in element_name.lower()
                    or "export" in element_name.lower()
                )

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
                        evidence={
                            "source": "faostat",
                            "domain": domain_code,
                            "element": element_name,
                            "element_code": element_code,
                            "flag": flag,
                        },
                        confidence=1.0,
                    )
                    records.append(trade_rec)
                else:
                    # Production / Agriculture balance
                    element = "production_t"
                    if element_code == 5110 or "area" in element_name.lower():
                        element = "area_harvested_ha"
                    elif element_code == 5419 or "yield" in element_name.lower():
                        element = "yield_kg_ha"
                    elif element_code == 645 or "kcal" in element_name.lower():
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
                        evidence={
                            "source": "faostat",
                            "domain": domain_code,
                            "element": element_name,
                            "element_code": element_code,
                            "flag": flag,
                        },
                        confidence=1.0,
                    )
                    records.append(prod_rec)

            except Exception as exc:
                issues.append({"kind": "row_parse_error", "row_index": idx, "detail": str(exc)})

        return ParseResult(records=records, issues=issues, parser_version=self.parser_version)
