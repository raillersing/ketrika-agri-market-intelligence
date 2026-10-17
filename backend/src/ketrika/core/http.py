"""One admission per wire attempt, explicit redirects and durable policy stops."""

from __future__ import annotations

import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from tenacity import RetryCallState, retry, retry_if_exception_type, stop_after_attempt
from tenacity.wait import wait_exponential_jitter

from ketrika.core.db import get_engine
from ketrika.core.http_budget import Admission, BudgetBackend, SqlBudgetBackend
from ketrika.core.policy import (
    PolicyEngine,
    PolicyStop,
    canonical_origin,
    detect_challenge,
    get_policy_engine,
    validate_candidate_url,
)
from ketrika.core.settings import get_settings


@dataclass
class FetchResult:
    url: str
    status_code: int
    content: bytes
    text: str
    headers: dict[str, str]
    etag: str | None = None
    last_modified: str | None = None
    is_not_modified: bool = False


class RetryableStatus(Exception):
    def __init__(self, response: httpx.Response, delay: float) -> None:
        self.response, self.delay = response, delay
        super().__init__("http_transient_status")


def retry_after_delay(value: str | None, now: datetime) -> float:
    if not value:
        return 0.0
    try:
        if value.isascii() and value.isdigit():
            delay = float(int(value))
        else:
            target = parsedate_to_datetime(value)
            if target.tzinfo is None:
                raise ValueError("timezone")
            delay = max(0.0, (target.astimezone(UTC) - now.astimezone(UTC)).total_seconds())
    except (ValueError, TypeError, OverflowError):
        raise PolicyStop("http_invalid_retry_after") from None
    if delay > 300:
        raise PolicyStop("http_retry_after_exceeds_local_wait")
    return delay


def _retry_wait(state: RetryCallState) -> float:
    backoff = float(wait_exponential_jitter(initial=2, max=300)(state))
    error = state.outcome.exception() if state.outcome else None
    return max(backoff, error.delay if isinstance(error, RetryableStatus) else 0.0)


class PoliteHttpClient:
    def __init__(
        self,
        policy_engine: PolicyEngine | None = None,
        timeout: float = 60.0,
        connect_timeout: float = 10.0,
        *,
        budget_backend: BudgetBackend | None = None,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        allow_loopback: bool | None = None,
    ) -> None:
        self.policy = policy_engine or get_policy_engine()
        self.budget = (
            budget_backend if budget_backend is not None else SqlBudgetBackend(get_engine())
        )
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sleep = sleep
        self.allow_loopback = (
            allow_loopback
            if allow_loopback is not None
            else (os.environ.get("KETRIKA_ALLOW_TEST_LOOPBACK", "") in ("1", "true", "True"))
        )
        settings = get_settings()
        self.user_agent = f"{settings.bot_user_agent}; {settings.bot_contact_email}"
        self.timeout = httpx.Timeout(timeout, connect=connect_timeout)
        self._client = httpx.Client(
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent},
            follow_redirects=False,
            transport=transport,
        )
        self.source_id = "unbound"
        self.source_limit = 500
        self.source_rate: float | None = None
        self._stopped = False
        self._robots_token = object()

    def bind_source(self, source_id: str, daily_request_budget: int, max_rps: float) -> None:
        if self.source_id != "unbound" and self.source_id != source_id:
            raise PolicyStop("http_source_binding_mismatch")
        Admission(
            source_id,
            "validation.invalid",
            "https://validation.invalid",
            daily_request_budget,
            daily_request_budget,
            max_rps,
        ).validate()
        self.source_id = source_id
        self.source_limit = min(self.source_limit, daily_request_budget)
        self.source_rate = (
            min(self.source_rate, max_rps) if self.source_rate is not None else max_rps
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PoliteHttpClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def fetch_robots_txt(self, domain: str) -> None:
        origin = canonical_origin(domain if "://" in domain else "https://" + domain)
        if self.policy.has_robots_txt(origin):
            return
        response = self._execute_request("GET", origin + "/robots.txt", _robots=self._robots_token)
        if response.status_code in (404, 410):
            content = "User-agent: *\nDisallow:\n"
        elif response.status_code == 200:
            content = response.text
        else:
            raise PolicyStop("http_robots_unavailable")
        self.policy.set_robots_txt(origin, content)

    @retry(
        stop=stop_after_attempt(4),
        wait=_retry_wait,
        retry=retry_if_exception_type(
            (httpx.NetworkError, httpx.TimeoutException, RetryableStatus)
        ),
        reraise=True,
    )
    def _execute_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        max_rps: float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Every retry repeats admission; HTTPX redirect and auth flows disabled."""
        token = kwargs.pop("_robots", None)
        if token is not None and token is not self._robots_token:
            raise PolicyStop("http_unsafe_request_options")
        robots = token is self._robots_token
        if kwargs.pop("follow_redirects", False):
            raise PolicyStop("http_automatic_redirect_forbidden")
        if set(kwargs) - {"params", "timeout"}:
            raise PolicyStop("http_unsafe_request_options")
        current, original_origin = url, canonical_origin(url)
        if max_rps is not None and (not math.isfinite(max_rps) or max_rps <= 0):
            raise PolicyStop("http_invalid_rate")
        for hop in range(11):
            validate_candidate_url(current, allow_loopback=self.allow_loopback)
            origin = canonical_origin(current)
            if self._stopped:
                raise PolicyStop("http_source_disabled")
            self.policy.check_offline(current)
            self.budget.check(self.source_id, origin)
            if not robots:
                self.fetch_robots_txt(origin)
                self.policy.check_pre_fetch(current, max_rps=max_rps)
            domain = urlparse(current).hostname
            assert domain is not None
            rate = (
                self.source_rate
                if self.source_rate is not None
                else self.policy.get_domain_rate(domain)
            )
            if max_rps is not None:
                rate = min(rate, max_rps)
            admission = Admission(
                self.source_id,
                domain.lower(),
                origin,
                self.source_limit,
                min(500, self.source_limit),
                rate,
            )
            delay = self.budget.reserve(admission, self._clock())
            if delay:
                self._sleep(delay)
            self.policy.check_offline(current)
            self.budget.check(self.source_id, origin)
            request = self._client.build_request(method, current, headers=headers, **kwargs)
            if robots or origin != original_origin:
                for key in (
                    "authorization",
                    "proxy-authorization",
                    "cookie",
                    "x-api-key",
                    "api-key",
                    "apikey",
                    "x-auth-token",
                    "token",
                    "if-none-match",
                    "if-modified-since",
                ):
                    request.headers.pop(key, None)
            request.headers["User-Agent"] = self.user_agent
            response = self._client.send(request, auth=None, follow_redirects=False)
            if detect_challenge(response.text, response.status_code):
                self._stopped = True
                self.budget.stop(self.source_id, origin, response.status_code)
                raise PolicyStop("Challenge, CAPTCHA or forbidden status detected")
            if response.status_code in (301, 302, 303, 307, 308) and "location" in response.headers:
                if hop == 10:
                    raise PolicyStop("http_redirect_limit_exceeded")
                next_url = str(response.url.join(response.headers["location"]))
                validate_candidate_url(next_url, allow_loopback=self.allow_loopback)
                current = next_url
                kwargs.pop("params", None)
                continue
            if response.status_code in (429, 502, 503, 504):
                delay = retry_after_delay(
                    response.headers.get("Retry-After")
                    if response.status_code in (429, 503)
                    else None,
                    self._clock(),
                )
                raise RetryableStatus(response, delay)
            return response
        raise PolicyStop("http_redirect_limit_exceeded")

    def get(
        self,
        url: str,
        etag: str | None = None,
        last_modified: str | None = None,
        max_rps: float | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> FetchResult:
        req_headers = dict(headers or {})
        if etag:
            req_headers["If-None-Match"] = etag
        if last_modified:
            req_headers["If-Modified-Since"] = last_modified
        try:
            response = self._execute_request(
                "GET", url, headers=req_headers, max_rps=max_rps, **kwargs
            )
        except RetryableStatus as exc:
            response = exc.response
        not_modified = response.status_code == 304
        return FetchResult(
            url=str(response.url),
            status_code=response.status_code,
            content=b"" if not_modified else response.content,
            text="" if not_modified else response.text,
            headers=dict(response.headers),
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
            is_not_modified=not_modified,
        )
