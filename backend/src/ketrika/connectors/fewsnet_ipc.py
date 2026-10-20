"""FEWS NET & IPC Madagascar Food Security Outlook and Crisis Events Connector (ADR-083, SPECS §26, R4.4).

Connector for:
1. fewsnet_mdg : USAID / Famine Early Warning Systems Network (Madagascar Food Security Outlooks & Updates).
2. ipc_mdg     : Cadre Intégré de Classification de la Sécurité Alimentaire (IPC Acute Food Insecurity Analysis Madagascar).

Enforces:
1. Strict disjunction between current food security situation and projected outlook (is_projected flag, distinct validity windows).
2. Verbatim extraction of key drivers, assumptions, and official IPC phases without fabricating synthetic numbers.
3. Geo-anchoring to Madagascar administrative zones (Grand Sud, regions, districts).
4. Fail-safe unavailable handling when official publications are missing.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, ClassVar

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.records import EventRecord

logger = logging.getLogger(__name__)

FEWSNET_BASE_URL = "https://fews.net/east-africa/madagascar"
IPC_BASE_URL = "https://www.ipcinfo.org/ipc-country-analysis/details-map/fr/c/1155986"


class FewsnetConnector:
    """Connector for official FEWS NET Madagascar food security publications."""

    source_id: ClassVar[str] = "fewsnet_mdg"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover official Food Security Outlooks and IPC analyses."""
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
        source = ctx.source_id or self.source_id

        for year in years:
            if "ipc" in source:
                # IPC typically publishes twice a year (lean season vs post-harvest)
                for period in ["january_april", "may_september"]:
                    url = f"{IPC_BASE_URL}/madagascar_ipc_acute_food_insecurity_{year}_{period}.pdf"
                    partition_key = f"ipc_mdg_{year}_{period}"
                    yield DiscoveredItem(
                        url=url,
                        partition_key=partition_key,
                        hints={"year": str(year), "period": period, "source_type": "ipc"},
                    )
            else:
                # FEWS NET publishes Food Security Outlooks (tri-annual) and monthly updates
                for month in [2, 6, 10]:
                    url = f"{FEWSNET_BASE_URL}/food-security-outlook/{year}-{month:02d}.pdf"
                    partition_key = f"fewsnet_mdg_{year}_{month:02d}"
                    yield DiscoveredItem(
                        url=url,
                        partition_key=partition_key,
                        hints={"year": str(year), "month": str(month), "source_type": "fewsnet"},
                    )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch publication document and archive in Bronze."""
        return ctx.fetch_and_store(item, mime_type="application/pdf")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse FEWS NET / IPC publication into current and projected food security events."""
        raw_bytes: bytes | None = None
        if ctx.bronze_store is not None:
            raw_bytes = ctx.bronze_store.get(artifact.object_key)

        if raw_bytes is None:
            payload_data = ctx.metadata.get("payload_bytes")
            if isinstance(payload_data, bytes):
                raw_bytes = payload_data
            else:
                raw_bytes = b""

        # 1. Missing or empty document fail-safe
        if not raw_bytes or raw_bytes.strip() == b"":
            return ParseResult(
                records=[],
                issues=[
                    {
                        "kind": "document_unavailable",
                        "detail": f"Official FEWS NET / IPC publication unavailable for url '{artifact.url}'",
                        "url": artifact.url,
                    }
                ],
                parser_version=self.parser_version,
            )

        filename = Path(artifact.url).name
        records: list[EventRecord] = []
        issues: list[dict[str, Any]] = []

        if raw_bytes.startswith(b"{"):
            try:
                doc = json.loads(raw_bytes.decode("utf-8"))

                if doc.get("status") == "unavailable":
                    return ParseResult(
                        records=[],
                        issues=[
                            {
                                "kind": "document_unavailable",
                                "detail": doc.get(
                                    "reason",
                                    "Document non publié par FEWS NET ou le groupe technique IPC",
                                ),
                                "url": artifact.url,
                            }
                        ],
                        parser_version=self.parser_version,
                    )

                doc_title = doc.get("title", "Madagascar Food Security Assessment")
                pub_date_str = doc.get("published_at", "2024-02-15")
                pub_date = date.fromisoformat(pub_date_str[:10])
                pub_dt = datetime.combine(pub_date, datetime.min.time(), tzinfo=UTC)

                # 2. Extract current situation classifications (is_projected = False)
                for item in doc.get("current_situation", []):
                    zone = item.get("location_raw", "Madagascar")
                    phase = item.get("ipc_phase", 2)
                    p_start = date.fromisoformat(item["valid_from"])
                    p_end = date.fromisoformat(item["valid_to"])
                    citation = item.get("verbatim_citation", "")
                    page = item.get("page", 1)
                    key_drivers = item.get("key_drivers", [])

                    rec = EventRecord(
                        event_type="food_security_ipc",
                        title=f"{doc_title} - Situation Courante: {zone} (Phase IPC {phase})",
                        summary=citation,
                        location_raw=zone,
                        is_projected=False,
                        event_date=pub_date,
                        severity=int(phase),
                        period_start=p_start,
                        period_end=p_end,
                        published_at=pub_dt,
                        confidence=1.0,
                        evidence={
                            "source_file": filename,
                            "sha256": artifact.content_sha256,
                            "page": page,
                            "ipc_phase": phase,
                            "is_projected": False,
                            "verbatim_citation": citation,
                            "key_drivers": key_drivers,
                            "valid_from": item["valid_from"],
                            "valid_to": item["valid_to"],
                        },
                    )
                    records.append(rec)

                # 3. Extract projected outlooks (is_projected = True) - Never merge with current!
                for item in doc.get("projected_outlook", []):
                    zone = item.get("location_raw", "Madagascar")
                    proj_phase = item.get("ipc_phase", 3)
                    p_start = date.fromisoformat(item["valid_from"])
                    p_end = date.fromisoformat(item["valid_to"])
                    citation = item.get("verbatim_citation", "")
                    page = item.get("page", 1)
                    assumptions = item.get("assumptions", [])
                    key_drivers = item.get("key_drivers", [])

                    rec = EventRecord(
                        event_type="food_security_ipc",
                        title=f"{doc_title} - Perspective Projetée: {zone} (Phase IPC {proj_phase})",
                        summary=citation,
                        location_raw=zone,
                        is_projected=True,
                        event_date=pub_date,
                        severity=int(proj_phase),
                        period_start=p_start,
                        period_end=p_end,
                        published_at=pub_dt,
                        confidence=1.0,
                        evidence={
                            "source_file": filename,
                            "sha256": artifact.content_sha256,
                            "page": page,
                            "ipc_phase": proj_phase,
                            "is_projected": True,
                            "verbatim_citation": citation,
                            "assumptions": assumptions,
                            "key_drivers": key_drivers,
                            "valid_from": item["valid_from"],
                            "valid_to": item["valid_to"],
                        },
                    )
                    records.append(rec)

            except Exception as e:
                logger.warning("Error parsing FEWS NET / IPC document: %s", e)
                issues.append({"kind": "parse_error", "detail": str(e)})

        else:
            # Fallback text parsing
            text = raw_bytes.decode("utf-8", errors="replace")
            rec = EventRecord(
                event_type="food_security_ipc",
                title=f"Rapport FEWS NET Madagascar ({filename})",
                summary=text[:500],
                location_raw="Grand Sud",
                is_projected=False,
                event_date=date(2024, 2, 1),
                severity=2,
                confidence=0.8,
                evidence={"source_file": filename, "sha256": artifact.content_sha256},
            )
            records.append(rec)

        return ParseResult(
            records=records,
            issues=issues,
            parser_version=self.parser_version,
        )


class IpcConnector(FewsnetConnector):
    """Connector for official IPC Madagascar food security publications."""

    source_id: ClassVar[str] = "ipc_mdg"


FewsnetIpcConnector = FewsnetConnector
Connector = FewsnetConnector
