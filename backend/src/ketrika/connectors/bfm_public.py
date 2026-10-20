"""Banky Foiben'i Madagasikara (BFM) public exchange rate and monetary connector (R2.6).

Ingests official daily reference exchange rates from the Marché Interbancaire de Devises (MID)
published by Banky Foiben'i Madagasikara (Banque Centrale de Madagascar).
Strictly preserves native daily frequency on business days without silent interpolation of
weekends or holidays, separates buying/selling/mid rates, and documents proven inverse rates.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime, time
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

BFM_CATALOG_URL = "https://www.banky-foibe.mg/cours-de-change"

SUPPORTED_CURRENCIES = {
    "USD": "USD/MGA",
    "EUR": "EUR/MGA",
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


def clean_rate_number(val: Any) -> float:
    """Parse numeric string with space thousand separator and comma decimal into float."""
    if val is None:
        raise ValueError("Cannot parse None as rate number")
    if isinstance(val, (int, float)):
        return float(val)
    txt = str(val).strip().replace("\xa0", " ").replace(" ", "").replace(",", ".")
    return float(txt)


def compute_inverse_exchange_rate(rate: float) -> float:
    """Compute verified inverse exchange rate (e.g. 1 USD = X MGA => 1 MGA = 1/X USD)."""
    if rate <= 0:
        raise ValueError(f"Exchange rate must be positive, got {rate}")
    return 1.0 / rate


def is_business_trading_day(d: date) -> bool:
    """Check if date is an official trading day (Monday through Friday, weekday < 5)."""
    return d.weekday() < 5


def parse_french_date_text(text: str) -> date | None:
    """Extract calendar date from French text like '18 Mai 2026' or ISO '2026-05-18'."""
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

    # Match "DD Month YYYY"
    month_pattern = "|".join(FRENCH_MONTHS.keys())
    named_match = re.search(
        rf"\b(\d{{1,2}})\s+({month_pattern})\s+(\d{{4}})\b",
        text,
        re.IGNORECASE,
    )
    if named_match:
        d = int(named_match.group(1))
        m_name = named_match.group(2).lower()
        m = FRENCH_MONTHS.get(m_name, 1)
        y = int(named_match.group(3))
        try:
            return date(y, m, d)
        except ValueError:
            pass

    return None


class Connector:
    """Connector for Banky Foiben'i Madagasikara (BFM) public exchange rate data."""

    source_id: ClassVar[str] = "bfm_public"
    source_family: ClassVar[str] = "bfm"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover BFM exchange rate daily bulletins or CSV datasets."""
        custom_url = ctx.metadata.get("catalog_url") if ctx.metadata else None
        target_url = custom_url or BFM_CATALOG_URL
        allow_loopback = ctx.metadata.get("allow_loopback", False) if ctx.metadata else False

        allowed_domains = ["banky-foibe.mg"]
        if allow_loopback:
            allowed_domains.extend(["localhost", "127.0.0.1"])

        engine = CatalogDiscoveryEngine(
            source_id=self.source_id,
            http_client=ctx.http_client,
            allowed_domains=allowed_domains,
            max_pages=5,
            allow_loopback=allow_loopback,
        )

        bfm_link_pattern = re.compile(
            r"/.*(?:cours|change|taux|mid|devises).*\.(?:csv|xlsx|xls|html)$",
            re.IGNORECASE,
        )

        try:
            discovery_res = engine.discover_html_editions(
                start_url=target_url,
                link_pattern=bfm_link_pattern,
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
                            partition_key="bfm_rates",
                            published_at=edition.published_at or datetime.now(UTC),
                            hints={"format": fmt, "edition_title": edition.title or ""},
                        )
                    )
                return items
        except Exception as exc:
            logger.warning("BFM discovery failed (%s); falling back to default entrypoint", exc)

        return [
            DiscoveredItem(
                url=target_url,
                partition_key="bfm_rates",
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
        """Parse BFM exchange rate file and emit normalized MacroRecord instances."""
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

        # Content sniffing or mime type dispatch
        url_lower = artifact.url.lower()
        mime_lower = (artifact.mime_type or "").lower()

        try:
            if "csv" in mime_lower or url_lower.endswith(".csv"):
                records = self._parse_csv(raw_bytes, published_at_dt, first_avail_dt)
            elif "html" in mime_lower or url_lower.endswith((".html", ".htm")):
                records = self._parse_html(raw_bytes, published_at_dt, first_avail_dt)
            else:
                # Attempt CSV then HTML
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

        logger.info("BFM connector parsed %d macro exchange rate records", len(records))

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
        """Parse daily exchange rate CSV."""
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
            # Strip comments
            c0 = row[0].strip()
            if c0.startswith("#"):
                continue

            # Header detection
            if not header_idx:
                row_clean = [col.strip().lower().replace(" ", "_") for col in row]
                if any(x in row_clean for x in ["date", "devise", "cours_moyen"]):
                    for idx, col in enumerate(row_clean):
                        header_idx[col] = idx
                    continue

            # Data rows
            d_str = (
                row[header_idx["date"]].strip()
                if "date" in header_idx and len(row) > header_idx["date"]
                else ""
            )
            if not d_str:
                continue

            try:
                obs_date = date.fromisoformat(d_str)
            except ValueError:
                parsed_d = parse_french_date_text(d_str)
                if not parsed_d:
                    continue
                obs_date = parsed_d

            # Invariant: verify weekday (no silent weekend interpolation)
            if not is_business_trading_day(obs_date):
                logger.warning(
                    "BFM observation date %s is a weekend; skipping non-trading day", obs_date
                )
                continue

            curr = (
                row[header_idx["devise"]].strip().upper()
                if "devise" in header_idx and len(row) > header_idx["devise"]
                else ""
            )
            if curr not in SUPPORTED_CURRENCIES:
                continue

            # Extract rates: moyen, achat, vente
            moyen_val = (
                row[header_idx["cours_moyen"]].strip()
                if "cours_moyen" in header_idx and len(row) > header_idx["cours_moyen"]
                else None
            )
            achat_val = (
                row[header_idx["cours_achat"]].strip()
                if "cours_achat" in header_idx and len(row) > header_idx["cours_achat"]
                else None
            )
            vente_val = (
                row[header_idx["cours_vente"]].strip()
                if "cours_vente" in header_idx and len(row) > header_idx["cours_vente"]
                else None
            )

            # Compute conservative first availability (trading day at 17:00 UTC or next day 09:00 UTC)
            obs_dt = datetime.combine(obs_date, time(17, 0), tzinfo=UTC)
            avail_dt = max(obs_dt, first_available_at)

            # 1. Cours Moyen (Reference Mid Rate)
            if moyen_val:
                try:
                    num_moyen = clean_rate_number(moyen_val)
                    inv_moyen = compute_inverse_exchange_rate(num_moyen)
                    records.append(
                        MacroRecord(
                            indicator_code=f"EXCHANGE_RATE_{curr}_MGA",
                            indicator_name=f"Cours de Change {curr}/MGA Moyen",
                            frequency="daily",
                            unit="MGA",
                            geo_scope="national",
                            period_start=obs_date,
                            period_end=obs_date,
                            value=num_moyen,
                            value_raw=str(moyen_val),
                            vintage="final",
                            observed_or_imputed="observed",
                            published_at=published_at,
                            first_available_at=avail_dt,
                            evidence={
                                "primary_institution": "Banky Foiben'i Madagasikara",
                                "market": "MID",
                                "currency": curr,
                                "rate_type": "mid",
                                "inverse_rate_usd_per_mga": inv_moyen,
                            },
                        )
                    )
                except ValueError:
                    pass

            # 2. Cours Achat (Buying Rate)
            if achat_val:
                try:
                    num_achat = clean_rate_number(achat_val)
                    records.append(
                        MacroRecord(
                            indicator_code=f"EXCHANGE_RATE_{curr}_MGA_BUY",
                            indicator_name=f"Cours de Change {curr}/MGA Achat",
                            frequency="daily",
                            unit="MGA",
                            geo_scope="national",
                            period_start=obs_date,
                            period_end=obs_date,
                            value=num_achat,
                            value_raw=str(achat_val),
                            vintage="final",
                            observed_or_imputed="observed",
                            published_at=published_at,
                            first_available_at=avail_dt,
                            evidence={
                                "primary_institution": "Banky Foiben'i Madagasikara",
                                "market": "MID",
                                "currency": curr,
                                "rate_type": "buy",
                            },
                        )
                    )
                except ValueError:
                    pass

            # 3. Cours Vente (Selling Rate)
            if vente_val:
                try:
                    num_vente = clean_rate_number(vente_val)
                    records.append(
                        MacroRecord(
                            indicator_code=f"EXCHANGE_RATE_{curr}_MGA_SELL",
                            indicator_name=f"Cours de Change {curr}/MGA Vente",
                            frequency="daily",
                            unit="MGA",
                            geo_scope="national",
                            period_start=obs_date,
                            period_end=obs_date,
                            value=num_vente,
                            value_raw=str(vente_val),
                            vintage="final",
                            observed_or_imputed="observed",
                            published_at=published_at,
                            first_available_at=avail_dt,
                            evidence={
                                "primary_institution": "Banky Foiben'i Madagasikara",
                                "market": "MID",
                                "currency": curr,
                                "rate_type": "sell",
                            },
                        )
                    )
                except ValueError:
                    pass

        return records

    def _parse_html(
        self,
        raw_bytes: bytes,
        published_at: datetime,
        first_available_at: datetime,
    ) -> list[MacroRecord]:
        """Parse daily HTML bulletin table from BFM portal."""
        try:
            html_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            html_text = raw_bytes.decode("latin1", errors="replace")

        parser = LexborHTMLParser(html_text)
        records: list[MacroRecord] = []

        # Find quotation date from body or header
        date_node = parser.css_first(".date-cotation, .seance-date, h1, h2, caption, p")
        obs_date: date | None = None
        if date_node and date_node.text():
            obs_date = parse_french_date_text(date_node.text())

        if not obs_date:
            obs_date = published_at.date()

        if not is_business_trading_day(obs_date):
            logger.warning("BFM HTML quotation date %s is a weekend; skipping", obs_date)
            return []

        obs_dt = datetime.combine(obs_date, time(17, 0), tzinfo=UTC)
        avail_dt = max(obs_dt, first_available_at)

        # Parse table rows
        rows = parser.css("table tr")
        for tr in rows:
            tds = tr.css("td")
            if len(tds) < 4:
                continue
            curr_code = tds[0].text().strip().upper()
            if curr_code not in SUPPORTED_CURRENCIES:
                continue

            # Expected columns: Code | Libelle | Achat | Vente | Moyen
            # or: Code | Achat | Vente | Moyen
            if len(tds) >= 5:
                achat_txt = tds[2].text().strip()
                vente_txt = tds[3].text().strip()
                moyen_txt = tds[4].text().strip()
            else:
                achat_txt = tds[1].text().strip()
                vente_txt = tds[2].text().strip()
                moyen_txt = tds[3].text().strip()

            try:
                num_moyen = clean_rate_number(moyen_txt)
                inv_moyen = compute_inverse_exchange_rate(num_moyen)
                records.append(
                    MacroRecord(
                        indicator_code=f"EXCHANGE_RATE_{curr_code}_MGA",
                        indicator_name=f"Cours de Change {curr_code}/MGA Moyen",
                        frequency="daily",
                        unit="MGA",
                        geo_scope="national",
                        period_start=obs_date,
                        period_end=obs_date,
                        value=num_moyen,
                        value_raw=moyen_txt,
                        vintage="final",
                        observed_or_imputed="observed",
                        published_at=published_at,
                        first_available_at=avail_dt,
                        evidence={
                            "primary_institution": "Banky Foiben'i Madagasikara",
                            "market": "MID",
                            "currency": curr_code,
                            "rate_type": "mid",
                            "inverse_rate_usd_per_mga": inv_moyen,
                        },
                    )
                )
            except ValueError:
                pass

            try:
                num_achat = clean_rate_number(achat_txt)
                records.append(
                    MacroRecord(
                        indicator_code=f"EXCHANGE_RATE_{curr_code}_MGA_BUY",
                        indicator_name=f"Cours de Change {curr_code}/MGA Achat",
                        frequency="daily",
                        unit="MGA",
                        geo_scope="national",
                        period_start=obs_date,
                        period_end=obs_date,
                        value=num_achat,
                        value_raw=achat_txt,
                        vintage="final",
                        observed_or_imputed="observed",
                        published_at=published_at,
                        first_available_at=avail_dt,
                        evidence={
                            "primary_institution": "Banky Foiben'i Madagasikara",
                            "market": "MID",
                            "currency": curr_code,
                            "rate_type": "buy",
                        },
                    )
                )
            except ValueError:
                pass

            try:
                num_vente = clean_rate_number(vente_txt)
                records.append(
                    MacroRecord(
                        indicator_code=f"EXCHANGE_RATE_{curr_code}_MGA_SELL",
                        indicator_name=f"Cours de Change {curr_code}/MGA Vente",
                        frequency="daily",
                        unit="MGA",
                        geo_scope="national",
                        period_start=obs_date,
                        period_end=obs_date,
                        value=num_vente,
                        value_raw=vente_txt,
                        vintage="final",
                        observed_or_imputed="observed",
                        published_at=published_at,
                        first_available_at=avail_dt,
                        evidence={
                            "primary_institution": "Banky Foiben'i Madagasikara",
                            "market": "MID",
                            "currency": curr_code,
                            "rate_type": "sell",
                        },
                    )
                )
            except ValueError:
                pass

        return records


BfmPublicConnector = Connector
