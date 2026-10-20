"""Connector for MiASA Observatoire du Riz (ODR) rice market bulletins (SPECS §5.2, §11, T4.1)."""

from __future__ import annotations

import calendar
import hashlib
import io
import logging
import re
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from typing import Any, ClassVar

import pdfplumber
from pydantic import BaseModel

from ketrika.connectors.base import (
    Connector,
    DiscoveredItem,
    ParseResult,
    RawArtifact,
    RunContext,
)
from ketrika.connectors.discovery import CatalogDiscoveryEngine
from ketrika.connectors.records import PriceRecord, RecordBase
from ketrika.core.registry import find_repo_root
from ketrika.extraction.llm.base import LLMPart
from ketrika.extraction.llm.replay import ReplayClient
from ketrika.extraction.pdf import extract_pdf_pages, is_scanned_pdf
from ketrika.extraction.reconcile import reconcile_records

logger = logging.getLogger(__name__)


class OdrPriceItem(BaseModel):
    """Pydantic model representing an extracted price item by LLM."""

    product_raw: str
    variety: str | None = None
    actor_level: str
    location_raw: str
    price_raw: str
    price_value: float | None = None
    missing_code: str | None = None
    evidence_text: str


class OdrPageExtraction(BaseModel):
    """Pydantic container model for page-level LLM extraction."""

    items: list[OdrPriceItem] = []


MONTH_MAP = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}


def _clean_cell(val: Any) -> str:
    """Normalize whitespace and strip cell content."""
    if val is None:
        return ""
    return " ".join(str(val).split())


def _parse_bulletin_metadata(full_text: str) -> tuple[int | None, date | None, date | None]:
    """Parse bulletin number and observation period dates from document text."""
    # Bulletin number
    num_match = re.search(r"BULLETIN\s+(?:N°|NO\.?)\s*(\d+)", full_text, re.IGNORECASE)
    bulletin_num = int(num_match.group(1)) if num_match else None

    # Observation period: e.g. "Période : Janvier 2024" or "PÉRIODE : Mai 2018"
    period_match = re.search(r"P[EÉ]RIODE\s*:\s*([A-Za-zÀ-ÿ]+)\s+(\d{4})", full_text, re.IGNORECASE)
    if period_match:
        m_name = period_match.group(1).lower()
        year = int(period_match.group(2))
        month = MONTH_MAP.get(m_name, 1)
        last_day = calendar.monthrange(year, month)[1]
        period_start = date(year, month, 1)
        period_end = date(year, month, last_day)
    else:
        period_start = None
        period_end = None

    return bulletin_num, period_start, period_end


class MiasaOdrConnector(Connector):
    """Connector for official Ministry of Agriculture (MiASA) / Observatoire du Riz bulletins."""

    source_id: ClassVar[str] = "miasa_odr"
    parser_version: ClassVar[str] = "1.1.0"
    dual_extraction: bool = True

    def __init__(self, dual_extraction: bool = True) -> None:
        self.dual_extraction = dual_extraction

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover available ODR bulletins via official catalog discovery or explicit targets."""
        # 1. Explicit targets in metadata
        file_urls = ctx.metadata.get("file_urls")
        if file_urls and isinstance(file_urls, list):
            for u in file_urls:
                url_str = str(u)
                ed_match = re.search(r"bulletin[-_]?(\d+)", url_str, re.IGNORECASE)
                ed_id = ed_match.group(1) if ed_match else "custom"
                yield DiscoveredItem(
                    url=url_str,
                    partition_key=f"odr_bulletin_{ed_id}",
                    hints={"edition": ed_id, "publisher": "MiASA/ODR", "format": "pdf"},
                )
            return

        file_url = ctx.metadata.get("file_url")
        if file_url:
            url_str = str(file_url)
            ed_match = re.search(r"bulletin[-_]?(\d+)", url_str, re.IGNORECASE)
            ed_id = ed_match.group(1) if ed_match else "custom"
            yield DiscoveredItem(
                url=url_str,
                partition_key=f"odr_bulletin_{ed_id}",
                hints={"edition": ed_id, "publisher": "MiASA/ODR", "format": "pdf"},
            )
            return

        # 2. Dynamic Catalog Discovery (R1.2, R1.4)
        catalog_url = (
            ctx.metadata.get("catalog_url") or "http://www.agriculture.gov.mg/odr/bulletins"
        )
        allow_loopback = ctx.metadata.get("allow_loopback", False)
        allowed_domains: list[str] = list(
            ctx.metadata.get("allowed_domains") or ["agriculture.gov.mg"]
        )
        if allow_loopback:
            allowed_domains.extend(["localhost", "127.0.0.1"])

        engine = CatalogDiscoveryEngine(
            source_id=self.source_id,
            http_client=ctx.http_client,
            allowed_domains=allowed_domains,
            max_pages=5,
            allow_loopback=allow_loopback,
        )

        odr_link_pattern = re.compile(
            r"/.*(?:bulletin|odr)[-_]?(\d+)?.*\.pdf$",
            re.IGNORECASE,
        )

        try:
            discovery_res = engine.discover_html_editions(
                start_url=catalog_url,
                link_pattern=odr_link_pattern,
            )
            if discovery_res.editions:
                for edition in discovery_res.editions:
                    ed_match = re.search(r"bulletin[-_]?(\d+)", edition.url, re.IGNORECASE)
                    ed_id = (
                        ed_match.group(1) if ed_match else (edition.edition_identifier or "unknown")
                    )
                    hints = dict(
                        edition.hints,
                        parent_url=edition.parent_url,
                        publisher="MiASA/ODR",
                        format="pdf",
                        edition=ed_id,
                    )
                    yield DiscoveredItem(
                        url=edition.url,
                        partition_key=f"odr_bulletin_{ed_id}",
                        published_at=edition.published_at,
                        hints=hints,
                    )
                return
        except Exception as exc:
            logger.warning("Catalog discovery failed on %s: %s", catalog_url, exc)

        # 3. Fallback baseline historical catalog
        logger.info("Falling back to standard baseline ODR catalog editions")
        catalog = [
            DiscoveredItem(
                url="http://www.agriculture.gov.mg/odr/bulletin_850.pdf",
                partition_key="odr_bulletin_850",
                published_at=datetime(2024, 1, 22, 8, 0, tzinfo=UTC),
                hints={
                    "edition": "850",
                    "period": "2024-01",
                    "publisher": "MiASA/ODR",
                    "format": "pdf",
                },
            ),
            DiscoveredItem(
                url="http://www.agriculture.gov.mg/odr/bulletin_710.pdf",
                partition_key="odr_bulletin_710",
                published_at=datetime(2021, 10, 25, 8, 0, tzinfo=UTC),
                hints={
                    "edition": "710",
                    "period": "2021-10",
                    "publisher": "MiASA/ODR",
                    "format": "pdf",
                },
            ),
            DiscoveredItem(
                url="http://www.agriculture.gov.mg/odr/bulletin_520.pdf",
                partition_key="odr_bulletin_520",
                published_at=datetime(2018, 5, 20, 8, 0, tzinfo=UTC),
                hints={
                    "edition": "520",
                    "period": "2018-05",
                    "publisher": "MiASA/ODR",
                    "format": "pdf",
                },
            ),
        ]
        yield from catalog

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch ODR bulletin PDF artifact and store in Bronze."""
        if ctx.offline or ctx.http_client is None:
            root = find_repo_root()
            filename = (
                f"{item.partition_key}.pdf" if item.partition_key else "odr_bulletin_sample.pdf"
            )
            fixture_path = root / "backend" / "tests" / "fixtures" / "miasa_odr" / filename
            if not fixture_path.exists():
                fallback = (
                    root / "backend" / "tests" / "fixtures" / "miasa_odr" / "odr_bulletin_850.pdf"
                )
                fixture_path = fallback if fallback.exists() else fixture_path

            with open(fixture_path, "rb") as f:
                pdf_bytes = f.read()

            content_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
            now = datetime.now(UTC)
            object_key = f"{self.source_id}/{now.year}/{now.month:02d}/{content_sha256}.pdf"

            if ctx.bronze_store:
                bronze_art = ctx.bronze_store.put(
                    source_id=self.source_id,
                    content=pdf_bytes,
                    mime_type="application/pdf",
                    url=item.url,
                )
                object_key = bronze_art.object_key

            return RawArtifact(
                source_record_id="",
                object_key=object_key,
                content_sha256=content_sha256,
                mime_type="application/pdf",
                url=item.url,
                is_new=True,
                published_at=item.published_at,
            )

        return ctx.fetch_and_store(item, mime_type="application/pdf")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse ODR bulletin PDF tables with deterministic extractor and dual LLM reconciliation."""
        if not ctx.bronze_store:
            raise RuntimeError("BronzeStore required for parsing ODR artifacts")

        pdf_bytes = ctx.bronze_store.get(artifact.object_key)
        pages = extract_pdf_pages(pdf_bytes)
        if not pages:
            return ParseResult(records=[], issues=[], parser_version=self.parser_version)

        # 0. Check for scanned raster PDF (no selectable text)
        if is_scanned_pdf(pages):
            return ParseResult(
                records=[],
                issues=[
                    {
                        "kind": "scanned_pdf_needs_review",
                        "detail": "PDF contains scanned raster pages with no extractable text; OCR is not authorized without extension contract",
                    }
                ],
                parser_version=self.parser_version,
            )

        # 1. Parse document metadata (bulletin number, observation period)
        full_text = "\n".join(p.text for p in pages)
        bulletin_num, p_start, p_end = _parse_bulletin_metadata(full_text)

        # Fallback to publication month if period wasn't extracted from text
        if p_start is None or p_end is None:
            pub_date = artifact.published_at.date() if artifact.published_at else date.today()
            last_day = calendar.monthrange(pub_date.year, pub_date.month)[1]
            p_start = date(pub_date.year, pub_date.month, 1)
            p_end = date(pub_date.year, pub_date.month, last_day)

        page_texts: dict[int, str] = {p.page_num: p.text for p in pages}

        # 2. Deterministic Extraction
        det_records: list[RecordBase] = []
        issues: list[dict[str, Any]] = []
        recognized_tables_count = 0

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for p_idx, page in enumerate(pdf.pages, start=1):
                extracted_tables = page.extract_tables() or []
                for table in extracted_tables:
                    if not table or len(table) < 2:
                        continue

                    header_row = [_clean_cell(c) for c in table[0]]
                    hdr_joined = " ".join(header_row).lower()

                    # Producer table (Paddy)
                    if (
                        "producteur" in hdr_joined
                        or "paddy" in hdr_joined
                        or "collecte" in hdr_joined
                    ):
                        recognized_tables_count += 1
                        for row in table[1:]:
                            if len(row) < 2:
                                continue
                            loc_raw = _clean_cell(row[0])
                            pr_raw = _clean_cell(row[1])
                            if not loc_raw:
                                continue

                            is_missing = pr_raw.upper() in (
                                "ND",
                                "NA",
                                "-",
                                "N.D.",
                                "N.A.",
                                "",
                                "NONE",
                            )
                            missing_code = (
                                (pr_raw.upper() if pr_raw.upper() in ("ND", "NA") else "ND")
                                if is_missing
                                else None
                            )

                            price_val: float | None = None
                            if not is_missing:
                                try:
                                    clean_val = pr_raw.replace(" ", "").replace(",", ".")
                                    price_val = float(clean_val)
                                except ValueError:
                                    price_val = None

                            evidence = {
                                "page": p_idx,
                                "text": f"{loc_raw} {pr_raw}",
                                "table": "producer",
                            }

                            det_records.append(
                                PriceRecord(
                                    product_raw="Riz paddy",
                                    variety=None,
                                    actor_level="producer",
                                    location_raw=loc_raw,
                                    period_start=p_start,
                                    period_end=p_end,
                                    published_at=artifact.published_at,
                                    price_raw=pr_raw,
                                    price_value=price_val,
                                    unit_raw="kg",
                                    currency_raw="MGA",
                                    missing_code=missing_code,
                                    extraction_method="deterministic",
                                    evidence=evidence,
                                    confidence=0.95,
                                )
                            )

                    # Wholesale table
                    elif "gros" in hdr_joined:
                        recognized_tables_count += 1
                        self._parse_variety_table(
                            table=table,
                            actor_level="wholesale",
                            p_idx=p_idx,
                            p_start=p_start,
                            p_end=p_end,
                            artifact=artifact,
                            out_records=det_records,
                        )

                    # Retail table
                    elif "détail" in hdr_joined or "consommation" in hdr_joined:
                        recognized_tables_count += 1
                        self._parse_variety_table(
                            table=table,
                            actor_level="retail",
                            p_idx=p_idx,
                            p_start=p_start,
                            p_end=p_end,
                            artifact=artifact,
                            out_records=det_records,
                        )

        # 3. Check for layout drift / schema change
        if recognized_tables_count == 0:
            return ParseResult(
                records=[],
                issues=[
                    {
                        "kind": "layout_changed",
                        "detail": "ODR recognized tables (producer/wholesale/retail) not found: layout or schema drift detected",
                    }
                ],
                parser_version=self.parser_version,
            )

        # 4. Dual Extraction with LLM (SPECS §11.1)
        llm_records: list[RecordBase] = []
        if self.dual_extraction:
            llm_client = ctx.llm_client or ReplayClient()

            for p_idx, pdf_page in enumerate(pages, start=1):
                try:
                    parts = [
                        LLMPart(text=pdf_page.text),
                    ]
                    llm_data, _ = llm_client.extract(
                        schema=OdrPageExtraction,
                        parts=parts,
                        prompt_id="miasa_odr_extract",
                        prompt_version="v1",
                        content_sha256=artifact.content_sha256,
                        page=p_idx,
                    )

                    for item in llm_data.items:
                        llm_records.append(
                            PriceRecord(
                                product_raw=item.product_raw,
                                variety=item.variety,
                                actor_level=item.actor_level,
                                location_raw=item.location_raw,
                                period_start=p_start,
                                period_end=p_end,
                                published_at=artifact.published_at,
                                price_raw=item.price_raw,
                                price_value=item.price_value,
                                unit_raw="kg",
                                currency_raw="MGA",
                                missing_code=item.missing_code,
                                extraction_method="llm_verified",
                                evidence={"page": p_idx, "text": item.evidence_text},
                                confidence=0.80,
                            )
                        )
                except Exception as e:
                    # Log issue if LLM replay or API fails on this page
                    issues.append(
                        {
                            "kind": "llm_extraction_error",
                            "page": p_idx,
                            "error": str(e),
                        }
                    )

        # 4. Reconciliation
        final_records: Sequence[RecordBase]
        if llm_records:
            reconciled = reconcile_records(
                source_id=self.source_id,
                deterministic_records=det_records,
                llm_records=llm_records,
                page_texts=page_texts,
                source_record_id=artifact.source_record_id,
            )
            final_records = reconciled.accepted_records
            for rev in reconciled.review_items:
                issues.append(
                    {
                        "kind": rev.kind,
                        "payload": rev.payload,
                    }
                )
        else:
            final_records = det_records

        return ParseResult(
            records=final_records,
            issues=issues,
            parser_version=self.parser_version,
        )

    def _parse_variety_table(
        self,
        table: list[list[Any]],
        actor_level: str,
        p_idx: int,
        p_start: date,
        p_end: date,
        artifact: RawArtifact,
        out_records: list[RecordBase],
    ) -> None:
        """Parse multi-variety table (wholesale or retail)."""
        header_row = [_clean_cell(c) for c in table[0]]

        # Map each column index to (product_raw, variety)
        col_specs: dict[int, tuple[str, str | None]] = {}
        for col_idx in range(1, len(header_row)):
            col_hdr = header_row[col_idx]
            col_lower = col_hdr.lower()
            if "vary gasy" in col_lower:
                col_specs[col_idx] = ("Riz blanc local (Vary gasy)", "Vary gasy")
            elif "makalioka" in col_lower:
                col_specs[col_idx] = ("Riz blanc local (Makalioka)", "Makalioka")
            elif "tsipala" in col_lower:
                col_specs[col_idx] = ("Riz blanc local (Tsipala)", "Tsipala")
            elif "import" in col_lower:
                col_specs[col_idx] = ("Riz importé (25% brisures)", "25% brisures")
            else:
                col_specs[col_idx] = (col_hdr or "Riz blanc", None)

        for row in table[1:]:
            if not row or not row[0]:
                continue
            loc_raw = _clean_cell(row[0])
            if not loc_raw:
                continue

            for col_idx in range(1, len(row)):
                if col_idx not in col_specs:
                    continue
                pr_raw = _clean_cell(row[col_idx])
                if not pr_raw:
                    continue

                prod_raw, var_name = col_specs[col_idx]

                is_missing = pr_raw.upper() in (
                    "ND",
                    "NA",
                    "-",
                    "N.D.",
                    "N.A.",
                    "",
                    "NONE",
                )
                missing_code = (
                    (pr_raw.upper() if pr_raw.upper() in ("ND", "NA") else "ND")
                    if is_missing
                    else None
                )

                price_val: float | None = None
                if not is_missing:
                    try:
                        clean_val = pr_raw.replace(" ", "").replace(",", ".")
                        price_val = float(clean_val)
                    except ValueError:
                        price_val = None

                evidence = {
                    "page": p_idx,
                    "text": f"{loc_raw} {pr_raw}",
                }

                out_records.append(
                    PriceRecord(
                        product_raw=prod_raw,
                        variety=var_name,
                        actor_level=actor_level,
                        location_raw=loc_raw,
                        period_start=p_start,
                        period_end=p_end,
                        published_at=artifact.published_at,
                        price_raw=pr_raw,
                        price_value=price_val,
                        unit_raw="kg",
                        currency_raw="MGA",
                        missing_code=missing_code,
                        extraction_method="deterministic",
                        evidence=evidence,
                        confidence=0.95,
                    )
                )
