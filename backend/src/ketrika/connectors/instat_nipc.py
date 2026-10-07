"""INSTAT Consumer Price Index (NIPC) connector (SPECS §5.5, MVP_EXECUTION_PLAN T3.5).

Ingests monthly Consumer Price Index (NIPC) series (All items, Food, Rice)
for Madagascar published by the National Statistics Institute (INSTAT).
Supports Excel (XLSX) and CSV with dynamic header row detection.
"""

from __future__ import annotations

import calendar
import csv
import io
import logging
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any, ClassVar

import openpyxl

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.records import CpiRecord

logger = logging.getLogger(__name__)

INSTAT_NIPC_URL = "https://www.instat.mg/statistiques/prix-a-la-consommation/nipc_sample.xlsx"


def _clean_str(val: Any) -> str:
    """Normalize text cell for keyword matching."""
    if val is None:
        return ""
    return (
        str(val)
        .strip()
        .lower()
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("ô", "o")
    )


def _parse_month_year(period_val: Any) -> tuple[int, int] | None:
    """Parse period into (year, month)."""
    if isinstance(period_val, (date, datetime)):
        return period_val.year, period_val.month

    s = str(period_val).strip()
    if not s:
        return None

    # Handle formats: YYYY-MM, YYYY/MM, YYYYM01, MM/YYYY
    if len(s) == 7 and (s[4] == "-" or s[4] == "/"):
        try:
            return int(s[:4]), int(s[5:7])
        except ValueError:
            pass

    if "m" in s.lower():
        parts = s.lower().split("m")
        if len(parts) == 2:
            try:
                return int(parts[0]), int(parts[1])
            except ValueError:
                pass

    if "/" in s:
        parts = s.split("/")
        if len(parts) == 2 and len(parts[1]) == 4:
            try:
                return int(parts[1]), int(parts[0])
            except ValueError:
                pass

    return None


class InstatNipcConnector:
    """Connector for INSTAT Madagascar Consumer Price Index (NIPC) tables."""

    source_id: ClassVar[str] = "instat_nipc"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover NIPC file targets."""
        url = ctx.metadata.get("file_url") or INSTAT_NIPC_URL
        fmt = "xlsx" if url.endswith(".xlsx") else "csv"
        yield DiscoveredItem(
            url=url,
            partition_key="nipc_national",
            hints={"publisher": "INSTAT", "format": fmt},
        )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch NIPC file (Excel or CSV) and store into Bronze layer."""
        mime = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if item.hints.get("format") == "xlsx"
            else "text/csv"
        )
        return ctx.fetch_and_store(item, mime_type=mime)

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse NIPC Excel or CSV using dynamic header detection."""
        if ctx.bronze_store is None:
            raise ValueError("Bronze store is required in RunContext")

        raw_bytes = ctx.bronze_store.get(artifact.object_key)
        rows: list[list[Any]] = []

        is_xlsx = (
            raw_bytes.startswith(b"PK\x03\x04")
            or artifact.mime_type.endswith("spreadsheetml.sheet")
            or artifact.url.endswith(".xlsx")
        )

        if is_xlsx:
            try:
                wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
                ws = wb.active
                if ws is not None:
                    for excel_row in ws.iter_rows(values_only=True):
                        rows.append(list(excel_row))
            except Exception as exc:
                return ParseResult(
                    records=[],
                    issues=[{"kind": "xlsx_read_error", "detail": str(exc)}],
                    parser_version=self.parser_version,
                )
        else:
            text = raw_bytes.decode("utf-8", errors="replace")
            reader = csv.reader(io.StringIO(text))
            for csv_row in reader:
                rows.append(list(csv_row))

        # 1. Dynamic Header Location (MVP_EXECUTION_PLAN T3.5)
        # Search dynamically for row containing period and CPI index column keywords
        header_idx: int | None = None
        period_col_idx: int | None = None
        col_series_map: dict[int, tuple[str, str]] = {}

        for row_num, row in enumerate(rows):
            if not row or not any(cell is not None and str(cell).strip() for cell in row):
                continue

            cleaned_cells = [_clean_str(c) for c in row]
            # Check for period column
            found_period_idx = None
            for idx, c in enumerate(cleaned_cells):
                if any(k in c for k in ("periode", "mois", "date", "annee")):
                    found_period_idx = idx
                    break

            # Check for at least one series column (ensemble, alimentaire, alimentation, riz)
            has_series = any(
                any(k in c for k in ("ensemble", "general", "aliment", "nourriture", "riz", "cpi"))
                for c in cleaned_cells
            )

            if found_period_idx is not None and has_series:
                header_idx = row_num
                period_col_idx = found_period_idx

                for col_idx, cell_str in enumerate(cleaned_cells):
                    if col_idx == period_col_idx:
                        continue
                    orig_label = str(row[col_idx]).strip()
                    if any(k in cell_str for k in ("aliment", "nourriture", "food")):
                        col_series_map[col_idx] = ("cpi_food", orig_label)
                    elif any(k in cell_str for k in ("riz", "rice")):
                        col_series_map[col_idx] = ("cpi_rice", orig_label)
                    elif any(k in cell_str for k in ("ensemble", "general", "total", "global")):
                        col_series_map[col_idx] = ("cpi_total", orig_label)

                break

        if header_idx is None or period_col_idx is None or not col_series_map:
            return ParseResult(
                records=[],
                issues=[
                    {
                        "kind": "header_not_found",
                        "detail": "Failed to dynamically locate NIPC header row",
                    }
                ],
                parser_version=self.parser_version,
            )

        # 2. Extract Data Rows
        records: list[CpiRecord] = []
        issues: list[dict[str, Any]] = []

        for row_num in range(header_idx + 1, len(rows)):
            row = rows[row_num]
            if not row or len(row) <= period_col_idx:
                continue

            period_raw = row[period_col_idx]
            if (
                period_raw is None
                or str(period_raw).strip() == ""
                or str(period_raw).startswith("#")
            ):
                continue

            parsed_my = _parse_month_year(period_raw)
            if parsed_my is None:
                continue

            year, month = parsed_my
            last_day = calendar.monthrange(year, month)[1]
            period_start = date(year, month, 1)
            period_end = date(year, month, last_day)

            for col_idx, (series_code, series_label) in col_series_map.items():
                if col_idx >= len(row):
                    continue
                val_raw = row[col_idx]
                if val_raw is None or str(val_raw).strip() in ("", "-", "ND", "NA"):
                    continue

                try:
                    clean_num_str = str(val_raw).replace(" ", "").replace(",", ".")
                    val = float(clean_num_str)
                    if val <= 0.0:
                        continue

                    rec = CpiRecord(
                        series_code=series_code,
                        series_label=series_label,
                        geo_scope="national",
                        period_start=period_start,
                        period_end=period_end,
                        index_value_raw=str(val_raw),
                        index_value=val,
                        base_period="2016=100",
                        extraction_method="deterministic",
                        evidence={
                            "source": "instat_nipc",
                            "row_index": row_num,
                            "period_raw": str(period_raw),
                            "value_raw": str(val_raw),
                        },
                        confidence=1.0,
                    )
                    records.append(rec)
                except ValueError as exc:
                    issues.append(
                        {
                            "kind": "value_conversion_error",
                            "row_index": row_num,
                            "col_index": col_idx,
                            "detail": str(exc),
                        }
                    )

        return ParseResult(records=records, issues=issues, parser_version=self.parser_version)
