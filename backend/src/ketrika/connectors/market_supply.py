"""Connector for physical market supply arrivals, stock inventories and basin harvest volumes (SPECS §27, ADR-088, ADR-089, R5.2)."""

from __future__ import annotations

import csv
import io
import json
import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any, ClassVar

from ketrika.connectors.base import (
    Connector,
    DiscoveredItem,
    ParseResult,
    RawArtifact,
    RunContext,
)
from ketrika.connectors.records import StockRecord
from ketrika.supply.contracts import (
    MarketType,
    QuantityMeasurementMode,
    QuantityTarget,
    QuantityUnit,
    convert_quantity_to_kg,
    validate_payload_no_pii,
)

logger = logging.getLogger(__name__)


class MarketSupplyConnector(Connector):
    """Ingests official and institutional market supply observations (arrivals and stocks) under zero-PII rules."""

    source_id = "market_supply"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover available market supply datasets from registered institutional drops or metadata."""
        urls_meta = ctx.metadata.get("urls") if ctx and ctx.metadata else None
        if urls_meta and isinstance(urls_meta, list):
            for u in urls_meta:
                if isinstance(u, dict) and "url" in u:
                    yield DiscoveredItem(
                        url=str(u["url"]),
                        partition_key=str(u.get("partition_key", "supply_drop_custom")),
                        hints={str(k): str(v) for k, v in u.get("hints", {}).items()}
                        if isinstance(u.get("hints"), dict)
                        else {},
                    )
            return

        # Default standard institutional drops
        yield DiscoveredItem(
            url="file:///workspace/data/supply/odr_suivi_approvisionnement_anosibe_2024.csv",
            partition_key="odr_anosibe_2024",
            hints={"market": "Anosibe", "year": "2024", "source": "ODR"},
        )
        yield DiscoveredItem(
            url="file:///workspace/data/supply/odr_suivi_collecte_ambatondrazaka_2024.csv",
            partition_key="odr_ambatondrazaka_2024",
            hints={"market": "Ambatondrazaka", "year": "2024", "source": "ODR"},
        )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch drop payload into Bronze storage and register immutable SHA-256."""
        if ctx.bronze_store is None:
            raise ValueError("BronzeStore is required in RunContext")

        return ctx.fetch_and_store(item, mime_type="text/csv")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse supply arrival and stock inventory payload into normalized StockRecord objects."""
        if ctx.bronze_store is None:
            raise ValueError("BronzeStore is required in RunContext")

        raw_bytes = ctx.bronze_store.get(artifact.object_key)
        if not raw_bytes:
            return ParseResult(
                records=[], issues=[{"error": "Empty artifact payload"}], parser_version="1.0.0"
            )

        # Attempt to decode text
        try:
            text_content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text_content = raw_bytes.decode("latin-1", errors="replace")

        records: list[StockRecord] = []
        issues: list[dict[str, Any]] = []

        # Check for JSON format first
        trimmed = text_content.strip()
        if trimmed.startswith("{") or trimmed.startswith("["):
            try:
                data = json.loads(trimmed)
                items = data if isinstance(data, list) else data.get("observations", [])
                for idx, row in enumerate(items):
                    try:
                        validate_payload_no_pii(row)
                        rec = self._parse_dict_row(row, artifact)
                        records.append(rec)
                    except ValueError as err:
                        issues.append({"row_index": idx, "error": str(err)})
                return ParseResult(records=records, issues=issues, parser_version="1.0.0")
            except json.JSONDecodeError:
                pass  # Fall through to CSV parser

        # CSV format parsing
        try:
            reader = csv.DictReader(io.StringIO(text_content))
            if not reader.fieldnames:
                return ParseResult(
                    records=[], issues=[{"error": "CSV contains no header"}], parser_version="1.0.0"
                )

            # Pre-scan headers for PII
            header_dict = dict.fromkeys(reader.fieldnames, "")
            validate_payload_no_pii(header_dict)

            for idx, row in enumerate(reader, start=1):
                try:
                    validate_payload_no_pii(row)
                    rec = self._parse_csv_row(row, artifact)
                    records.append(rec)
                except ValueError as err:
                    issues.append({"row_index": idx, "error": str(err), "row": row})
        except ValueError as pii_err:
            issues.append({"error": f"PII_REJECTION: {pii_err}"})

        return ParseResult(records=records, issues=issues, parser_version="1.0.0")

    def _parse_csv_row(self, row: dict[str, str], artifact: RawArtifact) -> StockRecord:
        """Parse and normalize a single CSV row into StockRecord."""
        target_str = (row.get("target") or "stock_inventory").strip().lower()
        if target_str not in [t.value for t in QuantityTarget]:
            raise ValueError(
                f"Invalid target '{target_str}'. Expected one of {[t.value for t in QuantityTarget]}"
            )

        mode_str = (row.get("measurement_mode") or "declared_trader").strip().lower()
        if mode_str not in [m.value for m in QuantityMeasurementMode]:
            mode_str = QuantityMeasurementMode.DECLARED_TRADER.value

        market_type_str = (row.get("market_type") or "regional_wholesale").strip().lower()
        if market_type_str not in [m.value for m in MarketType]:
            market_type_str = MarketType.REGIONAL_WHOLESALE.value

        product_raw = (row.get("product_raw") or row.get("product_code") or "").strip()
        if not product_raw:
            raise ValueError("product_raw is required")

        location_raw = (
            row.get("location_raw") or row.get("market_name") or row.get("market_code") or ""
        ).strip()
        market_code = (row.get("market_code") or "").strip() or None

        # Parse dates
        obs_date_str = (row.get("observed_date") or row.get("date") or "").strip()
        p_start_str = (row.get("period_start") or obs_date_str).strip()
        p_end_str = (row.get("period_end") or obs_date_str).strip()

        if not p_start_str or not p_end_str:
            raise ValueError("Observation dates cannot be determined from row")

        period_start = date.fromisoformat(p_start_str)
        period_end = date.fromisoformat(p_end_str)

        # Quantity and unit
        qty_str = (row.get("quantity_raw") or row.get("quantity_value") or "").strip()
        if not qty_str:
            raise ValueError("quantity is missing")
        qty_raw = float(qty_str.replace(",", "."))
        if qty_raw <= 0:
            raise ValueError(f"Quantity must be positive, got {qty_raw}")

        unit_raw = (row.get("unit_raw") or "kg").strip().lower()
        unit_enum = QuantityUnit.KG
        for u in QuantityUnit:
            if u.value == unit_raw:
                unit_enum = u
                break

        quantity_kg = convert_quantity_to_kg(qty_raw, unit_enum, product_code=product_raw)

        published_at_str = (row.get("published_at") or "").strip()
        published_at = (
            datetime.fromisoformat(published_at_str).astimezone(UTC) if published_at_str else None
        )

        stock_status = (row.get("stock_status") or "sufficient").strip()

        return StockRecord(
            product_raw=product_raw,
            location_raw=location_raw,
            period_start=period_start,
            period_end=period_end,
            quantity_raw=str(qty_raw),
            quantity_value=quantity_kg,
            unit_raw=unit_raw,
            stock_status=stock_status,
            published_at=published_at,
            target=target_str,
            measurement_mode=mode_str,
            market_type=market_type_str,
            market_code=market_code,
        )

    def _parse_dict_row(self, row: dict[str, Any], artifact: RawArtifact) -> StockRecord:
        """Parse and normalize a single dictionary row into StockRecord."""
        target_str = str(row.get("target") or "stock_inventory").strip().lower()
        product_raw = str(row.get("product_raw") or row.get("product_code") or "").strip()
        location_raw = str(row.get("location_raw") or row.get("market_name") or "").strip()
        market_code = str(row.get("market_code") or "").strip() or None

        obs_date_str = str(row.get("observed_date") or row.get("date") or "").strip()
        p_start_str = str(row.get("period_start") or obs_date_str).strip()
        p_end_str = str(row.get("period_end") or obs_date_str).strip()

        period_start = date.fromisoformat(p_start_str)
        period_end = date.fromisoformat(p_end_str)

        qty_raw = float(row.get("quantity_raw") or row.get("quantity_value") or 0.0)
        unit_raw = str(row.get("unit_raw") or "kg").strip().lower()

        unit_enum = QuantityUnit.KG
        for u in QuantityUnit:
            if u.value == unit_raw:
                unit_enum = u
                break

        quantity_kg = convert_quantity_to_kg(qty_raw, unit_enum, product_code=product_raw)

        return StockRecord(
            product_raw=product_raw,
            location_raw=location_raw,
            period_start=period_start,
            period_end=period_end,
            quantity_raw=str(qty_raw),
            quantity_value=quantity_kg,
            unit_raw=unit_raw,
            stock_status=str(row.get("stock_status") or "sufficient"),
            target=target_str,
            measurement_mode=str(row.get("measurement_mode") or "declared_trader"),
            market_type=str(row.get("market_type") or "regional_wholesale"),
            market_code=market_code,
        )
