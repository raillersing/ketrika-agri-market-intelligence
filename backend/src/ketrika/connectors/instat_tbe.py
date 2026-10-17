"""INSTAT Tableau de bord économique (TBE) connector (SPECS §5.5, R2.5, CC-R).

Ingests periodic economic conjuncture series (Real sector, Trade flows, Monetary situation,
and republished CPI indicators) published by the National Statistics Institute (INSTAT) Madagascar.

Key invariants enforced (R2.5):
1. Native frequencies preserved: quarterly and annual series remain quarterly/annual.
   NO artificial monthly splitting or replication into fake months.
2. Primary institution traceability preserved in metadata/evidence (INSTAT, DGD, BFM, JIRAMA).
3. Non-independent confirmation: republished NIPC is explicitly tagged with primary_source='instat_nipc'.
4. Multi-edition catalog discovery and openpyxl multi-sheet ingestion.
"""

from __future__ import annotations

import calendar
import io
import logging
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any, ClassVar

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from ketrika.connectors.base import (
    DiscoveredItem,
    ParseResult,
    RawArtifact,
    RunContext,
)
from ketrika.connectors.discovery import CatalogDiscoveryEngine
from ketrika.connectors.records import MacroRecord

logger = logging.getLogger(__name__)

INSTAT_TBE_CATALOG_URL = "https://www.instat.mg/statistiques/conjoncture-economique"


def _clean_text(val: Any) -> str:
    """Normalize string cell for matching."""
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
        .replace("'", " ")
        .replace("-", " ")
    )


def parse_period_and_frequency(period_raw: str) -> tuple[date, date, str]:
    """Parse period string into exact start_date, end_date and native frequency.

    Strictly refuses fake month replication:
    - Monthly: '2025-01' -> (2025-01-01, 2025-01-31, 'monthly')
    - Quarterly: '2025-T1' or 'T1 2025' -> (2025-01-01, 2025-03-31, 'quarterly')
    - Annual: '2025' -> (2025-01-01, 2025-12-31, 'annual')
    """
    s = str(period_raw).strip()

    # Pattern 1: Quarterly (e.g. 2025-T1, 2025T1, T1-2025, T1 2025)
    q_match = re.search(r"(\d{4})[-_\s]*[tT]([1-4])", s) or re.search(r"[tT]([1-4])[-_\s]*(\d{4})", s)
    if q_match:
        if len(q_match.group(1)) == 4:
            year = int(q_match.group(1))
            quarter = int(q_match.group(2))
        else:
            quarter = int(q_match.group(1))
            year = int(q_match.group(2))

        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3
        last_day = calendar.monthrange(year, end_month)[1]
        return date(year, start_month, 1), date(year, end_month, last_day), "quarterly"

    # Pattern 2: Monthly (e.g. 2025-01, 2025/01, 2025_01)
    m_match = re.search(r"(\d{4})[-_/](\d{1,2})", s)
    if m_match:
        year = int(m_match.group(1))
        month = int(m_match.group(2))
        if 1 <= month <= 12:
            last_day = calendar.monthrange(year, month)[1]
            return date(year, month, 1), date(year, month, last_day), "monthly"

    # Pattern 3: Annual (e.g. 2025)
    a_match = re.match(r"^(\d{4})$", s)
    if a_match:
        year = int(a_match.group(1))
        return date(year, 1, 1), date(year, 12, 31), "annual"

    raise ValueError(f"unrecognized_tbe_period_format: '{period_raw}'")


class Connector:
    """INSTAT Madagascar Tableau de bord économique (TBE) connector."""

    source_id: ClassVar[str] = "instat_tbe"
    source_family: ClassVar[str] = "madagascar_gov"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover TBE editions from landing catalog or recorded entries."""
        custom_url = ctx.metadata.get("catalog_url") if ctx.metadata else None
        target_url = custom_url or INSTAT_TBE_CATALOG_URL
        allow_loopback = ctx.metadata.get("allow_loopback", False) if ctx.metadata else False

        allowed_domains = ["instat.mg"]
        if allow_loopback:
            allowed_domains.extend(["localhost", "127.0.0.1"])

        engine = CatalogDiscoveryEngine(
            source_id=self.source_id,
            http_client=ctx.http_client,
            allowed_domains=allowed_domains,
            max_pages=5,
            allow_loopback=allow_loopback,
        )

        tbe_link_pattern = re.compile(
            r"/.*(?:tbe|tableau.*bord).*\.(?:xlsx|xls)$",
            re.IGNORECASE,
        )

        try:
            discovery_res = engine.discover_html_editions(
                start_url=target_url,
                link_pattern=tbe_link_pattern,
            )
            if discovery_res.editions:
                items: list[DiscoveredItem] = []
                for edition in discovery_res.editions:
                    items.append(
                        DiscoveredItem(
                            url=edition.url,
                            partition_key="tbe_national",
                            published_at=edition.published_at or datetime.now(UTC),
                            hints={"format": "xlsx", "edition_title": edition.title or ""},
                        )
                    )
                return items
        except Exception as exc:
            logger.warning("INSTAT TBE discovery failed (%s); falling back to default entrypoint", exc)

        return [
            DiscoveredItem(
                url=target_url,
                partition_key="tbe_national",
                published_at=datetime.now(UTC),
                hints={"fallback": "true", "format": "xlsx"},
            )
        ]

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch raw TBE file and store into Bronze layer."""
        return ctx.fetch_and_store(
            item,
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse multi-sheet Excel workbook and emit typed MacroRecord items."""
        raw_bytes = getattr(artifact, "content", None)
        if raw_bytes is None:
            if ctx.bronze_store is None:
                raise ValueError("Bronze store is required in RunContext when artifact has no direct content")
            raw_bytes = ctx.bronze_store.get(artifact.object_key)

        if not raw_bytes:
            return ParseResult(
                records=[],
                issues=[
                    {
                        "kind": "bronze_artifact_not_found",
                        "detail": f"No payload in bronze store for key {artifact.object_key}",
                    }
                ],
                parser_version=self.parser_version,
            )

        try:
            wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
        except Exception as exc:
            return ParseResult(
                records=[],
                issues=[{"kind": "xlsx_read_error", "detail": str(exc)}],
                parser_version=self.parser_version,
            )

        records: list[MacroRecord] = []

        # Step 1: Extract edition metadata from Summary sheet
        edition_num: int | None = None
        publication_date: date | None = None

        if "Sommaire & Sources" in wb.sheetnames:
            ws_meta = wb["Sommaire & Sources"]
            for row in ws_meta.iter_rows(values_only=True):
                for cell in row:
                    if cell:
                        txt = str(cell)
                        ed_match = re.search(r"EDITION\s+N[°oO]?\s*(\d+)", txt, re.IGNORECASE)
                        if ed_match:
                            edition_num = int(ed_match.group(1))
                        pub_match = re.search(r"publication\s*:\s*(\d{4}[-_]\d{2}[-_]\d{2})", txt, re.IGNORECASE)
                        if pub_match:
                            try:
                                publication_date = date.fromisoformat(pub_match.group(1).replace("_", "-"))
                            except ValueError:
                                pass

        published_at_dt = (
            datetime(publication_date.year, publication_date.month, publication_date.day, 12, 0, 0, tzinfo=UTC)
            if publication_date
            else artifact.published_at
        )
        fetched_at_dt = getattr(artifact, "fetched_at", None) or datetime.now(UTC)
        first_avail_dt = published_at_dt or fetched_at_dt

        # Step 2: Parse thematic sheets
        # Sheet: Secteur Réel
        if "Secteur Réel" in wb.sheetnames:
            records.extend(
                self._parse_real_sector(
                    wb["Secteur Réel"],
                    edition_num=edition_num,
                    published_at=published_at_dt,
                    first_available_at=first_avail_dt,
                )
            )

        # Sheet: Commerce Extérieur
        if "Commerce Extérieur" in wb.sheetnames:
            records.extend(
                self._parse_trade_sector(
                    wb["Commerce Extérieur"],
                    edition_num=edition_num,
                    published_at=published_at_dt,
                    first_available_at=first_avail_dt,
                )
            )

        # Sheet: Secteur Monétaire
        if "Secteur Monétaire" in wb.sheetnames:
            records.extend(
                self._parse_monetary_sector(
                    wb["Secteur Monétaire"],
                    edition_num=edition_num,
                    published_at=published_at_dt,
                    first_available_at=first_avail_dt,
                )
            )

        # Sheet: Prix Consommation
        if "Prix Consommation" in wb.sheetnames:
            records.extend(
                self._parse_cpi_sector(
                    wb["Prix Consommation"],
                    edition_num=edition_num,
                    published_at=published_at_dt,
                    first_available_at=first_avail_dt,
                )
            )

        logger.info(
            "INSTAT TBE parsed %d macro records from edition %s",
            len(records),
            edition_num,
        )

        return ParseResult(
            records=records,
            issues=[],
            parser_version=self.parser_version,
        )

    def _parse_real_sector(
        self,
        ws: Worksheet,
        edition_num: int | None,
        published_at: datetime | None,
        first_available_at: datetime,
    ) -> list[MacroRecord]:
        """Extract IPI, industrial electricity, cement and quarterly real GDP."""
        recs: list[MacroRecord] = []
        is_quarterly_section = False

        for row in ws.iter_rows(values_only=True):
            if not row or not row[0]:
                continue

            c0 = str(row[0]).strip()
            c0_clean = _clean_text(c0)

            if "pib reel" in c0_clean:
                is_quarterly_section = True
                continue
            if "indicateurs d activite" in c0_clean or ("tableau 1" in c0_clean and "pib" not in c0_clean):
                is_quarterly_section = False
                continue
            if "periode" in c0_clean:
                continue

            try:
                p_start, p_end, freq = parse_period_and_frequency(c0)
            except ValueError:
                continue

            if is_quarterly_section and freq == "quarterly":
                # Real GDP
                val = row[1] if len(row) > 1 else None
                if val is not None and isinstance(val, (int, float)):
                    recs.append(
                        MacroRecord(
                            indicator_code="GDP_REAL_MGA",
                            indicator_name="PIB Réel Trimestriel (Milliards MGA)",
                            frequency="quarterly",
                            unit="MGA_milliard",
                            geo_scope="national",
                            period_start=p_start,
                            period_end=p_end,
                            value=float(val),
                            value_raw=str(val),
                            vintage="final" if edition_num and edition_num >= 63 else "provisional",
                            observed_or_imputed="observed",
                            published_at=published_at,
                            first_available_at=first_available_at,
                            evidence={"primary_institution": "INSTAT"},
                        )
                    )
            elif not is_quarterly_section and freq == "monthly":
                # Col 1: IPI
                if len(row) > 1 and row[1] is not None and isinstance(row[1], (int, float)):
                    recs.append(
                        MacroRecord(
                            indicator_code="IPI_GLOBAL",
                            indicator_name="Indice de la Production Industrielle (Base 2015=100)",
                            frequency="monthly",
                            unit="index",
                            geo_scope="national",
                            period_start=p_start,
                            period_end=p_end,
                            value=float(row[1]),
                            value_raw=str(row[1]),
                            base_period="2015=100",
                            vintage="revised" if edition_num and edition_num >= 63 and p_start.year == 2026 and p_start.month <= 3 else "final",
                            observed_or_imputed="observed",
                            published_at=published_at,
                            first_available_at=first_available_at,
                            evidence={"primary_institution": "INSTAT"},
                        )
                    )
                # Col 2: Industrial electricity
                if len(row) > 2 and row[2] is not None and isinstance(row[2], (int, float)):
                    recs.append(
                        MacroRecord(
                            indicator_code="ELEC_IND_KWH",
                            indicator_name="Consommation Electricité Industrielle (MWh)",
                            frequency="monthly",
                            unit="MWh",
                            geo_scope="national",
                            period_start=p_start,
                            period_end=p_end,
                            value=float(row[2]),
                            value_raw=str(row[2]),
                            vintage="final",
                            observed_or_imputed="observed",
                            published_at=published_at,
                            first_available_at=first_available_at,
                            evidence={"primary_institution": "JIRAMA"},
                        )
                    )
                # Col 3: Cement
                if len(row) > 3 and row[3] is not None and isinstance(row[3], (int, float)):
                    recs.append(
                        MacroRecord(
                            indicator_code="CEMENT_CONSUMPTION_TONNES",
                            indicator_name="Consommation Ciment (Tonnes)",
                            frequency="monthly",
                            unit="tonnes",
                            geo_scope="national",
                            period_start=p_start,
                            period_end=p_end,
                            value=float(row[3]),
                            value_raw=str(row[3]),
                            vintage="final",
                            observed_or_imputed="observed",
                            published_at=published_at,
                            first_available_at=first_available_at,
                            evidence={"primary_institution": "Opérateurs/Douanes"},
                        )
                    )
        return recs

    def _parse_trade_sector(
        self,
        ws: Worksheet,
        edition_num: int | None,
        published_at: datetime | None,
        first_available_at: datetime,
    ) -> list[MacroRecord]:
        """Extract rice imports, total CIF imports, and FOB exports."""
        recs: list[MacroRecord] = []
        for row in ws.iter_rows(values_only=True):
            if not row or not row[0]:
                continue
            c0 = str(row[0]).strip()
            c0_clean = _clean_text(c0)
            if "tableau" in c0_clean or "statistiques du commerce" in c0_clean or "periode" in c0_clean:
                continue

            try:
                p_start, p_end, freq = parse_period_and_frequency(c0)
            except ValueError:
                continue

            if freq == "monthly":
                # Col 1: Rice imports (tonnes)
                if len(row) > 1 and row[1] is not None and isinstance(row[1], (int, float)):
                    recs.append(
                        MacroRecord(
                            indicator_code="RICE_IMPORTS_TONNES",
                            indicator_name="Importations Riz (Tonnes)",
                            frequency="monthly",
                            unit="tonnes",
                            geo_scope="national",
                            period_start=p_start,
                            period_end=p_end,
                            value=float(row[1]),
                            value_raw=str(row[1]),
                            vintage="final",
                            observed_or_imputed="observed",
                            published_at=published_at,
                            first_available_at=first_available_at,
                            evidence={"primary_institution": "Direction Générale des Douanes"},
                        )
                    )
                # Col 2: Total CIF imports (Millions MGA)
                if len(row) > 2 and row[2] is not None and isinstance(row[2], (int, float)):
                    recs.append(
                        MacroRecord(
                            indicator_code="IMPORTS_CIF_MGA",
                            indicator_name="Importations CAF Totales (Millions MGA)",
                            frequency="monthly",
                            unit="MGA_million",
                            geo_scope="national",
                            period_start=p_start,
                            period_end=p_end,
                            value=float(row[2]),
                            value_raw=str(row[2]),
                            vintage="final",
                            observed_or_imputed="observed",
                            published_at=published_at,
                            first_available_at=first_available_at,
                            evidence={"primary_institution": "Direction Générale des Douanes"},
                        )
                    )
                # Col 3: Total FOB exports (Millions MGA)
                if len(row) > 3 and row[3] is not None and isinstance(row[3], (int, float)):
                    recs.append(
                        MacroRecord(
                            indicator_code="EXPORTS_FOB_MGA",
                            indicator_name="Exportations FOB Totales (Millions MGA)",
                            frequency="monthly",
                            unit="MGA_million",
                            geo_scope="national",
                            period_start=p_start,
                            period_end=p_end,
                            value=float(row[3]),
                            value_raw=str(row[3]),
                            vintage="final",
                            observed_or_imputed="observed",
                            published_at=published_at,
                            first_available_at=first_available_at,
                            evidence={"primary_institution": "Direction Générale des Douanes"},
                        )
                    )
        return recs

    def _parse_monetary_sector(
        self,
        ws: Worksheet,
        edition_num: int | None,
        published_at: datetime | None,
        first_available_at: datetime,
    ) -> list[MacroRecord]:
        """Extract M3 money supply and exchange rate."""
        recs: list[MacroRecord] = []
        for row in ws.iter_rows(values_only=True):
            if not row or not row[0]:
                continue
            c0 = str(row[0]).strip()
            c0_clean = _clean_text(c0)
            if "tableau" in c0_clean or "situation monetaire" in c0_clean or "periode" in c0_clean:
                continue

            try:
                p_start, p_end, freq = parse_period_and_frequency(c0)
            except ValueError:
                continue

            if freq == "monthly":
                # Col 1: M3 (Milliards MGA)
                if len(row) > 1 and row[1] is not None and isinstance(row[1], (int, float)):
                    recs.append(
                        MacroRecord(
                            indicator_code="MONEY_SUPPLY_M3_MGA",
                            indicator_name="Masse Monétaire M3 (Milliards MGA)",
                            frequency="monthly",
                            unit="MGA_milliard",
                            geo_scope="national",
                            period_start=p_start,
                            period_end=p_end,
                            value=float(row[1]),
                            value_raw=str(row[1]),
                            vintage="final",
                            observed_or_imputed="observed",
                            published_at=published_at,
                            first_available_at=first_available_at,
                            evidence={"primary_institution": "Banky Foiben'i Madagasikara"},
                        )
                    )
                # Col 2: Exchange rate USD (MGA)
                if len(row) > 2 and row[2] is not None and isinstance(row[2], (int, float)):
                    recs.append(
                        MacroRecord(
                            indicator_code="EXCHANGE_RATE_MGA_USD",
                            indicator_name="Cours de Change USD Moyen (MGA)",
                            frequency="monthly",
                            unit="MGA",
                            geo_scope="national",
                            period_start=p_start,
                            period_end=p_end,
                            value=float(row[2]),
                            value_raw=str(row[2]),
                            vintage="final",
                            observed_or_imputed="observed",
                            published_at=published_at,
                            first_available_at=first_available_at,
                            evidence={"primary_institution": "Banky Foiben'i Madagasikara"},
                        )
                    )
        return recs

    def _parse_cpi_sector(
        self,
        ws: Worksheet,
        edition_num: int | None,
        published_at: datetime | None,
        first_available_at: datetime,
    ) -> list[MacroRecord]:
        """Extract republished food CPI series (traceable to primary source instat_nipc)."""
        recs: list[MacroRecord] = []
        for row in ws.iter_rows(values_only=True):
            if not row or not row[0]:
                continue
            c0 = str(row[0]).strip()
            c0_clean = _clean_text(c0)
            if "tableau" in c0_clean or "indice des prix" in c0_clean or "periode" in c0_clean:
                continue

            try:
                p_start, p_end, freq = parse_period_and_frequency(c0)
            except ValueError:
                continue

            if freq == "monthly" and len(row) > 1 and row[1] is not None and isinstance(row[1], (int, float)):
                recs.append(
                    MacroRecord(
                        indicator_code="CPI_TBE_FOOD",
                        indicator_name="NIPC Indice Alimentaire Réédité (Base 2016)",
                        frequency="monthly",
                        unit="index",
                        geo_scope="national",
                        period_start=p_start,
                        period_end=p_end,
                        value=float(row[1]),
                        value_raw=str(row[1]),
                        base_period="2016=100",
                        vintage="final",
                        observed_or_imputed="observed",
                        published_at=published_at,
                        first_available_at=first_available_at,
                        evidence={
                            "primary_source": "instat_nipc",
                            "primary_institution": "INSTAT Madagascar - Service des Prix (NIPC Base 2016)",
                        },
                    )
                )
        return recs


InstatTbeConnector = Connector
