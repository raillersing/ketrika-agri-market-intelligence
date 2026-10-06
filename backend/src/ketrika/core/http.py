"""Polite HTTP Client conforming to SPECS.md §12.

Features:
- Mandatory bot User-Agent with contact email
- Automatic robots.txt fetching and enforcement via Protego
- Domain rate limiting via TokenBucket
- Challenge and CAPTCHA detection -> PolicyStop
- Respect for 429 / 503 Retry-After headers
- Conditional requests (If-None-Match / If-Modified-Since) with 304 handling
- HTTP_OFFLINE=1 -> OfflineError
- Tenacity exponential backoff retries for transient network issues
"""

import time
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ketrika.core.policy import PolicyEngine, get_policy_engine
from ketrika.core.settings import get_settings


@dataclass
class FetchResult:
    """Wrapper for HTTP response."""

    url: str
    status_code: int
    content: bytes
    text: str
    headers: dict[str, str]
    etag: str | None = None
    last_modified: str | None = None
    is_not_modified: bool = False  # True on HTTP 304


class PoliteHttpClient:
    """HTTP client adhering to Ketrika scraping policies."""

    def __init__(
        self,
        policy_engine: PolicyEngine | None = None,
        timeout: float = 60.0,
        connect_timeout: float = 10.0,
    ) -> None:
        self.policy = policy_engine or get_policy_engine()
        self.timeout = httpx.Timeout(timeout, connect=connect_timeout)
        settings = get_settings()
        self.user_agent = f"{settings.bot_user_agent}; {settings.bot_contact_email}"
        self._client = httpx.Client(
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
        )

    def close(self) -> None:
        """Close underlying HTTP client session."""
        self._client.close()

    def __enter__(self) -> "PoliteHttpClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def fetch_robots_txt(self, domain: str) -> None:
        """Attempt to fetch and parse robots.txt for a domain if not already cached."""
        url = f"https://{domain}/robots.txt"
        try:
            resp = self._client.get(url, timeout=10.0)
            if resp.status_code == 200:
                self.policy.set_robots_txt(domain, resp.text)
        except Exception:
            # If robots.txt fails or unreachable, proceed with default permissions
            pass

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=2.0, max=60.0),
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        reraise=True,
    )
    def _execute_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute request with retries on network failures."""
        req_headers = {"User-Agent": self.user_agent}
        if headers:
            req_headers.update(headers)
        return self._client.request(method, url, headers=req_headers, **kwargs)

    def get(
        self,
        url: str,
        etag: str | None = None,
        last_modified: str | None = None,
        max_rps: float | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> FetchResult:
        """Fetch URL with full policy, rate limiting, and challenge checks."""
        # Check pre-fetch rules (offline, robots, rate limiting)
        self.policy.check_pre_fetch(url, max_rps=max_rps)

        # Prepare conditional headers if provided
        req_headers = dict(headers or {})
        if etag:
            req_headers["If-None-Match"] = etag
        if last_modified:
            req_headers["If-Modified-Since"] = last_modified

        resp = self._execute_request("GET", url, headers=req_headers, **kwargs)

        # Respect 429 and 503 Retry-After header
        if resp.status_code in (429, 503):
            retry_after_str = resp.headers.get("Retry-After")
            if retry_after_str:
                try:
                    delay = float(retry_after_str)
                    time.sleep(delay)
                    # Retry once after mandatory wait
                    resp = self._execute_request("GET", url, headers=req_headers, **kwargs)
                except ValueError:
                    pass

        # Handle HTTP 304 Not Modified
        if resp.status_code == 304:
            return FetchResult(
                url=url,
                status_code=304,
                content=b"",
                text="",
                headers=dict(resp.headers),
                etag=resp.headers.get("ETag"),
                last_modified=resp.headers.get("Last-Modified"),
                is_not_modified=True,
            )

        # Detect challenges and CAPTCHAs in response body
        text_content = resp.text
        self.policy.check_post_fetch(text_content, resp.status_code, url=url)

        return FetchResult(
            url=url,
            status_code=resp.status_code,
            content=resp.content,
            text=text_content,
            headers=dict(resp.headers),
            etag=resp.headers.get("ETag"),
            last_modified=resp.headers.get("Last-Modified"),
            is_not_modified=False,
        )
