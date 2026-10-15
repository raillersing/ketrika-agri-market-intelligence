"""Connector for Douanes Malagasy external trade statistics (SPECS §5.2, §8, T4.3)."""

from __future__ import annotations

import calendar
import csv
import hashlib
import io
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, ClassVar

from ketrika.connectors.base import (
    Connector,
    DiscoveredItem,
    ParseResult,
    RawArtifact,
    RunContext,
)
from ketrika.connectors.discovery import CatalogDiscoveryEngine
from ketrika.connectors.records import TradeFlowRecord
from ketrika.core.registry import find_repo_root

KNOWN_PPN_HS_CHAPTERS: set[str] = {"07", "10", "11", "12", "15", "17"}


def _validate_hs_code(hs_code: str) -> tuple[bool, str | None]:
    """Validate HS code format and chapter consistency (SPECS §5.2, R1.6)."""
    clean = re.sub(r"[^0-9]", "", hs_code)
    if len(clean) not in (6, 8):
        return False, f"Invalid HS code length ({len(clean)} digits, expected 6 or 8)"
    chapter = clean[:2]
    if chapter not in KNOWN_PPN_HS_CHAPTERS:
        return (
            False,
            f"HS chapter {chapter} is outside agricultural PPN chapters (07, 10, 11, 12, 15, 17)",
        )
    return True, None


def _clean_str(val: str | None) -> str:
    """Strip and normalize string."""
    return " ".join((val or "").split()).strip()


def _parse_float(val: str | None) -> float | None:
    """Parse float from formatted number string."""
    if not val:
        return None
    clean = val.replace(" ", "").replace(",", ".").strip()
    try:
        return float(clean)
    except ValueError:
        return None


class DouanesStatsConnector(Connector):
    """Connector for official Direction Générale des Douanes (DGD) import/export monthly data."""

    source_id: ClassVar[str] = "douanes_stats"
    parser_version: ClassVar[str] = "1.1.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover trade statistics editions via dynamic catalog or explicit targets."""
        # 1. Explicit file targets in metadata
        file_urls = ctx.metadata.get("file_urls")
        if file_urls and isinstance(file_urls, list):
            for u in file_urls:
                url_str = str(u)
                slug = Path(url_str).stem
                yield DiscoveredItem(
                    url=url_str,
                    partition_key=slug,
                    hints={"publisher": "Douanes Malagasy / DGD", "format": "csv"},
                )
            return

        file_url = ctx.metadata.get("file_url")
        if file_url:
            url_str = str(file_url)
            slug = Path(url_str).stem
            yield DiscoveredItem(
                url=url_str,
                partition_key=slug,
                hints={"publisher": "Douanes Malagasy / DGD", "format": "csv"},
            )
            return

        # 2. Dynamic catalog discovery (R1.2, R1.6)
        catalog_url = ctx.metadata.get("catalog_url")
        if catalog_url or (not ctx.offline and ctx.http_client is not None):
            target_cat_url = catalog_url or "https://www.douanes.gov.mg/statistiques"
            allow_loopback = ctx.metadata.get("allow_loopback", False)
            allowed_domains: list[str] = list(
                ctx.metadata.get("allowed_domains") or ["douanes.gov.mg"]
            )

            engine = CatalogDiscoveryEngine(
                http_client=ctx.http_client,
                source_id=self.source_id,
                allowed_domains=allowed_domains,
                allow_loopback=allow_loopback,
                max_pages=20,
            )

            discovery_res = engine.discover_html_editions(
                start_url=target_cat_url,
                link_pattern=r"/stats/.*(?:\.csv|\.xlsx)",
            )
            for edition in discovery_res.editions:
                slug = Path(edition.url).stem
                hints = {
                    "publisher": "Douanes Malagasy / DGD",
                    "format": "csv" if ".csv" in edition.url else "xlsx",
                }
                if edition.title:
                    hints["title"] = edition.title
                yield DiscoveredItem(
                    url=edition.url,
                    partition_key=slug,
                    published_at=edition.published_at,
                    hints=hints,
                )
            return

        # 3. Static historical datasets fallback
        publications = [
            ("douanes_stats_2024", datetime(2024, 4, 1, 8, 0, tzinfo=UTC), "2024"),
            ("douanes_stats_2023", datetime(2024, 1, 15, 8, 0, tzinfo=UTC), "2023"),
        ]

        for partition_key, pub_date, year in publications:
            yield DiscoveredItem(
                url=f"https://www.douanes.gov.mg/stats/{partition_key}.csv",
                partition_key=partition_key,
                published_at=pub_date,
                hints={"year": year, "publisher": "Douanes Malagasy / DGD"},
            )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch trade data CSV into Bronze storage respecting polite rate limits."""
        content_bytes: bytes

        if ctx.offline:
            root = find_repo_root()
            base_dir = root / "backend" if (root / "backend").exists() else root
            fixture_path = (
                base_dir / "tests" / "fixtures" / "douanes_stats" / f"{item.partition_key}.csv"
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
        object_key = f"{self.source_id}/{now.year}/{now.month:02d}/{content_sha256}.csv"
        is_new = True

        if ctx.bronze_store:
            bronze_art = ctx.bronze_store.put(
                source_id=self.source_id,
                content=content_bytes,
                mime_type="text/csv",
                url=item.url,
            )
            object_key = bronze_art.object_key
            is_new = bronze_art.is_new

        return RawArtifact(
            source_record_id="",
            object_key=object_key,
            content_sha256=content_sha256,
            mime_type="text/csv",
            url=item.url,
            is_new=is_new,
            published_at=item.published_at,
        )

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse Douanes trade statistics CSV into typed TradeFlowRecord instances."""
        if ctx.bronze_store is None:
            raise RuntimeError("BronzeStore is required for parsing artifacts")

        content_bytes = ctx.bronze_store.get(artifact.object_key)
        content_str = content_bytes.decode("utf-8", errors="replace")

        records: list[TradeFlowRecord] = []
        issues: list[dict[str, Any]] = []

        reader = csv.DictReader(io.StringIO(content_str))

        for row_idx, row in enumerate(reader, start=1):
            year_val = _parse_float(row.get("annee"))
            if year_val is None:
                issues.append(
                    {
                        "kind": "missing_period",
                        "row": str(row_idx),
                        "details": f"Missing year in row: {row}",
                    }
                )
                continue

            year = int(year_val)
            raw_month = _clean_str(row.get("mois")).upper()

            # Separate annual totals from monthly flows to prevent double-counting (R1.6)
            is_annual = raw_month in {
                "",
                "0",
                "13",
                "AN",
                "ANNUEL",
                "TOTAL",
                "ANNEE",
                "ANNÉE",
                "ALL",
            }
            if is_annual:
                period_start = date(year, 1, 1)
                period_end = date(year, 12, 31)
                aggregation_level = "annual_total"
            else:
                month_val = _parse_float(raw_month)
                if month_val is None or not (1 <= int(month_val) <= 12):
                    issues.append(
                        {
                            "kind": "invalid_month",
                            "row": str(row_idx),
                            "details": f"Invalid month value '{raw_month}' in row {row_idx}",
                        }
                    )
                    continue
                month = int(month_val)
                last_day = calendar.monthrange(year, month)[1]
                period_start = date(year, month, 1)
                period_end = date(year, month, last_day)
                aggregation_level = "monthly"

            raw_flow = _clean_str(row.get("flux") or "import").lower()
            flow = "export" if "export" in raw_flow else "import"

            hs_code = _clean_str(row.get("code_sh"))
            is_valid_hs, hs_issue = _validate_hs_code(hs_code)
            if not is_valid_hs and hs_code:
                issues.append(
                    {
                        "kind": "unverified_hs_code",
                        "row": str(row_idx),
                        "hs_code": hs_code,
                        "details": hs_issue or "Unverified HS code",
                    }
                )

            product_raw = _clean_str(row.get("designation_produit"))
            if not product_raw:
                product_raw = f"Produit SH {hs_code}"

            partner_raw = _clean_str(
                row.get("pays_partenaire")
                or row.get("pays_origine")
                or row.get("pays_destination")
            )
            partner_iso3 = _clean_str(row.get("code_iso3_pays") or "")

            weight_raw = _clean_str(row.get("poids_net_kg"))
            weight_kg = _parse_float(weight_raw)

            val_mga_raw = _clean_str(
                row.get("valeur_caf_fob_mga")
                or row.get("valeur_caf_mga")
                or row.get("valeur_fob_mga")
            )
            val_mga = _parse_float(val_mga_raw)

            val_usd_raw = _clean_str(row.get("valeur_usd"))
            val_usd = _parse_float(val_usd_raw)

            records.append(
                TradeFlowRecord(
                    flow=flow,
                    product_raw=product_raw,
                    hs_code=hs_code or None,
                    partner_raw=partner_raw or None,
                    partner_iso3=partner_iso3 or None,
                    period_start=period_start,
                    period_end=period_end,
                    published_at=artifact.published_at,
                    value_raw=val_mga_raw or None,
                    value_mga=val_mga,
                    value_usd=val_usd,
                    weight_raw=weight_raw or None,
                    weight_kg=weight_kg,
                    extraction_method="deterministic",
                    evidence={
                        "row": row_idx,
                        "hs_code": hs_code,
                        "partner": partner_raw,
                        "aggregation_level": aggregation_level,
                    },
                    confidence=1.0 if is_valid_hs else 0.5,
                )
            )

        return ParseResult(
            records=records,
            issues=issues,
            parser_version=self.parser_version,
        )
