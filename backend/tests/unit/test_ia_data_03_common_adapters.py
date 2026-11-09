"""Unit and simulation tests for IA-DATA-03: Common bounded acquisition adapters.

Normative requirements:
1. Bounded pagination: offset/limit, page_number, cursor, next_url within strict ceilings.
2. Controlled streaming: hard byte limits and on-the-fly SHA-256 calculation.
3. Resumable checkpoints: exact resume from interruption (429/503/disconnect) without duplicates or gaps.
4. Infinite loop protection: cycle detection on repeated URLs or cursors.
5. Secrecy & SSRF: secret redaction in logging and boundary validation.
"""

from __future__ import annotations

import hashlib
import json
from unittest.mock import MagicMock

import pytest

from ketrika.connectors.adapters.checkpoint import (
    CollectionCheckpoint,
    InMemoryCheckpointStore,
)
from ketrika.connectors.adapters.pagination import (
    BoundedPaginator,
    PaginationConfig,
    PaginationStrategy,
)
from ketrika.connectors.adapters.streaming import (
    ControlledStreamReader,
    StreamConfig,
    sanitize_url_for_logging,
)
from ketrika.core.http import FetchResult
from ketrika.core.policy import PolicyStop


def test_bounded_pagination_offset_limit_strategy() -> None:
    """Test offset/limit pagination collecting all items across multiple pages."""
    mock_client = MagicMock()

    # Page 1 (offset=0, limit=2): 2 items
    p1 = json.dumps({"data": [{"id": 1}, {"id": 2}]}).encode()
    # Page 2 (offset=2, limit=2): 2 items
    p2 = json.dumps({"data": [{"id": 3}, {"id": 4}]}).encode()
    # Page 3 (offset=4, limit=2): 1 item (endpoint exhausted)
    p3 = json.dumps({"data": [{"id": 5}]}).encode()

    mock_client.get.side_effect = [
        FetchResult(url="https://api.example.org/items?offset=0&limit=2", status_code=200, content=p1, text=p1.decode(), headers={"content-type": "application/json"}),
        FetchResult(url="https://api.example.org/items?offset=2&limit=2", status_code=200, content=p2, text=p2.decode(), headers={"content-type": "application/json"}),
        FetchResult(url="https://api.example.org/items?offset=4&limit=2", status_code=200, content=p3, text=p3.decode(), headers={"content-type": "application/json"}),
    ]

    config = PaginationConfig(
        strategy=PaginationStrategy.OFFSET_LIMIT,
        page_size=2,
        max_pages=10,
    )
    paginator = BoundedPaginator(
        source_id="test_source",
        base_url="https://api.example.org/items",
        config=config,
        http_client=mock_client,
        allowed_domains=["api.example.org"],
    )

    pages = list(paginator.iter_pages())
    assert len(pages) == 3

    all_ids = [item["id"] for page in pages for item in page.items]
    assert all_ids == [1, 2, 3, 4, 5]
    assert pages[0].has_more is True
    assert pages[1].has_more is True
    assert pages[2].has_more is False


def test_bounded_pagination_cursor_strategy() -> None:
    """Test cursor-based pagination advancing tokens until exhaustion."""
    mock_client = MagicMock()

    p1 = json.dumps({"items": [{"val": "a"}], "next_token": "cursor_b"}).encode()
    p2 = json.dumps({"items": [{"val": "b"}], "next_token": None}).encode()

    mock_client.get.side_effect = [
        FetchResult(url="https://api.example.org/records", status_code=200, content=p1, text=p1.decode(), headers={"content-type": "application/json"}),
        FetchResult(url="https://api.example.org/records?cursor=cursor_b", status_code=200, content=p2, text=p2.decode(), headers={"content-type": "application/json"}),
    ]

    config = PaginationConfig(
        strategy=PaginationStrategy.CURSOR,
        cursor_param="cursor",
        cursor_json_path="next_token",
    )
    paginator = BoundedPaginator(
        source_id="test_source",
        base_url="https://api.example.org/records",
        config=config,
        http_client=mock_client,
        allowed_domains=["api.example.org"],
    )

    pages = list(paginator.iter_pages())
    assert len(pages) == 2
    assert [p.items[0]["val"] for p in pages] == ["a", "b"]
    assert pages[1].has_more is False


def test_bounded_pagination_enforces_max_pages() -> None:
    """Verify paginator stops when max_pages ceiling is reached."""
    mock_client = MagicMock()

    # Infinite pages with 10 items each
    content = json.dumps({"data": [{"id": i} for i in range(10)]}).encode()
    mock_client.get.return_value = FetchResult(
        url="https://api.example.org/feed",
        status_code=200,
        content=content,
        text=content.decode(),
        headers={"content-type": "application/json"},
    )

    config = PaginationConfig(
        strategy=PaginationStrategy.PAGE_NUMBER,
        page_size=10,
        max_pages=3,  # Strict ceiling
    )
    paginator = BoundedPaginator(
        source_id="test_source",
        base_url="https://api.example.org/feed",
        config=config,
        http_client=mock_client,
        allowed_domains=["api.example.org"],
    )

    pages = list(paginator.iter_pages())
    assert len(pages) == 3
    assert mock_client.get.call_count == 3


def test_pagination_infinite_loop_detection() -> None:
    """Detect broken upstream endpoints returning the exact same page URL or cursor."""
    mock_client = MagicMock()

    content = json.dumps({"data": [{"id": 1}], "next_cursor": "same_cursor"}).encode()
    mock_client.get.return_value = FetchResult(
        url="https://api.example.org/loop?cursor=same_cursor",
        status_code=200,
        content=content,
        text=content.decode(),
        headers={"content-type": "application/json"},
    )

    config = PaginationConfig(
        strategy=PaginationStrategy.CURSOR,
        cursor_param="cursor",
        cursor_json_path="next_cursor",
    )
    paginator = BoundedPaginator(
        source_id="test_source",
        base_url="https://api.example.org/loop",
        config=config,
        http_client=mock_client,
        allowed_domains=["api.example.org"],
    )

    with pytest.raises(PolicyStop, match="pagination_infinite_loop_detected"):
        list(paginator.iter_pages())


def test_pagination_resumes_from_checkpoint_without_duplicates_or_gaps() -> None:
    """Simulate transient failure (429 or 503) and prove exact resume from checkpoint."""
    store = InMemoryCheckpointStore()
    mock_client = MagicMock()

    # Session 1: Page 1 succeeds, Page 2 fails with 503
    p1 = json.dumps({"data": [{"id": "item_1"}, {"id": "item_2"}]}).encode()

    mock_client.get.side_effect = [
        FetchResult(url="https://api.example.org/v1/data?offset=0&limit=2", status_code=200, content=p1, text=p1.decode(), headers={"content-type": "application/json"}),
        FetchResult(url="https://api.example.org/v1/data?offset=2&limit=2", status_code=503, content=b"Service Unavailable", text="Service Unavailable", headers={}),
    ]

    config = PaginationConfig(
        strategy=PaginationStrategy.OFFSET_LIMIT,
        page_size=2,
    )
    pag1 = BoundedPaginator(
        source_id="wb_rtfp",
        base_url="https://api.example.org/v1/data",
        config=config,
        http_client=mock_client,
        checkpoint_store=store,
        partition_key="2026-01",
        allowed_domains=["api.example.org"],
    )

    collected_session1 = []
    try:
        for page in pag1.iter_pages():
            collected_session1.extend([i["id"] for i in page.items])
    except PolicyStop as exc:
        assert "503" in str(exc)

    assert collected_session1 == ["item_1", "item_2"]

    # Verify checkpoint stored offset=2 and status='failed'
    cp = store.get("wb_rtfp", "2026-01")
    assert cp is not None
    assert cp.cursor_value == "2"
    assert cp.status == "failed"
    assert cp.items_collected == 2

    # Session 2: Resumes at offset=2, processes Page 2 and Page 3 (final)
    p2 = json.dumps({"data": [{"id": "item_3"}, {"id": "item_4"}]}).encode()
    p3 = json.dumps({"data": [{"id": "item_5"}]}).encode()

    mock_client.reset_mock()
    mock_client.get.side_effect = [
        FetchResult(url="https://api.example.org/v1/data?offset=2&limit=2", status_code=200, content=p2, text=p2.decode(), headers={"content-type": "application/json"}),
        FetchResult(url="https://api.example.org/v1/data?offset=4&limit=2", status_code=200, content=p3, text=p3.decode(), headers={"content-type": "application/json"}),
    ]

    pag2 = BoundedPaginator(
        source_id="wb_rtfp",
        base_url="https://api.example.org/v1/data",
        config=config,
        http_client=mock_client,
        checkpoint_store=store,
        partition_key="2026-01",
        allowed_domains=["api.example.org"],
    )

    collected_session2 = []
    for page in pag2.iter_pages():
        collected_session2.extend([i["id"] for i in page.items])

    # Verified: Started directly from item_3, no duplicates of item_1 or item_2
    assert collected_session2 == ["item_3", "item_4", "item_5"]

    # Final checkpoint is completed
    cp_final = store.get("wb_rtfp", "2026-01")
    assert cp_final is not None
    assert cp_final.status == "completed"
    assert cp_final.items_collected == 5


def test_controlled_streaming_enforces_content_length_limit() -> None:
    """Pre-check Content-Length header to abort multi-gigabyte files before downloading bytes."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Length": "104857600", "Content-Type": "application/zip"}  # 100 MiB
    mock_client.send.return_value = mock_resp

    reader = ControlledStreamReader(
        config=StreamConfig(max_bytes=10 * 1024 * 1024)  # 10 MiB limit
    )

    with pytest.raises(PolicyStop, match="http_content_length_exceeds_limit"):
        reader.stream_url(mock_client, "https://example.org/huge_archive.zip")


def test_controlled_streaming_enforces_chunk_size_ceiling() -> None:
    """Stream without Content-Length header and abort immediately when chunk ceiling is crossed."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/octet-stream"}
    # Emits 3 chunks of 1 KiB
    mock_resp.iter_bytes.return_value = [b"x" * 1024, b"y" * 1024, b"z" * 1024]
    mock_client.send.return_value = mock_resp

    # Limit to 2 KiB (2048 bytes)
    reader = ControlledStreamReader(
        config=StreamConfig(max_bytes=2048, chunk_size=1024, verify_content_length=False)
    )

    with pytest.raises(PolicyStop, match="http_stream_size_exceeds_limit"):
        reader.stream_url(mock_client, "https://example.org/stream")


def test_controlled_streaming_calculates_sha256_accurately() -> None:
    """Accurately compute SHA-256 digest on the fly without second pass."""
    payload = b"Hello, Ketrika DataOps Autonomous Collection!"
    expected_sha256 = hashlib.sha256(payload).hexdigest()

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Length": str(len(payload)), "Content-Type": "text/plain", "ETag": '"abc123"'}
    mock_resp.iter_bytes.return_value = [payload[:10], payload[10:]]
    mock_client.send.return_value = mock_resp

    reader = ControlledStreamReader()
    result = reader.stream_url(mock_client, "https://example.org/dataset.csv")

    assert result.content == payload
    assert result.content_sha256 == expected_sha256
    assert result.bytes_downloaded == len(payload)
    assert result.mime_type == "text/plain"
    assert result.etag == '"abc123"'


def test_sanitize_url_for_logging() -> None:
    """Ensure sensitive API keys, bearer tokens and passwords are redacted from log URLs."""
    url = "https://data.gov.mg/api/v2/prices?api_key=SECRET_XYZ_999&token=eyJhbGciOiJIUzI1NiJ9&page=3&format=json"
    sanitized = sanitize_url_for_logging(url)

    assert "SECRET_XYZ_999" not in sanitized
    assert "eyJhbGci" not in sanitized
    assert "api_key=REDACTED" in sanitized
    assert "token=REDACTED" in sanitized
    assert "page=3" in sanitized
    assert "format=json" in sanitized


def test_sql_checkpoint_store_persistence() -> None:
    """Test SqlCheckpointStore upsert, get, advance, and reset."""
    from ketrika.connectors.adapters.checkpoint import SqlCheckpointStore
    from ketrika.core.db import get_engine

    engine = get_engine()
    store = SqlCheckpointStore(engine)

    # Use existing source 'wb_rtfp_mdg' from registry
    source_id = "wb_rtfp_mdg"
    pkey = "test_partition_2026_01"

    try:
        # 1. Clean start
        store.reset(source_id, pkey)
        assert store.get(source_id, pkey) is None

        # 2. Save initial checkpoint
        cp = CollectionCheckpoint(
            source_id=source_id,
            partition_key=pkey,
            cursor_value="100",
            cursor_type="offset",
            items_collected=100,
            bytes_downloaded=50000,
            status="in_progress",
            metadata={"source_format": "json"},
        )
        store.save(cp)

        # 3. Read back
        loaded = store.get(source_id, pkey)
        assert loaded is not None
        assert loaded.source_id == source_id
        assert loaded.cursor_value == "100"
        assert loaded.items_collected == 100
        assert loaded.metadata.get("source_format") == "json"

        # 4. Advance
        loaded.advance(new_cursor="200", new_items=100, new_bytes=48000, etag='"etag999"')
        store.save(loaded)

        advanced = store.get(source_id, pkey)
        assert advanced is not None
        assert advanced.cursor_value == "200"
        assert advanced.items_collected == 200
        assert advanced.etag == '"etag999"'
    finally:
        store.reset(source_id, pkey)
