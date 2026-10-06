"""PDF text, table extraction and page rendering utilities (SPECS §11)."""

from __future__ import annotations

import io
from dataclasses import dataclass

import pdfplumber
import pypdfium2 as pdfium


@dataclass
class PdfPage:
    """Extracted content and rendering capability for a single PDF page."""

    page_num: int  # 1-indexed
    text: str
    tables: list[list[list[str | None]]]
    _pdf_bytes: bytes

    def render_png(self, scale: float = 2.0) -> bytes:
        """Render page to PNG bytes using pypdfium2."""
        pdf = pdfium.PdfDocument(self._pdf_bytes)
        page = pdf.get_page(self.page_num - 1)
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()
        out_buf = io.BytesIO()
        pil_image.save(out_buf, format="PNG")
        return out_buf.getvalue()


def extract_pdf_pages(pdf_bytes: bytes) -> list[PdfPage]:
    """Extract text and tables page-by-page from raw PDF bytes."""
    pages: list[PdfPage] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            extracted_text = page.extract_text() or ""
            extracted_tables = page.extract_tables() or []
            pages.append(
                PdfPage(
                    page_num=idx,
                    text=extracted_text,
                    tables=extracted_tables,
                    _pdf_bytes=pdf_bytes,
                )
            )
    return pages
