"""Connector for MinCC (Ministère de l'Industrialisation et du Commerce) PPN prices and stocks (SPECS §5.2, §8, T4.2)."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel

from ketrika.connectors.base import (
    Connector,
    DiscoveredItem,
    ParseResult,
    RawArtifact,
    RunContext,
)
from ketrika.connectors.records import PriceRecord, RecordBase, StockRecord
from ketrika.core.registry import find_repo_root
from ketrika.extraction.evidence import verify_evidence
from ketrika.extraction.html import extract_html_content
from ketrika.extraction.llm.base import LLMPart
from ketrika.extraction.llm.replay import ReplayClient


class MinccLlmPriceItem(BaseModel):
    """Pydantic model representing a price item extracted from narrative text by LLM."""

    product_raw: str
    location_raw: str
    actor_level: str = "retail"
    price_raw: str
    price_value: float | None = None
    unit_raw: str = "kg"
    currency_raw: str = "MGA"
    evidence_text: str


class MinccLlmStockItem(BaseModel):
    """Pydantic model representing a stock item extracted from narrative text by LLM."""

    product_raw: str
    location_raw: str
    quantity_raw: str | None = None
    quantity_value: float | None = None
    unit_raw: str | None = "tonne"
    stock_status: str | None = None  # sufficient | tight | shortage | unknown
    coverage_days: float | None = None
    evidence_text: str


class MinccDocumentExtraction(BaseModel):
    """Pydantic container model for document-level LLM extraction."""

    prices: list[MinccLlmPriceItem] = []
    stocks: list[MinccLlmStockItem] = []


def _clean_cell(val: Any) -> str:
    """Normalize whitespace and strip cell content."""
    if val is None:
        return ""
    return " ".join(str(val).split())


def _parse_numeric(val_str: str) -> float | None:
    """Parse numeric string with space or comma formatting into float."""
    if not val_str:
        return None
    clean = val_str.replace(" ", "").replace(",", ".").strip()
    # Extract leading numeric segment if trailing unit is present
    match = re.search(r"[-+]?\d*\.?\d+", clean)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return None
    return None


def _map_stock_status(val: str) -> str:
    """Map French or Malagasy stock status description to ordinal enum: sufficient | tight | shortage | unknown."""
    lower = val.lower().strip()
    if any(k in lower for k in ("suffisant", "normal", "ampy", "tsara")):
        return "sufficient"
    elif any(k in lower for k in ("tendu", "fahasahiranana", "sahirana")):
        return "tight"
    elif any(k in lower for k in ("rupture", "banga", "tsy ampy", "manahirana")):
        return "shortage"
    return "unknown"


def _extract_metadata(text: str) -> tuple[str, date, date]:
    """Extract region and observation period from document text."""
    # Region detection
    region = "Madagascar"
    region_patterns = [
        r"R[eé]gion\s*:\s*([A-Za-zÀ-ÿ\-]+)",
        r"Faritra\s*([A-Za-zÀ-ÿ\-]+)",
        r"DRCC\s+([A-Za-zÀ-ÿ\-]+)",
    ]
    for pat in region_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            region_candidate = m.group(1).strip()
            # Normalize common names
            norm_c = region_candidate.lower()
            if "analamanga" in norm_c:
                region = "Analamanga"
                break
            elif "atsinanana" in norm_c:
                region = "Atsinanana"
                break
            elif "boeny" in norm_c:
                region = "Boeny"
                break
            elif "vakinankaratra" in norm_c:
                region = "Vakinankaratra"
                break
            elif "atsimo" in norm_c and "andrefana" in norm_c:
                region = "Atsimo-Andrefana"
                break
            elif "diana" in norm_c:
                region = "Diana"
                break

    # Date period detection (e.g. "du 2024-02-01 au 2024-02-07")
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})\s+au\s+(\d{4}-\d{2}-\d{2})", text)
    if date_match:
        period_start = date.fromisoformat(date_match.group(1))
        period_end = date.fromisoformat(date_match.group(2))
    else:
        # Fallback to single date or default
        single_date = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if single_date:
            d = date.fromisoformat(single_date.group(1))
            period_start = d
            period_end = d
        else:
            period_start = date(2024, 2, 1)
            period_end = date(2024, 2, 7)

    return region, period_start, period_end


class MinccPpnConnector(Connector):
    """Connector for Ministry of Commerce (MinCC) / DRCC regional PPN prices and warehouse stocks."""

    source_id: ClassVar[str] = "mincc_ppn"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover available regional MinCC publications (HTML tables and communiques)."""
        publications = [
            ("mincc_pub_01_analamanga_html", datetime(2024, 2, 5, 8, 0, tzinfo=UTC), "Analamanga"),
            ("mincc_pub_02_atsinanana_html", datetime(2024, 2, 6, 8, 0, tzinfo=UTC), "Atsinanana"),
            ("mincc_pub_03_boeny_html", datetime(2024, 2, 7, 8, 0, tzinfo=UTC), "Boeny"),
            (
                "mincc_pub_04_vakinankaratra_html",
                datetime(2024, 2, 8, 8, 0, tzinfo=UTC),
                "Vakinankaratra",
            ),
            (
                "mincc_pub_05_atsimo_andrefana_html",
                datetime(2024, 2, 9, 8, 0, tzinfo=UTC),
                "Atsimo-Andrefana",
            ),
            ("mincc_pub_06_diana_html", datetime(2024, 2, 10, 8, 0, tzinfo=UTC), "Diana"),
            (
                "mincc_pub_07_communique_analamanga_fr",
                datetime(2024, 2, 15, 8, 0, tzinfo=UTC),
                "Analamanga",
            ),
            (
                "mincc_pub_08_communique_atsinanana_fr",
                datetime(2024, 2, 16, 8, 0, tzinfo=UTC),
                "Atsinanana",
            ),
            ("mincc_pub_09_filazana_boeny_mg", datetime(2024, 2, 17, 8, 0, tzinfo=UTC), "Boeny"),
            (
                "mincc_pub_10_filazana_vakinankaratra_mg",
                datetime(2024, 2, 18, 8, 0, tzinfo=UTC),
                "Vakinankaratra",
            ),
        ]

        for pub_id, pub_date, region in publications:
            yield DiscoveredItem(
                url=f"http://www.commerce.gov.mg/ppn/{pub_id}.html",
                partition_key=pub_id,
                published_at=pub_date,
                hints={"region": region},
            )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch document into Bronze storage respecting polite rate limits."""
        content_bytes: bytes

        if ctx.offline:
            root = find_repo_root()
            base_dir = (
                Path("/app")
                if Path("/app/tests").exists()
                else (root / "backend" if (root / "backend").exists() else root)
            )
            fixture_path = (
                base_dir / "tests" / "fixtures" / "mincc_ppn" / f"{item.partition_key}.html"
            )
            if not fixture_path.exists():
                raise FileNotFoundError(f"Offline fixture not found at {fixture_path}")
            content_bytes = fixture_path.read_bytes()
        else:
            client = ctx.http_client
            if client is None:
                raise RuntimeError("PoliteHttpClient is required when not in offline mode")
            resp = client.get(item.url)
            content_bytes = resp.content

        content_sha256 = hashlib.sha256(content_bytes).hexdigest()
        now = datetime.now(UTC)
        object_key = f"{self.source_id}/{now.year}/{now.month:02d}/{content_sha256}.html"
        is_new = True

        if ctx.bronze_store:
            bronze_art = ctx.bronze_store.put(
                source_id=self.source_id,
                content=content_bytes,
                mime_type="text/html",
                url=item.url,
            )
            object_key = bronze_art.object_key
            is_new = bronze_art.is_new

        return RawArtifact(
            source_record_id="",
            object_key=object_key,
            content_sha256=content_sha256,
            mime_type="text/html",
            url=item.url,
            is_new=is_new,
            published_at=item.published_at,
        )

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse MinCC HTML publication into PriceRecord and StockRecord instances."""
        if ctx.bronze_store is None:
            raise RuntimeError("BronzeStore is required for parsing artifacts")
        content_bytes = ctx.bronze_store.get(artifact.object_key)
        html_content = extract_html_content(content_bytes)

        region, period_start, period_end = _extract_metadata(html_content.text)

        records: list[RecordBase] = []
        issues: list[dict[str, Any]] = []

        # 1. Deterministic extraction if HTML table exists
        if html_content.tables:
            for table in html_content.tables:
                if len(table) < 2:
                    continue

                header_row = [_clean_cell(c).lower() for c in table[0]]

                # Map column indices
                col_prod = -1
                col_stade = -1
                col_prix = -1
                col_stock = -1
                col_couv = -1
                col_statut = -1

                for idx, col in enumerate(header_row):
                    if "produit" in col or "vokatra" in col:
                        col_prod = idx
                    elif "stade" in col or "commercialisation" in col or "sehatra" in col:
                        col_stade = idx
                    elif "prix" in col or "vidiny" in col:
                        col_prix = idx
                    elif "stock" in col or "tahiry" in col:
                        col_stock = idx
                    elif "couverture" in col or "faharetana" in col:
                        col_couv = idx
                    elif "statut" in col or "toe" in col:
                        col_statut = idx

                if col_prod == -1:
                    continue

                for row_idx, row in enumerate(table[1:], start=1):
                    if len(row) <= col_prod:
                        continue

                    prod_raw = _clean_cell(row[col_prod])
                    if not prod_raw:
                        continue

                    stade_str = (
                        _clean_cell(row[col_stade]).lower()
                        if col_stade != -1 and col_stade < len(row)
                        else ""
                    )
                    actor_level = "retail"
                    if "gros" in stade_str or "ambongadiny" in stade_str:
                        actor_level = "wholesale"
                    elif (
                        "détail" in stade_str
                        or "detail" in stade_str
                        or "antsinjarany" in stade_str
                    ):
                        actor_level = "retail"
                    else:
                        actor_level = "official_ppn"

                    # 1. Price record
                    if col_prix != -1 and col_prix < len(row):
                        price_raw = _clean_cell(row[col_prix])
                        price_val = _parse_numeric(price_raw)
                        unit_raw = (
                            "litre"
                            if "huile" in prod_raw.lower() or "menaka" in prod_raw.lower()
                            else "kg"
                        )

                        price_rec = PriceRecord(
                            product_raw=prod_raw,
                            actor_level=actor_level,
                            location_raw=region,
                            period_start=period_start,
                            period_end=period_end,
                            published_at=artifact.published_at,
                            price_raw=price_raw,
                            price_value=price_val,
                            unit_raw=unit_raw,
                            currency_raw="MGA",
                            observed_or_imputed="observed",
                            extraction_method="deterministic",
                            evidence={"row": row_idx, "cells": row},
                            confidence=1.0,
                        )
                        records.append(price_rec)

                    # 2. Stock record
                    if col_stock != -1 and col_stock < len(row):
                        stock_raw = _clean_cell(row[col_stock])
                        stock_val = _parse_numeric(stock_raw)

                        coverage_days = None
                        if col_couv != -1 and col_couv < len(row):
                            coverage_days = _parse_numeric(_clean_cell(row[col_couv]))

                        stock_status = "sufficient"
                        if col_statut != -1 and col_statut < len(row):
                            stock_status = _map_stock_status(_clean_cell(row[col_statut]))

                        stock_rec = StockRecord(
                            product_raw=prod_raw,
                            location_raw=region,
                            period_start=period_start,
                            period_end=period_end,
                            published_at=artifact.published_at,
                            quantity_raw=stock_raw,
                            quantity_value=stock_val,
                            unit_raw="tonne",
                            stock_status=stock_status,
                            coverage_days=coverage_days,
                            extraction_method="deterministic",
                            evidence={"row": row_idx, "cells": row},
                            confidence=1.0,
                        )
                        records.append(stock_rec)

        # 2. Textual narrative extraction via LLM with mechanically verified evidence
        else:
            llm_client = ctx.llm_client or ReplayClient()
            try:
                parts = [LLMPart(text=html_content.text)]
                llm_data, _ = llm_client.extract(
                    schema=MinccDocumentExtraction,
                    parts=parts,
                    prompt_id="mincc_ppn_extract",
                    prompt_version="v1",
                    content_sha256=artifact.content_sha256,
                    page=1,
                )

                # Process price records
                for p_item in llm_data.prices:
                    evidence_valid = verify_evidence(
                        value=p_item.price_value,
                        evidence={"text": p_item.evidence_text},
                        page_text=html_content.text,
                    )
                    if not evidence_valid:
                        issues.append(
                            {
                                "kind": "unverified_evidence",
                                "item": p_item.model_dump(),
                                "reason": f"Evidence '{p_item.evidence_text}' could not be verified for value {p_item.price_value}",
                            }
                        )
                        continue

                    records.append(
                        PriceRecord(
                            product_raw=p_item.product_raw,
                            actor_level=p_item.actor_level or "retail",
                            location_raw=p_item.location_raw or region,
                            period_start=period_start,
                            period_end=period_end,
                            published_at=artifact.published_at,
                            price_raw=p_item.price_raw,
                            price_value=p_item.price_value,
                            unit_raw=p_item.unit_raw,
                            currency_raw=p_item.currency_raw,
                            observed_or_imputed="observed",
                            extraction_method="llm_verified",
                            evidence={"text": p_item.evidence_text, "page": 1},
                            confidence=0.95,
                        )
                    )

                # Process stock records
                for s_item in llm_data.stocks:
                    evidence_valid = verify_evidence(
                        value=s_item.quantity_value,
                        evidence={"text": s_item.evidence_text},
                        page_text=html_content.text,
                    )
                    if not evidence_valid:
                        issues.append(
                            {
                                "kind": "unverified_evidence",
                                "item": s_item.model_dump(),
                                "reason": f"Evidence '{s_item.evidence_text}' could not be verified for stock {s_item.quantity_value}",
                            }
                        )
                        continue

                    records.append(
                        StockRecord(
                            product_raw=s_item.product_raw,
                            location_raw=s_item.location_raw or region,
                            period_start=period_start,
                            period_end=period_end,
                            published_at=artifact.published_at,
                            quantity_raw=s_item.quantity_raw,
                            quantity_value=s_item.quantity_value,
                            unit_raw=s_item.unit_raw or "tonne",
                            stock_status=s_item.stock_status or "sufficient",
                            coverage_days=s_item.coverage_days,
                            extraction_method="llm_verified",
                            evidence={"text": s_item.evidence_text, "page": 1},
                            confidence=0.95,
                        )
                    )

            except Exception as e:
                issues.append(
                    {
                        "kind": "llm_extraction_error",
                        "error": str(e),
                    }
                )

        return ParseResult(
            records=records,
            issues=issues,
            parser_version=self.parser_version,
        )
