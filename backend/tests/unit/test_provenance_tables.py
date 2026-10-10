"""Synthetic table-reader regressions; no source/model qualification."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook

from ketrika.core.provenance import ProofError, verify_cells
from ketrika.core.provenance_tables import table_cell_reader

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HTML = b"<table><tr><th>product</th><th>price</th></tr><tr><td>rice</td><td>3000.1250<script>9999</script></td></tr><tr><td>maize</td><td>3000.1250</td></tr></table>"


def xlsx(value: str = "3000.1250", formula: bool = False) -> bytes:
    """Minimal simulated OOXML with the exact numeric lexeme under test."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>',
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="xl/workbook.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/></Relationships>',
        )
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Prices" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/></Relationships>',
        )
        f = "<f>SUM(B1)</f>" if formula else ""
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="2"><c r="A2" t="inlineStr"><is><t>rice</t></is></c><c r="B2">{f}<v>{value}</v></c></row></sheetData></worksheet>',
        )
    return output.getvalue()


def test_html_cell_is_anchored_and_script_is_not_a_value():
    reader = table_cell_reader(HTML, "text/html", {"format": "html_table", "table": 0, "row": 1})
    assert reader({"column": 0}) == ((0, 1, 0), "rice")
    assert reader({"column": 1}) == ((0, 1, 1), "3000.1250")
    other = table_cell_reader(HTML, "text/html", {"format": "html_table", "table": 0, "row": 2})
    assert other({"column": 0})[1] == "maize"


def test_xlsx_numeric_lexeme_is_not_rounded_through_float():
    raw = "9007199254740993.12500001"
    reader = table_cell_reader(
        xlsx(raw), XLSX_MIME, {"format": "xlsx_table", "sheet": "Prices", "row": 2}
    )
    assert reader({"column": 1}) == (("Prices", 2, 1), "rice")
    assert reader({"column": 2}) == (("Prices", 2, 2), raw)


def test_xlsx_formula_is_not_proven_by_cached_numeric_value():
    reader = table_cell_reader(
        xlsx(formula=True), XLSX_MIME, {"format": "xlsx_table", "sheet": "Prices", "row": 2}
    )
    with pytest.raises(ProofError, match="formula_unverifiable"):
        reader({"column": 2})


def test_pdf_exact_page_table_row_and_column():
    content = (
        Path(__file__).resolve().parents[1] / "fixtures/miasa_odr/odr_bulletin_850.pdf"
    ).read_bytes()
    reader = table_cell_reader(
        content, "application/pdf", {"format": "pdf_table", "page": 1, "table": 0, "row": 1}
    )
    assert reader({"column": 0}) == ((1, 0, 1, 0), "Alaotra Mangoro (Ambatondrazaka)")
    assert reader({"column": 1}) == ((1, 0, 1, 1), "1650")
    other = table_cell_reader(
        content, "application/pdf", {"format": "pdf_table", "page": 2, "table": 0, "row": 1}
    )
    assert other({"column": 0})[1] == "Vakinankaratra"


@pytest.mark.parametrize(
    "change",
    [
        {"row": -1},
        {"row": True},
        {"row": "1"},
        {"table": -1},
        {"table": True},
        {"table": 30},
        {"row": 50},
    ],
)
def test_bad_html_coordinates_refused(change):
    with pytest.raises(ProofError):
        table_cell_reader(
            HTML, "text/html", {"format": "html_table", "table": 0, "row": 1, **change}
        )


@pytest.mark.parametrize("column", [-1, True, "1", 200])
def test_bad_cell_coordinates_refused(column):
    reader = table_cell_reader(HTML, "text/html", {"format": "html_table", "table": 0, "row": 1})
    with pytest.raises(ProofError):
        reader({"column": column})


@pytest.mark.parametrize(
    "change",
    [
        {"sheet": "Missing"},
        {"sheet": None},
        {"row": 0},
        {"row": True},
        {"row": 1048577},
        {"row": 3},
    ],
)
def test_xlsx_missing_sheet_or_row_is_not_a_success(change):
    with pytest.raises(ProofError):
        table_cell_reader(
            xlsx(), XLSX_MIME, {"format": "xlsx_table", "sheet": "Prices", "row": 2, **change}
        )


@pytest.mark.parametrize("column", [0, True, 16385, 3])
def test_xlsx_bad_or_missing_column_refused(column):
    reader = table_cell_reader(
        xlsx(), XLSX_MIME, {"format": "xlsx_table", "sheet": "Prices", "row": 2}
    )
    with pytest.raises(ProofError):
        reader({"column": column})


@pytest.mark.parametrize(
    "format_name,mime",
    [
        ("html_table", "application/pdf"),
        ("pdf_table", "text/html"),
        ("xlsx_table", "text/html"),
        ("unknown", "text/html"),
    ],
)
def test_mime_mismatch_or_unknown_format_refused(format_name, mime):
    with pytest.raises(ProofError):
        table_cell_reader(HTML, mime, {"format": format_name, "table": 0, "row": 1})


def test_nested_html_table_is_not_an_ambiguous_record():
    with pytest.raises(ProofError, match="unsupported_document_content"):
        table_cell_reader(
            b"<table><tr><td><table><tr><td>3000</td></tr></table></td></tr></table>",
            "text/html",
            {"format": "html_table", "table": 0, "row": 0},
        )


def table_proof(format_name="html_table", *, row=1, first=0, price="3000.1250", identity="rice"):
    return {
        "version": 1,
        "format": format_name,
        "table": 0,
        "row": row,
        "cells": [
            {
                "field": "price_value",
                "role": "value",
                "kind": "number",
                "column": first + 1,
                "expected": price,
            },
            {
                "field": "location_raw",
                "role": "identity",
                "kind": "text",
                "column": first,
                "expected": identity,
            },
        ],
    }


def test_generic_verifier_checks_html_identity_not_just_same_number():
    proof = table_proof()
    assert verify_cells(HTML, "text/html", proof) == 2
    proof["row"] = 2
    with pytest.raises(ProofError, match="identity_mismatch"):
        verify_cells(HTML, "text/html", proof)


def test_generic_verifier_checks_exact_xlsx_value_and_formula():
    proof = table_proof("xlsx_table", row=2, first=1)
    proof["sheet"] = "Prices"
    assert verify_cells(xlsx(), XLSX_MIME, proof) == 2
    with pytest.raises(ProofError, match="formula_unverifiable"):
        verify_cells(xlsx(formula=True), XLSX_MIME, proof)


def test_generic_verifier_reads_pdf_without_utf8_decode():
    content = (
        Path(__file__).resolve().parents[1] / "fixtures/miasa_odr/odr_bulletin_850.pdf"
    ).read_bytes()
    proof = table_proof("pdf_table", price="1650", identity="Alaotra Mangoro (Ambatondrazaka)")
    proof["page"] = 1
    assert verify_cells(content, "application/pdf", proof) == 2


def test_complete_generated_xlsx_workbook_is_supported():
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Prices"
    sheet.append(["product", "price"])
    sheet.append(["rice", 3000.125])
    stream = io.BytesIO()
    workbook.save(stream)
    proof = table_proof("xlsx_table", row=2, first=1)
    proof["sheet"] = "Prices"
    assert verify_cells(stream.getvalue(), XLSX_MIME, proof) == 2


@pytest.mark.parametrize(
    "change", [{"page": -1}, {"page": 0}, {"page": True}, {"page": 99}, {"table": 99}, {"row": 99}]
)
def test_pdf_wrong_or_missing_coordinates_fail(change):
    content = (
        Path(__file__).resolve().parents[1] / "fixtures/miasa_odr/odr_bulletin_850.pdf"
    ).read_bytes()
    with pytest.raises(ProofError):
        table_cell_reader(
            content,
            "application/pdf",
            {"format": "pdf_table", "page": 1, "table": 0, "row": 1, **change},
        )


def test_content_size_bound_is_fail_closed(monkeypatch):
    monkeypatch.setattr("ketrika.core.provenance_tables.MAX_CONTENT", 1)
    with pytest.raises(ProofError, match="document_limit_exceeded"):
        table_cell_reader(HTML, "text/html", {"format": "html_table", "row": 1, "table": 0})


def test_expanded_zip_size_bound_is_fail_closed(monkeypatch):
    monkeypatch.setattr("ketrika.core.provenance_tables.MAX_EXPANDED", 1)
    with pytest.raises(ProofError, match="document_limit_exceeded"):
        table_cell_reader(xlsx(), XLSX_MIME, {"format": "xlsx_table", "row": 2, "sheet": "Prices"})


@pytest.mark.parametrize(
    "format_name,mime,body",
    [
        ("html_table", "text/html", b"\xff"),
        ("pdf_table", "application/pdf", b"not PDF"),
        ("xlsx_table", XLSX_MIME, b"not ZIP"),
    ],
)
def test_malformed_documents_do_not_report_a_valid_cell(format_name, mime, body):
    with pytest.raises(ProofError):
        table_cell_reader(
            body, mime, {"format": format_name, "row": 1, "table": 0, "page": 1, "sheet": "Prices"}
        )
