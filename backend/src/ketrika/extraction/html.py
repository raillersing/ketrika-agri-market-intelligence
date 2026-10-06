"""Deterministic HTML text and table extraction using selectolax (SPECS §1, §11)."""

from __future__ import annotations

from dataclasses import dataclass

from selectolax.lexbor import LexborHTMLParser


@dataclass
class HtmlContent:
    """Extracted text and structured tables from an HTML document."""

    text: str
    tables: list[list[list[str]]]


def extract_html_content(html: str | bytes) -> HtmlContent:
    """Parse HTML and extract clean text (excluding scripts/styles) and HTML tables."""
    if isinstance(html, bytes):
        raw_text = html.decode("utf-8", errors="replace")
    else:
        raw_text = html

    parser = LexborHTMLParser(raw_text)

    # 1. Extract tables
    tables: list[list[list[str]]] = []
    for table_node in parser.css("table"):
        table_rows: list[list[str]] = []
        for tr in table_node.css("tr"):
            row_cells: list[str] = []
            for cell in tr.css("th, td"):
                cell_text = cell.text(strip=True)
                row_cells.append(cell_text)
            if row_cells:
                table_rows.append(row_cells)
        if table_rows:
            tables.append(table_rows)

    # 2. Decompose script and style nodes for clean text extraction
    for tag in parser.css("script, style, noscript, header, footer, nav"):
        tag.decompose()

    body = parser.body
    body_text = (
        body.text(separator=" ", strip=True) if body else parser.text(separator=" ", strip=True)
    )

    return HtmlContent(text=body_text, tables=tables)
