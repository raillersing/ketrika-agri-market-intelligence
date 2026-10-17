"""Office Malgache des Hydrocarbures (OMH) public fuel price connector (R2.7).

Ingests official regulated fuel price ceilings (Gazole, Super 95, Pétrole lampant)
and regulatory acts (décrets, arrêtés interministériels) from the OMH.
Strictly separates effective application dates (period_start) from publication dates,
tracks administered ceiling prices vs pump observations, and ensures full immutability.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any, ClassVar

from selectolax.lexbor import LexborHTMLParser

from ketrika.connectors.base import (
    DiscoveredItem,
    ParseResult,
    RawArtifact,
    RunContext,
)
from ketrika.connectors.discovery import CatalogDiscoveryEngine
from ketrika.connectors.records import MacroRecord

logger = logging.getLogger(__name__)

OMH_CATALOG_URL = "https://www.omh.mg/prix-des-carburants"

FUEL_INDICATOR_MAP = {
    "DIESEL": {
        "code": "FUEL_DIESEL_CEILING_MGA",
        "name": "Prix Plafond Réglementé Gazole (MGA/L)",
    },
    "GASOIL": {
        "code": "FUEL_DIESEL_CEILING_MGA",
        "name": "Prix Plafond Réglementé Gazole (MGA/L)",
    },
    "SUPER95": {
        "code": "FUEL_SUPER95_CEILING_MGA",
        "name": "Prix Plafond Réglementé Super 95 (MGA/L)",
    },
    "SUPER": {
        "code": "FUEL_SUPER95_CEILING_MGA",
        "name": "Prix Plafond Réglementé Super 95 (MGA/L)",
    },
    "KEROSENE": {
        "code": "FUEL_KEROSENE_CEILING_MGA",
        "name": "Prix Plafond Réglementé Pétrole Lampant (MGA/L)",
    },
    "PETROLE": {
        "code": "FUEL_KEROSENE_CEILING_MGA",
        "name": "Prix Plafond Réglementé Pétrole Lampant (MGA/L)",
    },
}

FRENCH_MONTHS = {
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


def clean_fuel_price(val: Any) -> float:
    """Parse numeric price string into float."""
    if val is None:
        raise ValueError("Cannot parse None as fuel price")
    if isinstance(val, (int, float)):
        return float(val)
    txt = str(val).strip().replace("\xa0", " ").replace(" ", "").replace(",", ".")
    # Strip leading '+'
    if txt.startswith("+"):
        txt = txt[1:]
    return float(txt)


def parse_french_date_text(text: str) -> date | None:
    """Extract calendar date from French text like '1er Juin 2026', '30 Mai 2026', or ISO '2026-06-01'."""
    # Match ISO YYYY-MM-DD
    iso_match = re.search(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            pass

    # Match DD/MM/YYYY
    dmy_match = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b", text)
    if dmy_match:
        try:
            return date(int(dmy_match.group(3)), int(dmy_match.group(2)), int(dmy_match.group(1)))
        except ValueError:
            pass

    # Match "1er Month YYYY" or "DD Month YYYY"
    month_pattern = "|".join(FRENCH_MONTHS.keys())
    named_match = re.search(
        rf"\b(\d{{1,2}}|1er)\s+({month_pattern})\s+(\d{{4}})\b",
        text,
        re.IGNORECASE,
    )
    if named_match:
        d_raw = named_match.group(1).lower()
        d = 1 if d_raw in ("1er", "1") else int(d_raw)
        m_name = named_match.group(2).lower()
        m = FRENCH_MONTHS.get(m_name, 1)
        y = int(named_match.group(3))
        try:
            return date(y, m, d)
        except ValueError:
            pass

    return None


class Connector:
    """Connector for Office Malgache des Hydrocarbures (OMH) public fuel price data."""

    source_id: ClassVar[str] = "omh_public"
    source_family: ClassVar[str] = "omh"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover OMH fuel price official bulletins or CSV datasets."""
        custom_url = ctx.metadata.get("catalog_url") if ctx.metadata else None
        target_url = custom_url or OMH_CATALOG_URL
        allow_loopback = ctx.metadata.get("allow_loopback", False) if ctx.metadata else False

        allowed_domains = ["omh.mg"]
        if allow_loopback:
            allowed_domains.extend(["localhost", "127.0.0.1"])

        engine = CatalogDiscoveryEngine(
            source_id=self.source_id,
            http_client=ctx.http_client,
            allowed_domains=allowed_domains,
            max_pages=5,
            allow_loopback=allow_loopback,
        )

        omh_link_pattern = re.compile(
            r"/.*(?:prix.*carburant|bareme|communique|hydrocarbure).*\.(?:csv|xlsx|xls|html|pdf)$",
            re.IGNORECASE,
        )

        try:
            discovery_res = engine.discover_html_editions(
                start_url=target_url,
                link_pattern=omh_link_pattern,
            )
            if discovery_res.editions:
                items: list[DiscoveredItem] = []
                for edition in discovery_res.editions:
                    fmt = (
                        "csv"
                        if edition.url.endswith(".csv")
                        else ("xlsx" if edition.url.endswith((".xlsx", ".xls")) else "html")
                    )
                    items.append(
                        DiscoveredItem(
                            url=edition.url,
                            partition_key="omh_prices",
                            published_at=edition.published_at or datetime.now(UTC),
                            hints={"format": fmt, "edition_title": edition.title or ""},
                        )
                    )
                return items
        except Exception as exc:
            logger.warning("OMH discovery failed (%s); falling back to default entrypoint", exc)

        return [
            DiscoveredItem(
                url=target_url,
                partition_key="omh_prices",
                published_at=datetime.now(UTC),
                hints={"fallback": "true", "format": "html"},
            )
        ]

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch raw artifact and store into Bronze layer."""
        fmt = item.hints.get("format", "csv") if item.hints else "csv"
        mime = (
            "text/csv"
            if fmt == "csv"
            else (
                "text/html"
                if fmt == "html"
                else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        )
        return ctx.fetch_and_store(item, mime_type=mime)

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse OMH fuel price document and emit typed MacroRecord instances."""
        raw_bytes = getattr(artifact, "content", None)
        if raw_bytes is None:
            if ctx.bronze_store is None:
                raise ValueError(
                    "Bronze store is required in RunContext when artifact has no direct content"
                )
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

        published_at_dt = artifact.published_at or datetime.now(UTC)
        fetched_at_dt = getattr(artifact, "fetched_at", None) or datetime.now(UTC)
        first_avail_dt = published_at_dt or fetched_at_dt

        url_lower = artifact.url.lower()
        mime_lower = (artifact.mime_type or "").lower()

        try:
            if "csv" in mime_lower or url_lower.endswith(".csv"):
                records = self._parse_csv(raw_bytes, published_at_dt, first_avail_dt)
            elif "html" in mime_lower or url_lower.endswith((".html", ".htm")):
                records = self._parse_html(raw_bytes, published_at_dt, first_avail_dt)
            else:
                try:
                    records = self._parse_csv(raw_bytes, published_at_dt, first_avail_dt)
                except Exception:
                    records = self._parse_html(raw_bytes, published_at_dt, first_avail_dt)
        except Exception as exc:
            return ParseResult(
                records=[],
                issues=[{"kind": "parse_error", "detail": str(exc)}],
                parser_version=self.parser_version,
            )

        logger.info("OMH connector parsed %d regulated fuel price records", len(records))

        return ParseResult(
            records=records,
            issues=[],
            parser_version=self.parser_version,
        )

    def _parse_csv(
        self,
        raw_bytes: bytes,
        published_at: datetime,
        first_available_at: datetime,
    ) -> list[MacroRecord]:
        """Parse official fuel ceiling prices CSV."""
        try:
            text_content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text_content = raw_bytes.decode("latin1", errors="replace")

        records: list[MacroRecord] = []
        reader = csv.reader(io.StringIO(text_content))

        header_idx: dict[str, int] = {}
        for row in reader:
            if not row or not any(row):
                continue
            c0 = row[0].strip()
            if c0.startswith("#"):
                continue

            if not header_idx:
                row_clean = [col.strip().lower().replace(" ", "_") for col in row]
                if any(x in row_clean for x in ["date_effet", "produit", "prix_plafond"]):
                    for idx, col in enumerate(row_clean):
                        header_idx[col] = idx
                    continue

            # Data row
            d_effet_str = (
                row[header_idx["date_effet"]].strip()
                if "date_effet" in header_idx and len(row) > header_idx["date_effet"]
                else ""
            )
            if not d_effet_str:
                continue

            try:
                effective_date = date.fromisoformat(d_effet_str)
            except ValueError:
                parsed_d = parse_french_date_text(d_effet_str)
                if not parsed_d:
                    continue
                effective_date = parsed_d

            # Publication date (may be distinct from effective date)
            pub_date = effective_date
            if "date_publication" in header_idx and len(row) > header_idx["date_publication"]:
                pub_str = row[header_idx["date_publication"]].strip()
                if pub_str:
                    try:
                        pub_date = date.fromisoformat(pub_str)
                    except ValueError:
                        parsed_pub = parse_french_date_text(pub_str)
                        if parsed_pub:
                            pub_date = parsed_pub

            # Regulatory act
            act_ref = (
                row[header_idx["acte_reglementaire"]].strip()
                if "acte_reglementaire" in header_idx
                and len(row) > header_idx["acte_reglementaire"]
                else "Arrêté Officiel OMH"
            )

            # Product
            prod_raw = (
                row[header_idx["produit"]].strip().upper()
                if "produit" in header_idx and len(row) > header_idx["produit"]
                else ""
            )
            ind_info = FUEL_INDICATOR_MAP.get(prod_raw)
            if not ind_info:
                continue

            # Prices: prix_plafond and former price
            prix_plafond_str = (
                row[header_idx["prix_plafond"]].strip()
                if "prix_plafond" in header_idx and len(row) > header_idx["prix_plafond"]
                else ""
            )
            if not prix_plafond_str:
                continue

            try:
                num_plafond = clean_fuel_price(prix_plafond_str)
            except ValueError:
                continue

            former_price: float | None = None
            if "prix_ancien" in header_idx and len(row) > header_idx["prix_ancien"]:
                try:
                    former_price = clean_fuel_price(row[header_idx["prix_ancien"]].strip())
                except ValueError:
                    former_price = None

            # Calculate conservative first availability
            pub_dt = datetime.combine(pub_date, datetime.min.time(), tzinfo=UTC)
            avail_dt = max(pub_dt, first_available_at)

            evidence_dict: dict[str, Any] = {
                "primary_institution": "Office Malgache des Hydrocarbures",
                "regulatory_act": act_ref,
                "is_administered": True,
                "rate_type": "ceiling",
                "product": prod_raw,
                "effective_date": effective_date.isoformat(),
                "published_date": pub_date.isoformat(),
            }
            if former_price is not None:
                evidence_dict["former_price"] = former_price
                evidence_dict["price_change"] = num_plafond - former_price

            records.append(
                MacroRecord(
                    indicator_code=ind_info["code"],
                    indicator_name=ind_info["name"],
                    frequency="event",
                    unit="MGA/L",
                    geo_scope="national",
                    period_start=effective_date,
                    period_end=effective_date,
                    value=num_plafond,
                    value_raw=str(prix_plafond_str),
                    vintage="final",
                    observed_or_imputed="observed",
                    published_at=pub_dt,
                    first_available_at=avail_dt,
                    evidence=evidence_dict,
                )
            )

        return records

    def _parse_html(
        self,
        raw_bytes: bytes,
        published_at: datetime,
        first_available_at: datetime,
    ) -> list[MacroRecord]:
        """Parse official OMH HTML communique table."""
        try:
            html_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            html_text = raw_bytes.decode("latin1", errors="replace")

        parser = LexborHTMLParser(html_text)
        records: list[MacroRecord] = []

        # Extract effective date
        app_node = parser.css_first(".date-application, .date-effet")
        if not app_node:
            for p in parser.css("p, h2, h3"):
                txt = p.text().lower()
                if "application" in txt or "effet" in txt or "vigueur" in txt:
                    app_node = p
                    break

        effective_date: date | None = None
        if app_node and app_node.text():
            effective_date = parse_french_date_text(app_node.text())

        if not effective_date:
            effective_date = published_at.date()

        # Extract publication date
        pub_node = parser.css_first(".date-publication, .date-signature")
        if not pub_node:
            for p in parser.css("p"):
                txt = p.text().lower()
                if "publication" in txt or "antananarivo, le" in txt or "signé" in txt:
                    pub_node = p
                    break

        pub_date: date = effective_date
        if pub_node and pub_node.text():
            parsed_pub = parse_french_date_text(pub_node.text())
            if parsed_pub:
                pub_date = parsed_pub

        # Extract regulatory act reference
        act_node = parser.css_first(".reference-acte, .arrete, .decret")
        if not act_node:
            for p in parser.css("p, h1, h2"):
                txt = p.text().lower()
                if "arrêté" in txt or "decret" in txt or "décret" in txt:
                    act_node = p
                    break

        act_ref = (
            act_node.text().strip() if act_node and act_node.text() else "Communiqué Officiel OMH"
        )

        pub_dt = datetime.combine(pub_date, datetime.min.time(), tzinfo=UTC)
        avail_dt = max(pub_dt, first_available_at)

        # Parse table rows
        rows = parser.css("table tr")
        for tr in rows:
            tds = tr.css("td")
            if len(tds) < 3:
                continue

            prod_label = tds[0].text().strip().lower()
            ind_info: dict[str, str] | None = None

            if "gazole" in prod_label or "gasoil" in prod_label:
                ind_info = FUEL_INDICATOR_MAP["DIESEL"]
            elif "super" in prod_label or "sp95" in prod_label:
                ind_info = FUEL_INDICATOR_MAP["SUPER95"]
            elif "petrole" in prod_label or "pétrole" in prod_label:
                ind_info = FUEL_INDICATOR_MAP["KEROSENE"]

            if not ind_info:
                continue

            # Expected columns: Carburant | Ancien Prix | Nouveau Prix | Variation
            former_str = tds[1].text().strip()
            new_str = tds[2].text().strip()

            try:
                new_price = clean_fuel_price(new_str)
            except ValueError:
                continue

            try:
                former_price = clean_fuel_price(former_str)
            except ValueError:
                former_price = None

            evidence_dict: dict[str, Any] = {
                "primary_institution": "Office Malgache des Hydrocarbures",
                "regulatory_act": act_ref,
                "is_administered": True,
                "rate_type": "ceiling",
                "product_label": tds[0].text().strip(),
                "effective_date": effective_date.isoformat(),
                "published_date": pub_date.isoformat(),
            }
            if former_price is not None:
                evidence_dict["former_price"] = former_price
                evidence_dict["price_change"] = new_price - former_price

            records.append(
                MacroRecord(
                    indicator_code=ind_info["code"],
                    indicator_name=ind_info["name"],
                    frequency="event",
                    unit="MGA/L",
                    geo_scope="national",
                    period_start=effective_date,
                    period_end=effective_date,
                    value=new_price,
                    value_raw=new_str,
                    vintage="final",
                    observed_or_imputed="observed",
                    published_at=pub_dt,
                    first_available_at=avail_dt,
                    evidence=evidence_dict,
                )
            )

        return records


OmhPublicConnector = Connector
