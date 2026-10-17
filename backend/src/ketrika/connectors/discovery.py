"""Catalog discovery, bounded pagination, SSRF validation and edition tracking (R1.2, SPECS §9, §12)."""

from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from selectolax.lexbor import LexborHTMLParser

from ketrika.connectors.base import DiscoveredItem, ParseResult
from ketrika.core.http import FetchResult, PoliteHttpClient
from ketrika.core.policy import PolicyStop, validate_candidate_url


class DiscoveryStatus(StrEnum):
    """Categorized status for catalogue and edition exploration."""

    NEW_EDITIONS_AVAILABLE = "new_editions_available"
    NO_NEW_EDITION = "no_new_edition"
    DISCOVERY_FAILED = "discovery_failed"
    EMPTY_PARSING = "empty_parsing"


@dataclass(frozen=True)
class DiscoveredEdition:
    """A discovered edition item tracing catalog lineage, provenance and conditional headers."""

    url: str
    source_id: str
    parent_url: str
    title: str | None = None
    published_at: datetime | None = None
    partition_key: str | None = None
    edition_identifier: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    content_sha256: str | None = None
    is_new: bool = True
    hints: dict[str, Any] = field(default_factory=dict)

    def to_discovered_item(self) -> DiscoveredItem:
        """Convert into legacy DiscoveredItem for connector compatibility."""
        return DiscoveredItem(
            url=self.url,
            partition_key=self.partition_key,
            published_at=self.published_at,
            hints=dict(self.hints, parent_url=self.parent_url),
        )


@dataclass
class DiscoveryResult:
    """Outcome of a catalogue scan containing items, pagination stats and distinct status."""

    status: DiscoveryStatus
    source_id: str
    catalog_url: str
    pages_scanned: int
    editions: list[DiscoveredEdition] = field(default_factory=list)
    new_editions_count: int = 0
    unchanged_editions_count: int = 0
    error: str | None = None


class CatalogDiscoveryEngine:
    """Bounded discovery engine navigating catalogs, RSS feeds and APIs with SSRF prevention."""

    MAX_PAGES_LIMIT: int = 20

    def __init__(
        self,
        source_id: str,
        http_client: PoliteHttpClient | None = None,
        allowed_domains: Sequence[str] | None = None,
        max_pages: int = 5,
        allow_loopback: bool = False,
    ) -> None:
        self.source_id = source_id
        self.http_client = http_client or PoliteHttpClient(allow_loopback=allow_loopback)
        self.allowed_domains = allowed_domains
        self.max_pages = min(max(1, max_pages), self.MAX_PAGES_LIMIT)
        self.allow_loopback = allow_loopback

    def discover_html_editions(
        self,
        start_url: str,
        link_pattern: str | re.Pattern[str],
        next_page_pattern: str | re.Pattern[str] | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> DiscoveryResult:
        """Scan HTML pages following bounded pagination and extract document edition links."""
        validate_candidate_url(
            start_url,
            allowed_domains=self.allowed_domains,
            allow_loopback=self.allow_loopback,
        )

        pattern = re.compile(link_pattern) if isinstance(link_pattern, str) else link_pattern
        next_pat = (
            re.compile(next_page_pattern)
            if isinstance(next_page_pattern, str)
            else next_page_pattern
        )

        visited_pages: set[str] = set()
        current_page_url: str | None = start_url
        discovered_editions: list[DiscoveredEdition] = []
        pages_scanned = 0

        while current_page_url and pages_scanned < self.max_pages:
            if current_page_url in visited_pages:
                break
            visited_pages.add(current_page_url)
            pages_scanned += 1

            try:
                # Use conditional headers on start page if provided
                fetch_etag = etag if pages_scanned == 1 else None
                fetch_last_mod = last_modified if pages_scanned == 1 else None
                resp: FetchResult = self.http_client.get(
                    current_page_url, etag=fetch_etag, last_modified=fetch_last_mod
                )
            except Exception as exc:
                return DiscoveryResult(
                    status=DiscoveryStatus.DISCOVERY_FAILED,
                    source_id=self.source_id,
                    catalog_url=start_url,
                    pages_scanned=pages_scanned,
                    error=f"Fetch failed for {current_page_url}: {exc}",
                )

            if resp.is_not_modified:
                return DiscoveryResult(
                    status=DiscoveryStatus.NO_NEW_EDITION,
                    source_id=self.source_id,
                    catalog_url=start_url,
                    pages_scanned=pages_scanned,
                    unchanged_editions_count=1,
                )

            if resp.status_code >= 400:
                return DiscoveryResult(
                    status=DiscoveryStatus.DISCOVERY_FAILED,
                    source_id=self.source_id,
                    catalog_url=start_url,
                    pages_scanned=pages_scanned,
                    error=f"HTTP status {resp.status_code} on {current_page_url}",
                )

            tree = LexborHTMLParser(resp.text)

            # Find matching document links
            for node in tree.css("a[href]"):
                href = node.attributes.get("href", "")
                if not href:
                    continue
                match = pattern.search(href)
                if match:
                    abs_url = urllib.parse.urljoin(current_page_url, href)
                    try:
                        valid_url = validate_candidate_url(
                            abs_url,
                            allowed_domains=self.allowed_domains,
                            allow_loopback=self.allow_loopback,
                        )
                    except PolicyStop:
                        continue  # Skip forbidden SSRF or cross-domain link

                    link_text = node.text(strip=True) if node.text() else None
                    edition_id = match.group(1) if match.groups() else None
                    discovered_editions.append(
                        DiscoveredEdition(
                            url=valid_url,
                            source_id=self.source_id,
                            parent_url=current_page_url,
                            title=link_text,
                            edition_identifier=edition_id,
                        )
                    )

            # Find next page link if requested and bounded
            next_url: str | None = None
            if next_pat and pages_scanned < self.max_pages:
                for node in tree.css("a[href]"):
                    href = node.attributes.get("href", "")
                    if href and next_pat.search(href):
                        cand_url = urllib.parse.urljoin(current_page_url, href)
                        try:
                            next_url = validate_candidate_url(
                                cand_url,
                                allowed_domains=self.allowed_domains,
                                allow_loopback=self.allow_loopback,
                            )
                            if next_url not in visited_pages:
                                break
                            next_url = None
                        except PolicyStop:
                            next_url = None

            current_page_url = next_url

        # Deduplicate editions preserving discovery order
        unique_editions: list[DiscoveredEdition] = []
        seen_urls: set[str] = set()
        for ed in discovered_editions:
            if ed.url not in seen_urls:
                seen_urls.add(ed.url)
                unique_editions.append(ed)

        status = (
            DiscoveryStatus.NEW_EDITIONS_AVAILABLE
            if unique_editions
            else DiscoveryStatus.NO_NEW_EDITION
        )
        return DiscoveryResult(
            status=status,
            source_id=self.source_id,
            catalog_url=start_url,
            pages_scanned=pages_scanned,
            editions=unique_editions,
            new_editions_count=len(unique_editions),
        )

    def discover_rss_editions(
        self,
        feed_url: str,
        link_pattern: str | re.Pattern[str] | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> DiscoveryResult:
        """Scan RSS/Atom XML feed and extract edition entries with publication dates."""
        validate_candidate_url(
            feed_url,
            allowed_domains=self.allowed_domains,
            allow_loopback=self.allow_loopback,
        )

        pattern = (
            re.compile(link_pattern)
            if isinstance(link_pattern, str)
            else link_pattern
            if link_pattern
            else None
        )

        try:
            resp: FetchResult = self.http_client.get(feed_url, etag=etag, last_modified=last_modified)
        except Exception as exc:
            return DiscoveryResult(
                status=DiscoveryStatus.DISCOVERY_FAILED,
                source_id=self.source_id,
                catalog_url=feed_url,
                pages_scanned=1,
                error=f"Fetch failed for {feed_url}: {exc}",
            )

        if resp.is_not_modified:
            return DiscoveryResult(
                status=DiscoveryStatus.NO_NEW_EDITION,
                source_id=self.source_id,
                catalog_url=feed_url,
                pages_scanned=1,
                unchanged_editions_count=1,
            )

        if resp.status_code >= 400:
            return DiscoveryResult(
                status=DiscoveryStatus.DISCOVERY_FAILED,
                source_id=self.source_id,
                catalog_url=feed_url,
                pages_scanned=1,
                error=f"HTTP status {resp.status_code} on {feed_url}",
            )

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as err:
            return DiscoveryResult(
                status=DiscoveryStatus.DISCOVERY_FAILED,
                source_id=self.source_id,
                catalog_url=feed_url,
                pages_scanned=1,
                error=f"XML parse error: {err}",
            )

        editions: list[DiscoveredEdition] = []
        # Support both RSS (<item>) and Atom (<entry>)
        items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")

        for item in items:
            link_node = item.find("link")
            link_href = ""
            if link_node is not None:
                link_href = link_node.attrib.get("href") or link_node.text or ""

            # Check enclosure for direct files
            enclosure = item.find("enclosure")
            if enclosure is not None and "url" in enclosure.attrib:
                link_href = enclosure.attrib["url"]

            if not link_href:
                continue

            abs_url = urllib.parse.urljoin(feed_url, link_href)
            if pattern and not pattern.search(abs_url):
                continue

            try:
                valid_url = validate_candidate_url(
                    abs_url,
                    allowed_domains=self.allowed_domains,
                    allow_loopback=self.allow_loopback,
                )
            except PolicyStop:
                continue

            title_node = item.find("title")
            if title_node is None:
                title_node = item.find("{http://www.w3.org/2005/Atom}title")
            title = title_node.text.strip() if title_node is not None and title_node.text else None

            pub_date_node = item.find("pubDate")
            if pub_date_node is None:
                pub_date_node = item.find("{http://www.w3.org/2005/Atom}updated")
            pub_date: datetime | None = None
            if pub_date_node is not None and pub_date_node.text:
                from email.utils import parsedate_to_datetime

                try:
                    pub_date = parsedate_to_datetime(pub_date_node.text)
                except Exception:
                    pub_date = None

            editions.append(
                DiscoveredEdition(
                    url=valid_url,
                    source_id=self.source_id,
                    parent_url=feed_url,
                    title=title,
                    published_at=pub_date,
                )
            )

        status = (
            DiscoveryStatus.NEW_EDITIONS_AVAILABLE
            if editions
            else DiscoveryStatus.NO_NEW_EDITION
        )
        return DiscoveryResult(
            status=status,
            source_id=self.source_id,
            catalog_url=feed_url,
            pages_scanned=1,
            editions=editions,
            new_editions_count=len(editions),
        )

    def filter_known_editions(
        self,
        editions: Sequence[DiscoveredEdition],
        known_shas: set[str] | None = None,
        known_urls: set[str] | None = None,
    ) -> tuple[list[DiscoveredEdition], list[DiscoveredEdition]]:
        """Separate editions into new candidates vs already persisted editions.

        Returns (new_editions, unchanged_editions).
        """
        known_shas = known_shas or set()
        known_urls = known_urls or set()

        new_editions: list[DiscoveredEdition] = []
        unchanged_editions: list[DiscoveredEdition] = []

        for ed in editions:
            is_known_url = ed.url in known_urls
            is_known_sha = ed.content_sha256 is not None and ed.content_sha256 in known_shas

            if is_known_sha or (is_known_url and ed.content_sha256 is None and not ed.is_new):
                unchanged_editions.append(
                    DiscoveredEdition(
                        url=ed.url,
                        source_id=ed.source_id,
                        parent_url=ed.parent_url,
                        title=ed.title,
                        published_at=ed.published_at,
                        partition_key=ed.partition_key,
                        edition_identifier=ed.edition_identifier,
                        etag=ed.etag,
                        last_modified=ed.last_modified,
                        content_sha256=ed.content_sha256,
                        is_new=False,
                        hints=ed.hints,
                    )
                )
            else:
                new_editions.append(ed)

        return new_editions, unchanged_editions


def classify_ingestion_outcome(
    discovery_result: DiscoveryResult,
    parse_results: Sequence[ParseResult] | None = None,
) -> str:
    """Classify connector execution into one of: 'no_new_edition', 'discovery_failed', 'empty_parsing', or 'success'."""
    if discovery_result.status == DiscoveryStatus.DISCOVERY_FAILED:
        return "discovery_failed"

    if discovery_result.status == DiscoveryStatus.NO_NEW_EDITION or discovery_result.new_editions_count == 0:
        return "no_new_edition"

    if parse_results is not None:
        total_records = sum(len(p.records) for p in parse_results)
        if total_records == 0 and discovery_result.new_editions_count > 0:
            return "empty_parsing"

    return "success"
