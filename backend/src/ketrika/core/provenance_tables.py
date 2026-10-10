"""Bounded offline table coordinates (ADR-018); never execute document content."""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from collections.abc import Callable, Mapping
from typing import Any
from xml.etree import ElementTree as ET

import pdfplumber
from selectolax.lexbor import LexborHTMLParser

from ketrika.core.provenance import ProofError

CellReader = Callable[[dict[str, Any]], tuple[tuple[Any, ...], Any]]
MAX_CONTENT = 32 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DOC_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _index(value: Any, *, first: int = 0) -> int:
    if type(value) is not int or value < first:
        raise ProofError("invalid_coordinates")
    return value


def _xml(archive: zipfile.ZipFile, name: str) -> ET.Element:
    info = archive.getinfo(name)
    with archive.open(info) as stream:
        data = stream.read(min(info.file_size, MAX_EXPANDED) + 1)
    if len(data) > info.file_size or len(data) > MAX_EXPANDED:
        raise ProofError("document_limit_exceeded")
    decoded = data.decode("utf-8-sig")
    if "<!DOCTYPE" in decoded.upper() or "<!ENTITY" in decoded.upper():
        raise ProofError("invalid_document")
    return ET.fromstring(decoded)


def _column_name(number: int) -> str:
    if number > 16384:
        raise ProofError("invalid_coordinates")
    parts = []
    while number:
        number, remainder = divmod(number - 1, 26)
        parts.append(chr(65 + remainder))
    return "".join(reversed(parts))


def _xlsx_cells(content: bytes, sheet: str, row: int) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if (
            len(entries) > 4096
            or len(set(names)) != len(names)
            or sum(entry.file_size for entry in entries) > MAX_EXPANDED
        ):
            raise ProofError("document_limit_exceeded")
        if any("vbaproject" in name.lower() for name in names):
            raise ProofError("unsupported_document_content")
        content_types = _xml(archive, "[Content_Types].xml")
        workbook_types = [
            node.get("ContentType")
            for node in content_types
            if node.get("PartName") == "/xl/workbook.xml"
        ]
        if workbook_types != [
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
        ]:
            raise ProofError("unsupported_document_content")
        root_relationships = _xml(archive, "_rels/.rels")
        workbook_links = [
            node
            for node in root_relationships
            if node.get("Type")
            == "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
        ]
        if (
            len(workbook_links) != 1
            or workbook_links[0].get("TargetMode") == "External"
            or workbook_links[0].get("Target", "").lstrip("/") != "xl/workbook.xml"
        ):
            raise ProofError("invalid_document")
        workbook = _xml(archive, "xl/workbook.xml")
        worksheets = [
            node for node in workbook.iter(f"{SHEET_NS}sheet") if node.get("name") == sheet
        ]
        if len(worksheets) != 1:
            raise ProofError("sheet_missing")
        relationship_id = worksheets[0].get(f"{DOC_REL_NS}id")
        relationships = _xml(archive, "xl/_rels/workbook.xml.rels")
        matching = [node for node in relationships if node.get("Id") == relationship_id]
        if len(matching) != 1 or matching[0].get("TargetMode") == "External":
            raise ProofError("invalid_document")
        target = matching[0].get("Target")
        if not isinstance(target, str) or not target:
            raise ProofError("invalid_document")
        path = posixpath.normpath(
            target.lstrip("/") if target.startswith("/") else posixpath.join("xl", target)
        )
        if not path.startswith("xl/worksheets/"):
            raise ProofError("invalid_document")
        worksheet = _xml(archive, path)
        shared = (
            [
                "".join(t.text or "" for t in node.iter(f"{SHEET_NS}t"))
                for node in _xml(archive, "xl/sharedStrings.xml")
            ]
            if "xl/sharedStrings.xml" in names
            else []
        )
        rows = [node for node in worksheet.iter(f"{SHEET_NS}row") if node.get("r") == str(row)]
        if len(rows) != 1:
            raise ProofError("cell_missing")
        cells = {}
        for node in rows[0].findall(f"{SHEET_NS}c"):
            address = node.get("r")
            if (
                not isinstance(address, str)
                or not re.fullmatch(r"[A-Z]+\d+", address)
                or address in cells
            ):
                raise ProofError("invalid_coordinates")
            cells[address] = node
        result: dict[str, Any] = {}
        for address, node in cells.items():
            if node.find(f"{SHEET_NS}f") is not None:
                result[address] = ProofError("formula_unverifiable")
                continue
            kind = node.get("t", "n")
            value = node.find(f"{SHEET_NS}v")
            raw = value.text if value is not None else None
            if kind == "inlineStr":
                result[address] = "".join(t.text or "" for t in node.iter(f"{SHEET_NS}t"))
            elif kind == "s":
                if raw is None or not raw.isdigit() or int(raw) >= len(shared):
                    raise ProofError("invalid_document")
                result[address] = shared[int(raw)]
            elif kind in ("n", "str", "d"):
                result[address] = raw
            else:
                result[address] = ProofError("unsupported_cell_type")
        return result


def table_cell_reader(content: bytes, mime: str, proof: Mapping[str, Any]) -> CellReader:
    """Return a literal-coordinate reader constrained to one table row."""
    if len(content) > MAX_CONTENT:
        raise ProofError("document_limit_exceeded")
    format_name = proof.get("format")
    row_index = _index(proof.get("row"), first=1 if format_name == "xlsx_table" else 0)
    scope: tuple[Any, ...]
    try:
        if format_name == "pdf_table" and mime == "application/pdf":
            page_index = _index(proof.get("page"), first=1)
            table_index = _index(proof.get("table"))
            with pdfplumber.open(io.BytesIO(content)) as document:
                if len(document.pages) > 512:
                    raise ProofError("document_limit_exceeded")
                if page_index > len(document.pages):
                    raise ProofError("cell_missing")
                tables = document.pages[page_index - 1].extract_tables()
            scope = (page_index, table_index, row_index)
        elif format_name == "html_table" and mime == "text/html":
            table_index = _index(proof.get("table"))
            parser = LexborHTMLParser(content.decode("utf-8-sig"))
            for node in parser.css("script, style, noscript"):
                node.decompose()
            if parser.css("table table"):
                raise ProofError("unsupported_document_content")
            tables = [
                [[cell.text(strip=True) for cell in tr.css("th, td")] for tr in table.css("tr")]
                for table in parser.css("table")
            ]
            scope = (table_index, row_index)
        elif (
            format_name == "xlsx_table"
            and mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ):
            sheet = proof.get("sheet")
            if not isinstance(sheet, str) or not sheet or row_index > 1048576:
                raise ProofError("invalid_coordinates")
            cells = _xlsx_cells(content, sheet, row_index)

            def read_xlsx(cell: dict[str, Any]) -> tuple[tuple[Any, ...], Any]:
                column = _index(cell.get("column"), first=1)
                address = f"{_column_name(column)}{row_index}"
                value = cells.get(address)
                if isinstance(value, ProofError):
                    raise value
                if value is None:
                    raise ProofError("cell_missing")
                return (sheet, row_index, column), value

            return read_xlsx
        else:
            raise ProofError("unsupported_format")
        if table_index >= len(tables) or row_index >= len(tables[table_index]):
            raise ProofError("cell_missing")
        selected_row = tables[table_index][row_index]

        def read_table(cell: dict[str, Any]) -> tuple[tuple[Any, ...], Any]:
            column = _index(cell.get("column"))
            if column >= len(selected_row) or selected_row[column] is None:
                raise ProofError("cell_missing")
            return (*scope, column), selected_row[column]

        return read_table
    except ProofError:
        raise
    except Exception as exc:
        raise ProofError("invalid_document") from exc
