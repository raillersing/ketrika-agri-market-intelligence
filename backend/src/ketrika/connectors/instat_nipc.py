"""INSTAT Consumer Price Index (NIPC) connector (SPECS §5.5, R1.3, CC-R).

Ingests monthly Consumer Price Index (NIPC) series (All items, Food, Rice, Bread/Cereals)
for Madagascar published by the National Statistics Institute (INSTAT).
Supports Excel (.xlsx) and CSV with multi-sheet parsing, merged cell propagation,
French locale dates, dynamic header detection, base change preservation, and
catalogue discovery via CatalogDiscoveryEngine.
"""

from __future__ import annotations

import calendar
import csv
import io
import logging
import re
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any, ClassVar

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.discovery import CatalogDiscoveryEngine
from ketrika.connectors.records import CpiRecord

logger = logging.getLogger(__name__)

INSTAT_CATALOG_URL = "https://www.instat.mg/statistiques/prix-a-la-consommation"
INSTAT_NIPC_URL = "https://www.instat.mg/statistiques/prix-a-la-consommation/nipc_sample.xlsx"

FRENCH_MONTH_MAP: dict[str, int] = {
    "janvier": 1,
    "janv": 1,
    "jan": 1,
    "fevrier": 2,
    "fevr": 2,
    "fev": 2,
    "mars": 3,
    "mar": 3,
    "avril": 4,
    "avr": 4,
    "mai": 5,
    "juin": 6,
    "jun": 6,
    "juillet": 7,
    "juil": 7,
    "jul": 7,
    "aout": 8,
    "aou": 8,
    "septembre": 9,
    "sept": 9,
    "sep": 9,
    "octobre": 10,
    "oct": 10,
    "novembre": 11,
    "nov": 11,
    "decembre": 12,
    "dec": 12,
}


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
        .replace("ë", "e")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ô", "o")
        .replace("û", "u")
        .replace("ù", "u")
        .replace("î", "i")
        .replace("ï", "i")
        .replace("ç", "c")
        .replace("’", "'")
    )


def _parse_month_year(period_val: Any) -> tuple[int, int] | None:
    """Parse period into (year, month). Supports ISO, French month names, and Excel dates."""
    if isinstance(period_val, (date, datetime)):
        return period_val.year, period_val.month

    s = str(period_val).strip()
    if not s:
        return None

    # Handle formats: YYYY-MM, YYYY/MM, YYYY.MM
    if len(s) >= 7 and s[:4].isdigit() and (s[4] in ("-", "/", ".")) and s[5:7].isdigit():
        try:
            return int(s[:4]), int(s[5:7])
        except ValueError:
            pass

    # Handle formats: MM/YYYY or MM-YYYY
    if len(s) >= 7 and s[:2].isdigit() and (s[2] in ("-", "/", ".")) and s[3:7].isdigit():
        try:
            return int(s[3:7]), int(s[:2])
        except ValueError:
            pass

    # Handle formats: YYYYM01 or YYYY-M01 or YYYY M01
    m_match = re.search(r"(\d{4})\s*[-/]?\s*m\s*(\d{1,2})", s, re.IGNORECASE)
    if m_match:
        try:
            return int(m_match.group(1)), int(m_match.group(2))
        except ValueError:
            pass

    # Handle French month names: e.g. "Janvier 2024", "Fév. 2024", "Mars-2024"
    clean_s = _clean_str(s)
    for m_name, m_num in FRENCH_MONTH_MAP.items():
        if m_name in clean_s:
            y_match = re.search(r"(\d{4})", clean_s)
            if y_match:
                return int(y_match.group(1)), m_num
            # 2-digit year (e.g., "Janv-24")
            y2_match = re.search(r"\b(\d{2})\b", clean_s)
            if y2_match:
                y2 = int(y2_match.group(1))
                full_year = 2000 + y2 if y2 < 70 else 1900 + y2
                return full_year, m_num

    return None


def _detect_base_period(text_lines: list[str]) -> str:
    """Detect CPI base period from text/header, e.g. 'Base 2016 = 100' or 'Base 2011 = 100'."""
    for line in text_lines:
        clean = _clean_str(line)
        m = re.search(r"base\s*:?\s*(\d{4})\s*=\s*100", clean)
        if m:
            return f"{m.group(1)}=100"
        m2 = re.search(r"base\s*:?\s*(\d{4})", clean)
        if m2:
            return f"{m2.group(1)}=100"
    return "2016=100"


def _detect_geo_scope(text_lines: list[str], sheet_name: str = "") -> str:
    """Detect geographic scope (national, urbain, antananarivo, etc.)."""
    full_text = f"{sheet_name} " + " ".join(text_lines)
    clean = _clean_str(full_text)
    if "antananarivo" in clean or "tananarive" in clean:
        return "antananarivo"
    if "urbain" in clean:
        return "urbain"
    return "national"


def _extract_worksheet_grid(ws: Worksheet) -> list[list[Any]]:
    """Extract cell values from openpyxl worksheet, propagating merged cells to all covered cells."""
    max_row = ws.max_row or 0
    max_col = ws.max_column or 0
    if max_row == 0 or max_col == 0:
        return []

    grid: list[list[Any]] = [[None for _ in range(max_col)] for _ in range(max_row)]
    for r in range(1, max_row + 1):
        for c in range(1, max_col + 1):
            grid[r - 1][c - 1] = ws.cell(row=r, column=c).value

    # Replicate merged cells values across their ranges so headers are accessible on all columns
    for merged_range in list(ws.merged_cells.ranges):
        min_c, min_r, max_c, max_r = (
            merged_range.min_col,
            merged_range.min_row,
            merged_range.max_col,
            merged_range.max_row,
        )
        top_left_val = grid[min_r - 1][min_c - 1]
        for r_idx in range(min_r - 1, min(max_r, max_row)):
            for c_idx in range(min_c - 1, min(max_c, max_col)):
                grid[r_idx][c_idx] = top_left_val

    return grid


def _parse_table_grid(
    rows: list[list[Any]],
    sheet_name: str = "default",
    default_base: str | None = None,
    default_scope: str | None = None,
) -> tuple[list[CpiRecord], list[dict[str, Any]]]:
    """Parse 2D table grid (from Excel worksheet or CSV) into CpiRecords with dynamic detection."""
    if not rows:
        return [], []

    # 1. Inspect preamble lines for base period and geographic scope
    preamble_texts = [" ".join(str(c) for c in row if c is not None) for row in rows[:15]]
    base_period = default_base or _detect_base_period(preamble_texts)
    geo_scope = default_scope or _detect_geo_scope(preamble_texts, sheet_name=sheet_name)

    # 2. Dynamic Header Location
    header_idx: int | None = None
    period_col_idx: int | None = None
    col_series_map: dict[int, tuple[str, str]] = {}

    for row_num, row in enumerate(rows):
        if not row or not any(cell is not None and str(cell).strip() for cell in row):
            continue

        cleaned_cells = [_clean_str(c) for c in row]

        # Find period column
        found_period_idx = None
        for idx, c in enumerate(cleaned_cells):
            if any(k in c for k in ("periode", "mois", "date", "annee")):
                found_period_idx = idx
                break

        # Check for series presence
        has_series = any(
            any(
                k in c
                for k in ("ensemble", "general", "aliment", "nourriture", "riz", "cpi", "pain")
            )
            for c in cleaned_cells
        )

        if found_period_idx is not None and has_series:
            header_idx = row_num
            period_col_idx = found_period_idx

            for col_idx, cell_str in enumerate(cleaned_cells):
                if col_idx == period_col_idx:
                    continue
                orig_label = str(row[col_idx]).strip()
                if any(k in cell_str for k in ("pain", "cereale", "cereal", "farine")):
                    col_series_map[col_idx] = ("cpi_bread_cereals", orig_label)
                elif any(k in cell_str for k in ("riz", "rice")):
                    col_series_map[col_idx] = ("cpi_rice", orig_label)
                elif any(k in cell_str for k in ("aliment", "nourriture", "food", "boisson")):
                    col_series_map[col_idx] = ("cpi_food", orig_label)
                elif any(k in cell_str for k in ("ensemble", "general", "total", "global", "cpi")):
                    col_series_map[col_idx] = ("cpi_total", orig_label)

            break

    if header_idx is None or period_col_idx is None or not col_series_map:
        return [], [
            {
                "kind": "header_not_found",
                "sheet": sheet_name,
                "detail": f"Failed to dynamically locate NIPC header row in sheet '{sheet_name}'",
            }
        ]

    # 3. Extract Observations
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
            or str(period_raw).strip().startswith("#")
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
            if val_raw is None:
                continue

            clean_val_str = str(val_raw).strip().upper()
            if clean_val_str in ("", "-", "ND", "N.D.", "NA", "N.A.", "..", "..."):
                continue

            try:
                clean_num_str = clean_val_str.replace(" ", "").replace(",", ".")
                val = float(clean_num_str)
                if val <= 0.0:
                    continue

                rec = CpiRecord(
                    series_code=series_code,
                    series_label=series_label,
                    geo_scope=geo_scope,
                    period_start=period_start,
                    period_end=period_end,
                    index_value_raw=str(val_raw),
                    index_value=val,
                    base_period=base_period,
                    extraction_method="deterministic",
                    evidence={
                        "source": "instat_nipc",
                        "sheet_name": sheet_name,
                        "row_index": row_num,
                        "col_index": col_idx,
                        "period_raw": str(period_raw),
                        "value_raw": str(val_raw),
                        "base_period": base_period,
                    },
                    confidence=1.0,
                )
                records.append(rec)
            except ValueError as exc:
                issues.append(
                    {
                        "kind": "value_conversion_error",
                        "sheet": sheet_name,
                        "row_index": row_num,
                        "col_index": col_idx,
                        "detail": str(exc),
                    }
                )

    return records, issues


class InstatNipcConnector:
    """Connector for INSTAT Madagascar Consumer Price Index (NIPC) tables."""

    source_id: ClassVar[str] = "instat_nipc"
    parser_version: ClassVar[str] = "1.1.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover NIPC file targets via official catalog discovery or explicit targets."""
        # 1. Explicit list of URLs in metadata
        file_urls = ctx.metadata.get("file_urls")
        if file_urls and isinstance(file_urls, list):
            for u in file_urls:
                url_str = str(u)
                fmt = (
                    "xlsx"
                    if url_str.endswith(".xlsx")
                    else ("xls" if url_str.endswith(".xls") else "csv")
                )
                yield DiscoveredItem(
                    url=url_str,
                    partition_key="nipc_national",
                    hints={"publisher": "INSTAT", "format": fmt},
                )
            return

        # 2. Single explicit URL in metadata
        file_url = ctx.metadata.get("file_url")
        if file_url:
            url_str = str(file_url)
            fmt = (
                "xlsx"
                if url_str.endswith(".xlsx")
                else ("xls" if url_str.endswith(".xls") else "csv")
            )
            yield DiscoveredItem(
                url=url_str,
                partition_key="nipc_national",
                hints={"publisher": "INSTAT", "format": fmt},
            )
            return

        # 3. Dynamic Catalog Discovery with SSRF and domain restrictions (R1.2, R1.3)
        catalog_url = ctx.metadata.get("catalog_url") or INSTAT_CATALOG_URL
        allow_loopback = ctx.metadata.get("allow_loopback", False)
        allowed_domains: list[str] = list(ctx.metadata.get("allowed_domains") or ["instat.mg"])
        if allow_loopback:
            allowed_domains.extend(["localhost", "127.0.0.1"])

        engine = CatalogDiscoveryEngine(
            source_id=self.source_id,
            http_client=ctx.http_client,
            allowed_domains=allowed_domains,
            max_pages=5,
            allow_loopback=allow_loopback,
        )

        nipc_link_pattern = re.compile(
            r"/.*(?:nipc|ipc|prix.*consommation|indice).*\.(?:xlsx|xls|csv)$",
            re.IGNORECASE,
        )

        try:
            discovery_res = engine.discover_html_editions(
                start_url=catalog_url,
                link_pattern=nipc_link_pattern,
            )
            if discovery_res.editions:
                for edition in discovery_res.editions:
                    fmt = (
                        "xlsx"
                        if edition.url.endswith(".xlsx")
                        else ("xls" if edition.url.endswith(".xls") else "csv")
                    )
                    hints = dict(
                        edition.hints,
                        parent_url=edition.parent_url,
                        publisher="INSTAT",
                        format=fmt,
                    )
                    yield DiscoveredItem(
                        url=edition.url,
                        partition_key="nipc_national",
                        published_at=edition.published_at,
                        hints=hints,
                    )
                return
        except Exception as exc:
            logger.warning("Catalog discovery failed on %s: %s", catalog_url, exc)

        # Fallback to configured default entrypoint
        logger.info("Falling back to standard INSTAT NIPC URL: %s", INSTAT_NIPC_URL)
        yield DiscoveredItem(
            url=INSTAT_NIPC_URL,
            partition_key="nipc_national",
            hints={"publisher": "INSTAT", "format": "xlsx", "fallback": "true"},
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
        """Parse NIPC Excel or CSV using multi-sheet traversal and dynamic header detection."""
        if ctx.bronze_store is None:
            raise ValueError("Bronze store is required in RunContext")

        raw_bytes = ctx.bronze_store.get(artifact.object_key)

        is_xlsx = (
            raw_bytes.startswith(b"PK\x03\x04")
            or artifact.mime_type.endswith("spreadsheetml.sheet")
            or artifact.url.endswith(".xlsx")
        )

        all_records: list[CpiRecord] = []
        all_issues: list[dict[str, Any]] = []

        if is_xlsx:
            try:
                wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
                for ws in wb.worksheets:
                    grid = _extract_worksheet_grid(ws)
                    if len(grid) < 2:
                        continue
                    sheet_recs, sheet_issues = _parse_table_grid(grid, sheet_name=ws.title)
                    all_records.extend(sheet_recs)
                    if not sheet_recs and sheet_issues:
                        all_issues.extend(sheet_issues)
            except Exception as exc:
                return ParseResult(
                    records=[],
                    issues=[{"kind": "xlsx_read_error", "detail": str(exc)}],
                    parser_version=self.parser_version,
                )
        else:
            try:
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = raw_bytes.decode("latin1", errors="replace")
            reader = csv.reader(io.StringIO(text))
            csv_rows = [list(r) for r in reader]
            sheet_recs, sheet_issues = _parse_table_grid(csv_rows, sheet_name="csv")
            all_records.extend(sheet_recs)
            all_issues.extend(sheet_issues)

        if not all_records:
            return ParseResult(
                records=[],
                issues=all_issues
                or [
                    {
                        "kind": "header_not_found",
                        "detail": "Failed to locate valid NIPC header in any sheet",
                    }
                ],
                parser_version=self.parser_version,
            )

        return ParseResult(records=all_records, issues=[], parser_version=self.parser_version)
