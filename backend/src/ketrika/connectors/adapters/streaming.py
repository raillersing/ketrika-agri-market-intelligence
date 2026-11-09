"""Controlled streaming adapter with hard size limits and SHA-256 verification (IA-DATA-03).

Prevents out-of-memory errors and resource exhaustion attacks when acquiring
voluminous datasets, compressed ZIPs, or multi-gigabyte files.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from ketrika.core.policy import PolicyStop, validate_candidate_url


@dataclass(frozen=True)
class StreamConfig:
    """Configuration for controlled streaming."""

    max_bytes: int = 50 * 1024 * 1024  # 50 MiB default ceiling
    chunk_size: int = 64 * 1024  # 64 KiB reading chunk
    verify_content_length: bool = True


@dataclass(frozen=True)
class StreamResult:
    """Result of a controlled stream download."""

    content: bytes
    content_sha256: str
    bytes_downloaded: int
    mime_type: str
    etag: str | None = None
    last_modified: str | None = None


_SENSITIVE_PARAM_PATTERN = re.compile(
    r"(key|token|auth|secret|password|credential|bearer)", re.IGNORECASE
)


def sanitize_url_for_logging(url: str) -> str:
    """Mask sensitive query parameters (API keys, tokens) from logged URLs."""
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        params = parse_qsl(parsed.query, keep_blank_values=True)
        sanitized_params = []
        for k, v in params:
            if _SENSITIVE_PARAM_PATTERN.search(k):
                sanitized_params.append((k, "REDACTED"))
            else:
                sanitized_params.append((k, v))
        new_query = urlencode(sanitized_params)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return "[UNPARSEABLE_URL]"


class ControlledStreamReader:
    """Streams HTTP responses with strict ceiling bounds and on-the-fly hashing."""

    def __init__(
        self,
        config: StreamConfig | None = None,
        allow_loopback: bool = False,
    ) -> None:
        self.config = config or StreamConfig()
        self.allow_loopback = allow_loopback

    def stream_url(
        self,
        client: httpx.Client,
        url: str,
        headers: dict[str, str] | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
        **kwargs: Any,
    ) -> StreamResult:
        """Fetch URL with bounded streaming and on-the-fly SHA-256 calculation."""
        # 1. SSRF boundary protection
        validate_candidate_url(url, allow_loopback=self.allow_loopback)

        req_headers = dict(headers or {})
        if etag:
            req_headers["If-None-Match"] = etag
        if last_modified:
            req_headers["If-Modified-Since"] = last_modified

        req = client.build_request("GET", url, headers=req_headers, **kwargs)
        resp = client.send(req, stream=True)

        try:
            if resp.status_code == 304:
                return StreamResult(
                    content=b"",
                    content_sha256=hashlib.sha256(b"").hexdigest(),
                    bytes_downloaded=0,
                    mime_type=resp.headers.get("content-type", "application/octet-stream").split(";")[0].strip(),
                    etag=resp.headers.get("ETag"),
                    last_modified=resp.headers.get("Last-Modified"),
                )

            # 2. Pre-check Content-Length header
            if self.config.verify_content_length:
                content_len_hdr = resp.headers.get("content-length") or resp.headers.get("Content-Length")
                if content_len_hdr and str(content_len_hdr).isdigit():
                    content_len = int(content_len_hdr)
                    if content_len > self.config.max_bytes:
                        raise PolicyStop(
                            f"http_content_length_exceeds_limit: {content_len} > {self.config.max_bytes}"
                        )

            # 3. Stream chunks with hard ceiling enforcement
            hasher = hashlib.sha256()
            chunks: list[bytes] = []
            total_bytes = 0

            for chunk in resp.iter_bytes(chunk_size=self.config.chunk_size):
                if not chunk:
                    continue
                total_bytes += len(chunk)
                if total_bytes > self.config.max_bytes:
                    raise PolicyStop(
                        f"http_stream_size_exceeds_limit: exceeded ceiling of {self.config.max_bytes} bytes"
                    )
                hasher.update(chunk)
                chunks.append(chunk)

            full_content = b"".join(chunks)
            raw_mime = (
                resp.headers.get("content-type")
                or resp.headers.get("Content-Type")
                or "application/octet-stream"
            )
            mime_type = raw_mime.split(";")[0].strip()
            etag_val = resp.headers.get("etag") or resp.headers.get("ETag")
            last_mod_val = resp.headers.get("last-modified") or resp.headers.get("Last-Modified")

            return StreamResult(
                content=full_content,
                content_sha256=hasher.hexdigest(),
                bytes_downloaded=total_bytes,
                mime_type=mime_type,
                etag=etag_val,
                last_modified=last_mod_val,
            )
        finally:
            resp.close()
