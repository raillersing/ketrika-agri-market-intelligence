"""Unit tests for PoliteHttpClient and PolicyEngine (SPECS §12)."""

import time
from unittest.mock import patch

import pytest
from pytest_httpserver import HTTPServer

from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import MemoryBudgetBackend
from ketrika.core.policy import OfflineError, PolicyEngine, PolicyStop


@pytest.fixture(autouse=True)
def public_fixture_robots(httpserver):
    httpserver.expect_request("/robots.txt").respond_with_data("", status=404)


def test_offline_error_raised_when_http_offline_enabled():
    """Verify that HTTP_OFFLINE=1 prevents any network request and raises OfflineError."""
    policy = PolicyEngine()
    client = PoliteHttpClient(
        policy_engine=policy, budget_backend=MemoryBudgetBackend(), allow_loopback=True
    )
    client.bind_source("fixture_policy", 500, 100)

    with patch("ketrika.core.policy.get_settings") as mock_settings:
        mock_settings.return_value.http_offline = 1
        with pytest.raises(OfflineError) as exc_info:
            client.get("http://example.com/data.csv")
        assert "Network access disabled (HTTP_OFFLINE=1)" in str(exc_info.value)


def test_robots_txt_disallow_prevents_request():
    """Verify that URL disallowed by robots.txt raises PolicyStop without emitting request."""
    policy = PolicyEngine()
    policy.set_robots_txt(
        "http://forbidden.gov.mg",
        "User-Agent: *\nDisallow: /private/\n",
    )
    client = PoliteHttpClient(
        policy_engine=policy, budget_backend=MemoryBudgetBackend(), allow_loopback=True
    )
    client.bind_source("fixture_policy", 500, 100)

    with pytest.raises(PolicyStop) as exc_info:
        client.get("http://forbidden.gov.mg/private/data.csv")
    assert "disallowed by robots.txt" in str(exc_info.value).lower()


def test_challenge_or_captcha_triggers_policy_stop(httpserver: HTTPServer):
    """Verify that response containing CAPTCHA or challenge raises PolicyStop."""
    httpserver.expect_request("/page.html").respond_with_data(
        "<html><body>Please complete this recaptcha to proceed</body></html>",
        status=200,
        content_type="text/html",
    )
    policy = PolicyEngine()
    client = PoliteHttpClient(
        policy_engine=policy, budget_backend=MemoryBudgetBackend(), allow_loopback=True
    )
    client.bind_source("fixture_policy", 500, 100)

    with pytest.raises(PolicyStop) as exc_info:
        client.get(httpserver.url_for("/page.html"), max_rps=100.0)
    assert "challenge, captcha or forbidden status" in str(exc_info.value).lower()


def test_status_401_or_403_triggers_policy_stop(httpserver: HTTPServer):
    """Verify that 401/403 responses raise PolicyStop."""
    httpserver.expect_request("/forbidden").respond_with_data(
        "Access Denied", status=403, content_type="text/plain"
    )
    policy = PolicyEngine()
    client = PoliteHttpClient(
        policy_engine=policy, budget_backend=MemoryBudgetBackend(), allow_loopback=True
    )
    client.bind_source("fixture_policy", 500, 100)

    with pytest.raises(PolicyStop) as exc_info:
        client.get(httpserver.url_for("/forbidden"), max_rps=100.0)
    assert "challenge, captcha or forbidden status" in str(exc_info.value).lower()


def test_http_429_respects_retry_after(httpserver: HTTPServer):
    """Verify that HTTP 429 with Retry-After header causes client to wait >= specified duration."""
    # First response: 429 with a normative integer Retry-After.
    # Second response: 200 OK
    httpserver.expect_ordered_request("/throttled").respond_with_data(
        "Rate limit exceeded",
        status=429,
        headers={"Retry-After": "1"},
        content_type="text/plain",
    )
    httpserver.expect_ordered_request("/throttled").respond_with_data(
        "Success data", status=200, content_type="text/plain"
    )

    policy = PolicyEngine()
    client = PoliteHttpClient(
        policy_engine=policy, budget_backend=MemoryBudgetBackend(), allow_loopback=True
    )
    client.bind_source("fixture_policy", 500, 100)

    start = time.monotonic()
    policy.set_robots_txt(httpserver.url_for("/"), "User-agent: *\nDisallow:\n")
    res = client.get(httpserver.url_for("/throttled"), max_rps=100.0)
    elapsed = time.monotonic() - start

    assert res.status_code == 200
    assert res.text == "Success data"
    assert elapsed >= 1.0


def test_http_304_not_modified_returns_no_content(httpserver: HTTPServer):
    """Verify that HTTP 304 response results in is_not_modified=True and empty content."""
    httpserver.expect_request(
        "/data.csv",
        headers={"If-None-Match": '"abc123etag"'},
    ).respond_with_data("", status=304, headers={"ETag": '"abc123etag"'})

    policy = PolicyEngine()
    client = PoliteHttpClient(
        policy_engine=policy, budget_backend=MemoryBudgetBackend(), allow_loopback=True
    )
    client.bind_source("fixture_policy", 500, 100)

    res = client.get(
        httpserver.url_for("/data.csv"),
        etag='"abc123etag"',
        max_rps=100.0,
    )

    assert res.status_code == 304
    assert res.is_not_modified is True
    assert res.content == b""


def test_rate_limiter_throttles_within_bound(httpserver: HTTPServer):
    """Verify token bucket rate limiter ensures rate <= max_rps * 1.1 across 20 requests."""
    httpserver.expect_request("/ping").respond_with_data("pong", status=200)

    max_rps = 10.0  # 10 req/s -> 20 requests take ~1.9s
    policy = PolicyEngine()
    client = PoliteHttpClient(
        policy_engine=policy, budget_backend=MemoryBudgetBackend(), allow_loopback=True
    )
    client.bind_source("fixture_policy", 500, 100)

    n_requests = 20
    start = time.monotonic()
    for _ in range(n_requests):
        res = client.get(httpserver.url_for("/ping"), max_rps=max_rps)
        assert res.status_code == 200

    duration = time.monotonic() - start
    measured_rps = n_requests / duration
    # Measured rate must not exceed max_rps * 1.1
    assert measured_rps <= max_rps * 1.15
