"""Bounded pagination adapter for REST, JSON, and paginated HTTP sources (IA-DATA-03).

Provides deterministic, bounded iteration over paginated resources with:
- Multiple strategies: offset/limit, page_number, cursor, and next_url
- Hard ceilings: max_pages, max_records, max_total_bytes
- Infinite loop and cycle detection
- Checkpoint resumption across interrupted runs
- Secret-safe sanitized URLs
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from ketrika.connectors.adapters.checkpoint import (
    CheckpointStore,
    CollectionCheckpoint,
)
from ketrika.connectors.adapters.streaming import sanitize_url_for_logging
from ketrika.core.http import FetchResult, PoliteHttpClient
from ketrika.core.policy import PolicyStop, validate_candidate_url


class PaginationStrategy(StrEnum):
    """Supported pagination mechanisms for web APIs."""

    OFFSET_LIMIT = "offset_limit"
    PAGE_NUMBER = "page_number"
    CURSOR = "cursor"
    NEXT_URL = "next_url"


@dataclass(frozen=True)
class PaginationConfig:
    """Configuration governing bounded pagination."""

    strategy: PaginationStrategy = PaginationStrategy.OFFSET_LIMIT
    page_size: int = 100
    max_pages: int = 50
    max_records: int = 10_000
    max_bytes_per_page: int = 10 * 1024 * 1024  # 10 MiB
    max_total_bytes: int = 50 * 1024 * 1024  # 50 MiB
    offset_param: str = "offset"
    limit_param: str = "limit"
    page_param: str = "page"
    page_size_param: str = "page_size"
    cursor_param: str = "cursor"
    records_json_path: str | None = None
    next_url_json_path: str | None = None
    cursor_json_path: str | None = None


@dataclass
class PageResult:
    """Structured result of a single paginated fetch."""

    page_index: int
    url: str
    items: list[Any]
    raw_content: bytes
    bytes_count: int
    has_more: bool
    next_cursor: str | None = None
    etag: str | None = None
    last_modified: str | None = None


def _extract_nested(data: Any, path: str | None) -> Any:
    """Extract nested value using dot-notation path."""
    if not path or not isinstance(data, dict):
        return data
    curr = data
    for part in path.split("."):
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return None
    return curr


class BoundedPaginator:
    """Iterates over paginated web endpoints within strict bounds and resumes from checkpoints."""

    def __init__(
        self,
        source_id: str,
        base_url: str,
        config: PaginationConfig | None = None,
        http_client: PoliteHttpClient | None = None,
        checkpoint_store: CheckpointStore | None = None,
        partition_key: str = "",
        allowed_domains: list[str] | None = None,
        allow_loopback: bool = False,
    ) -> None:
        self.source_id = source_id
        self.base_url = base_url
        self.config = config or PaginationConfig()
        self.http_client = http_client or PoliteHttpClient(allow_loopback=allow_loopback)
        self.checkpoint_store = checkpoint_store
        self.partition_key = partition_key
        self.allowed_domains = allowed_domains
        self.allow_loopback = allow_loopback

    def iter_pages(self) -> Iterator[PageResult]:
        """Yield pages one by one, respecting limits and updating checkpoint state."""
        checkpoint = (
            self.checkpoint_store.get(self.source_id, self.partition_key)
            if self.checkpoint_store
            else None
        )
        if checkpoint is None:
            checkpoint = CollectionCheckpoint(
                source_id=self.source_id,
                partition_key=self.partition_key,
                cursor_type=self.config.strategy.value,
            )

        # Initialize cursor/offset based on checkpoint resume state
        current_offset = 0
        current_page_num = 1
        current_cursor: str | None = None
        current_next_url: str | None = None

        if checkpoint.cursor_value:
            if self.config.strategy == PaginationStrategy.OFFSET_LIMIT:
                try:
                    current_offset = int(checkpoint.cursor_value)
                except ValueError:
                    current_offset = 0
            elif self.config.strategy == PaginationStrategy.PAGE_NUMBER:
                try:
                    current_page_num = int(checkpoint.cursor_value)
                except ValueError:
                    current_page_num = 1
            elif self.config.strategy == PaginationStrategy.CURSOR:
                current_cursor = checkpoint.cursor_value
            elif self.config.strategy == PaginationStrategy.NEXT_URL:
                current_next_url = checkpoint.cursor_value

        pages_fetched = 0
        total_records = checkpoint.items_collected
        total_bytes = checkpoint.bytes_downloaded
        seen_urls: set[str] = set()
        seen_cursors: set[str] = set()

        while pages_fetched < self.config.max_pages:
            # 1. Determine next URL
            target_url = self._build_page_url(
                current_offset, current_page_num, current_cursor, current_next_url
            )

            # SSRF validation
            validate_candidate_url(
                target_url,
                allowed_domains=self.allowed_domains,
                allow_loopback=self.allow_loopback,
            )

            # 2. Cycle / Infinite Loop Detection
            if target_url in seen_urls:
                raise PolicyStop(
                    f"pagination_infinite_loop_detected: Repeated page URL {sanitize_url_for_logging(target_url)}"
                )
            seen_urls.add(target_url)

            if current_cursor and current_cursor in seen_cursors:
                raise PolicyStop(
                    f"pagination_infinite_loop_detected: Repeated cursor value {current_cursor}"
                )
            if current_cursor:
                seen_cursors.add(current_cursor)

            # 3. Fetch Page with polite client and conditional headers
            fetch_etag = checkpoint.etag if pages_fetched == 0 else None
            fetch_last_mod = checkpoint.last_modified if pages_fetched == 0 else None

            resp: FetchResult = self.http_client.get(
                target_url,
                etag=fetch_etag,
                last_modified=fetch_last_mod,
            )

            if resp.is_not_modified:
                checkpoint.mark_completed()
                if self.checkpoint_store:
                    self.checkpoint_store.save(checkpoint)
                return

            if resp.status_code >= 400:
                checkpoint.mark_failed(f"HTTP {resp.status_code}")
                if self.checkpoint_store:
                    self.checkpoint_store.save(checkpoint)
                raise PolicyStop(f"pagination_http_error: HTTP status {resp.status_code}")

            raw_bytes = resp.content
            bytes_count = len(raw_bytes)
            if bytes_count > self.config.max_bytes_per_page:
                raise PolicyStop(
                    f"pagination_page_size_exceeded: Page exceeded {self.config.max_bytes_per_page} bytes"
                )

            total_bytes += bytes_count
            if total_bytes > self.config.max_total_bytes:
                raise PolicyStop(
                    f"pagination_total_bytes_exceeded: Total download exceeded {self.config.max_total_bytes} bytes"
                )

            # 4. Parse Items from Response
            items, next_cursor_val, next_url_val = self._parse_page_items(resp)
            pages_fetched += 1
            total_records += len(items)

            has_more = self._evaluate_has_more(
                items=items,
                next_cursor=next_cursor_val,
                next_url=next_url_val,
                pages_fetched=pages_fetched,
            )

            # 5. Compute new cursor for next iteration
            next_checkpoint_cursor: str | None = None
            if self.config.strategy == PaginationStrategy.OFFSET_LIMIT:
                current_offset += len(items)
                next_checkpoint_cursor = str(current_offset)
            elif self.config.strategy == PaginationStrategy.PAGE_NUMBER:
                current_page_num += 1
                next_checkpoint_cursor = str(current_page_num)
            elif self.config.strategy == PaginationStrategy.CURSOR:
                current_cursor = next_cursor_val
                next_checkpoint_cursor = current_cursor
            elif self.config.strategy == PaginationStrategy.NEXT_URL:
                current_next_url = next_url_val
                next_checkpoint_cursor = current_next_url

            # 6. Update Checkpoint
            checkpoint.advance(
                new_cursor=next_checkpoint_cursor,
                new_items=len(items),
                new_bytes=bytes_count,
                etag=resp.etag,
                last_modified=resp.last_modified,
            )
            if not has_more:
                checkpoint.mark_completed()

            if self.checkpoint_store:
                self.checkpoint_store.save(checkpoint)

            # 7. Yield current page result
            yield PageResult(
                page_index=pages_fetched,
                url=target_url,
                items=items,
                raw_content=raw_bytes,
                bytes_count=bytes_count,
                has_more=has_more,
                next_cursor=next_checkpoint_cursor,
                etag=resp.etag,
                last_modified=resp.last_modified,
            )

            if not has_more or total_records >= self.config.max_records:
                break

    def _build_page_url(
        self,
        offset: int,
        page_num: int,
        cursor: str | None,
        next_url: str | None,
    ) -> str:
        """Construct the URL for the requested page based on strategy."""
        if self.config.strategy == PaginationStrategy.NEXT_URL and next_url:
            return next_url

        parsed = urlparse(self.base_url)
        params = dict(parse_qsl(parsed.query, keep_blank_values=True))

        if self.config.strategy == PaginationStrategy.OFFSET_LIMIT:
            params[self.config.offset_param] = str(offset)
            params[self.config.limit_param] = str(self.config.page_size)
        elif self.config.strategy == PaginationStrategy.PAGE_NUMBER:
            params[self.config.page_param] = str(page_num)
            params[self.config.page_size_param] = str(self.config.page_size)
        elif self.config.strategy == PaginationStrategy.CURSOR and cursor:
            params[self.config.cursor_param] = cursor

        new_query = urlencode(params)
        return urlunparse(parsed._replace(query=new_query))

    def _parse_page_items(
        self,
        resp: FetchResult,
    ) -> tuple[list[Any], str | None, str | None]:
        """Extract items and optional next links from JSON/text response."""
        content_type = resp.headers.get("content-type", "").lower()
        if "json" in content_type or resp.text.strip().startswith(("{", "[")):
            try:
                data = json.loads(resp.text)
            except Exception:
                return [], None, None

            # 1. Extract items list
            raw_items = _extract_nested(data, self.config.records_json_path)
            items: list[Any] = []
            if isinstance(raw_items, list):
                items = raw_items
            elif isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # Search common list keys if not specified
                for candidate in ("data", "results", "records", "items"):
                    if isinstance(data.get(candidate), list):
                        items = data[candidate]
                        break

            # 2. Extract next cursor or next URL
            next_cursor = None
            if self.config.cursor_json_path and isinstance(data, dict):
                val = _extract_nested(data, self.config.cursor_json_path)
                if val:
                    next_cursor = str(val)

            next_url = None
            if self.config.next_url_json_path and isinstance(data, dict):
                val = _extract_nested(data, self.config.next_url_json_path)
                if val:
                    next_url = str(val)

            return items, next_cursor, next_url

        # Non-JSON content (e.g. CSV or HTML text)
        return [resp.text], None, None

    def _evaluate_has_more(
        self,
        items: list[Any],
        next_cursor: str | None,
        next_url: str | None,
        pages_fetched: int,
    ) -> bool:
        """Determine whether another page exists."""
        if pages_fetched >= self.config.max_pages:
            return False

        if not items:
            return False

        if self.config.strategy == PaginationStrategy.OFFSET_LIMIT:
            # If received fewer items than page_size, endpoint is exhausted
            return len(items) >= self.config.page_size

        if self.config.strategy == PaginationStrategy.PAGE_NUMBER:
            return len(items) >= self.config.page_size

        if self.config.strategy == PaginationStrategy.CURSOR:
            return bool(next_cursor)

        if self.config.strategy == PaginationStrategy.NEXT_URL:
            return bool(next_url)

        return False
