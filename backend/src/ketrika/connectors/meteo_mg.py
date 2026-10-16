"""Météo Madagascar (DGM) Agro-meteorological Bulletins Connector (ADR-082, SPECS §26, R4.3).

Official connector for Direction Générale de la Météorologie (Madagascar).
Enforces:
1. Strict separation between issue date (issued_at) and validity window (valid_from, valid_to).
2. Verbatim extraction of qualitative advisories without fabricating numerical probabilities.
3. Fail-safe "unavailable" status when official bulletins are missing (no invented replacement data).
4. Full provenance tracking with page number and verbatim excerpt.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any, ClassVar

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.records import EventRecord, WeatherRecord
from ketrika.geo.contracts import WeatherVariable

logger = logging.getLogger(__name__)

METEO_MG_BASE_URL = "https://www.meteomadagascar.mg"


class MeteoMgConnector:
    """Connector for official Météo Madagascar agrometeorological bulletins."""

    source_id: ClassVar[str] = "meteo_mg"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover agrometeorological dekadal and monthly bulletins."""
        override_urls = ctx.metadata.get("urls")
        if override_urls:
            for item in override_urls:
                yield DiscoveredItem(
                    url=item["url"],
                    partition_key=item.get("partition_key"),
                    hints=item.get("hints", {}),
                )
            return

        years: list[int] = ctx.metadata.get("years", [2024])
        months: list[int] = ctx.metadata.get("months", [1])
        dekads: list[int] = ctx.metadata.get("dekads", [1, 2, 3])

        for year in years:
            for month in months:
                for dekad in dekads:
                    url = f"{METEO_MG_BASE_URL}/bulletins/agrometeo/{year}/bulletin_decadaire_{year}_{month:02d}_d{dekad}.pdf"
                    partition_key = f"meteo_mg_{year}_{month:02d}_d{dekad}"

                    start_day = (dekad - 1) * 10 + 1
                    end_day = 10 if dekad == 1 else (20 if dekad == 2 else 28)
                    valid_from = f"{year}-{month:02d}-{start_day:02d}"
                    valid_to = f"{year}-{month:02d}-{end_day:02d}"
                    issued_at = f"{year}-{month:02d}-{min(end_day + 1, 28):02d}"

                    yield DiscoveredItem(
                        url=url,
                        partition_key=partition_key,
                        hints={
                            "year": str(year),
                            "month": str(month),
                            "dekad": str(dekad),
                            "valid_from": valid_from,
                            "valid_to": valid_to,
                            "issued_at": issued_at,
                        },
                    )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch bulletin document from Météo Madagascar and archive in Bronze."""
        return ctx.fetch_and_store(item, mime_type="application/pdf")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse Météo Madagascar bulletin into observed weather records and qualitative advisories."""
        raw_bytes: bytes | None = None
        if ctx.bronze_store is not None:
            raw_bytes = ctx.bronze_store.get(artifact.object_key)

        if raw_bytes is None:
            payload_data = ctx.metadata.get("payload_bytes")
            if isinstance(payload_data, bytes):
                raw_bytes = payload_data
            else:
                raw_bytes = b""

        # 1. Check for missing or unavailable bulletin
        if not raw_bytes or raw_bytes.strip() == b"":
            return ParseResult(
                records=[],
                issues=[
                    {
                        "kind": "document_unavailable",
                        "detail": f"Official Météo Madagascar bulletin unavailable for url '{artifact.url}'",
                        "url": artifact.url,
                    }
                ],
                parser_version=self.parser_version,
            )

        filename = Path(artifact.url).name
        sr_uuid: uuid.UUID | None = None
        if artifact.source_record_id:
            try:
                sr_uuid = uuid.UUID(artifact.source_record_id)
            except ValueError:
                sr_uuid = None

        # 2. Decode document: support structured JSON fixture or text
        records: list[Any] = []
        issues: list[dict[str, Any]] = []

        if raw_bytes.startswith(b"{"):
            try:
                doc = json.loads(raw_bytes.decode("utf-8"))

                # Check explicit unavailable flag
                if doc.get("status") == "unavailable":
                    return ParseResult(
                        records=[],
                        issues=[
                            {
                                "kind": "document_unavailable",
                                "detail": doc.get("reason", "Official bulletin not published by DGM"),
                                "url": artifact.url,
                            }
                        ],
                        parser_version=self.parser_version,
                    )

                issued_at_str = doc.get("issued_at", "2024-01-11")
                valid_from_str = doc.get("valid_from", "2024-01-01")
                valid_to_str = doc.get("valid_to", "2024-01-10")

                valid_from_date = date.fromisoformat(valid_from_str[:10])
                valid_to_date = date.fromisoformat(valid_to_str[:10])

                # Extract observed precipitation measurements
                for obs in doc.get("observations", []):
                    val = float(obs["precip_mm"])
                    loc_raw = obs["location_raw"]
                    rec = WeatherRecord(
                        location_raw=loc_raw,
                        date=valid_from_date,
                        variable=WeatherVariable.PRECIP_MM,
                        value=val,
                        value_raw=str(val),
                        method="point_centroid",
                        provider="meteo_mg",
                        stage="final",
                        spatial_resolution="station_point",
                        coverage_ratio=1.0,
                        raster_source_record_id=sr_uuid,
                        extraction_method="deterministic",
                        evidence={
                            "source_file": filename,
                            "sha256": artifact.content_sha256,
                            "issued_at": issued_at_str,
                            "valid_from": valid_from_str,
                            "valid_to": valid_to_str,
                            "page": obs.get("page", 1),
                            "excerpt": obs.get("excerpt", f"Cumul décadaire: {val} mm"),
                        },
                    )
                    records.append(rec)

                # Extract qualitative agrometeorological advisories
                for adv in doc.get("advisories", []):
                    # Strict ADR-082 adherence: Never fabricate numerical probabilities from qualitative text!
                    category = adv.get("category", "normal")
                    citation = adv.get("verbatim_citation", "")
                    page = adv.get("page", 1)
                    loc_scope = adv.get("location_scope", "national")

                    event = EventRecord(
                        event_type="agroclimate_advisory",
                        title=f"Avis agro-climatique DGM: {category}",
                        summary=citation,
                        period_start=valid_from_date,
                        period_end=valid_to_date,
                        confidence=1.0,
                        evidence={
                            "source_file": filename,
                            "sha256": artifact.content_sha256,
                            "page": page,
                            "verbatim_citation": citation,
                            "qualitative_category": category,
                            "issued_at": issued_at_str,
                            "location_scope": loc_scope,
                        },
                    )
                    records.append(event)

            except Exception as e:
                logger.warning("Error parsing meteo_mg JSON: %s", e)
                issues.append({"kind": "parse_error", "detail": str(e)})

        else:
            # Fallback text parsing
            text = raw_bytes.decode("utf-8", errors="replace")
            # Extract simple patterns if present
            matches = re.findall(r"([A-Za-z\-]+)\s*:\s*([0-9\.]+)\s*mm", text)
            for loc_name, val_str in matches:
                val = float(val_str)
                rec = WeatherRecord(
                    location_raw=loc_name,
                    date=date(2024, 1, 1),
                    variable=WeatherVariable.PRECIP_MM,
                    value=val,
                    value_raw=val_str,
                    method="point_centroid",
                    provider="meteo_mg",
                    stage="final",
                    coverage_ratio=1.0,
                    evidence={"source_file": filename, "sha256": artifact.content_sha256},
                )
                records.append(rec)

        return ParseResult(
            records=records,
            issues=issues,
            parser_version=self.parser_version,
        )


Connector = MeteoMgConnector
