"""Connector for Douanes Malagasy external trade statistics (SPECS §5.2, §8, T4.3)."""

from __future__ import annotations

import calendar
import csv
import hashlib
import io
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import ClassVar

from ketrika.connectors.base import (
    Connector,
    DiscoveredItem,
    ParseResult,
    RawArtifact,
    RunContext,
)
from ketrika.connectors.records import TradeFlowRecord
from ketrika.core.registry import find_repo_root


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
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover monthly trade statistics artifacts."""
        # Main dataset of PPN commodities
        yield DiscoveredItem(
            url="https://www.douanes.gov.mg/stats/douanes_stats_2024.csv",
            partition_key="douanes_stats_2024",
            published_at=datetime(2024, 4, 1, 8, 0, tzinfo=UTC),
            hints={"year": "2024"},
        )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch trade data CSV into Bronze storage respecting polite rate limits."""
        content_bytes: bytes

        if ctx.offline:
            root = find_repo_root()
            base_dir = (
                Path("/app")
                if Path("/app/tests").exists()
                else (root / "backend" if (root / "backend").exists() else root)
            )
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
        issues: list[dict[str, str]] = []

        reader = csv.DictReader(io.StringIO(content_str))

        for row_idx, row in enumerate(reader, start=1):
            year_val = _parse_float(row.get("annee"))
            month_val = _parse_float(row.get("mois"))

            if year_val is None or month_val is None:
                issues.append(
                    {
                        "kind": "missing_period",
                        "row": str(row_idx),
                        "details": f"Missing year or month in row: {row}",
                    }
                )
                continue

            year = int(year_val)
            month = int(month_val)
            last_day = calendar.monthrange(year, month)[1]
            period_start = date(year, month, 1)
            period_end = date(year, month, last_day)

            raw_flow = _clean_str(row.get("flux") or "import").lower()
            flow = "export" if "export" in raw_flow else "import"

            hs_code = _clean_str(row.get("code_sh"))
            product_raw = _clean_str(row.get("designation_produit"))
            if not product_raw:
                product_raw = f"Produit SH {hs_code}"

            partner_raw = _clean_str(
                row.get("pays_partenaire") or row.get("pays_origine") or row.get("pays_destination")
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
                    evidence={"row": row_idx, "hs_code": hs_code, "partner": partner_raw},
                    confidence=1.0,
                )
            )

        return ParseResult(
            records=records,
            issues=issues,
            parser_version=self.parser_version,
        )
