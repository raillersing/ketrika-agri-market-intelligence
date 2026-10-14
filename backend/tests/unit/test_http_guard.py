"""Real HTTPX inert transports exercise every guarded wire path."""

from datetime import UTC, datetime
from email.utils import format_datetime

import httpx
import pytest
from tenacity import wait_none

from ketrika.core.http import PoliteHttpClient, retry_after_delay
from ketrika.core.http_budget import MemoryBudgetBackend
from ketrika.core.policy import OfflineError, PolicyEngine, PolicyStop

NOW = datetime(2026, 10, 14, tzinfo=UTC)


def make_client(handler, budget=None, policy=None):
    client = PoliteHttpClient(
        policy_engine=policy or PolicyEngine(),
        budget_backend=budget or MemoryBudgetBackend(),
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
        sleep=lambda _: None,
    )
    client.bind_source("fixture_http_guard", 500, 5)
    return client


def allow(client, origin="https://example.invalid"):
    client.policy.set_robots_txt(origin, "User-agent: *\nDisallow:\n")


def test_robots_and_document_each_consume_admission():
    requests = []
    with make_client(lambda request: requests.append(request) or httpx.Response(404)) as client:
        assert client.get("https://example.invalid/data").status_code == 404
        assert [request.url.path for request in requests] == ["/robots.txt", "/data"]
        assert set(client.budget.counts.values()) == {2}


def test_quota_zero_prevents_even_robots():
    requests = []
    with make_client(lambda request: requests.append(request) or httpx.Response(200)) as client:
        client.bind_source("fixture_http_guard", 0, 5)
        with pytest.raises(PolicyStop, match="exhausted"):
            client.get("https://example.invalid/data")
    assert requests == []


@pytest.mark.parametrize("status", [401, 403, 302, 503])
def test_challenge_stops_before_redirect_or_retry_and_survives_new_client(status):
    requests = []
    budget = MemoryBudgetBackend()

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status, headers={"Location": "https://other.invalid/data"}, text="CAPTCHA"
        )

    with make_client(handler, budget) as client:
        allow(client)
        with pytest.raises(PolicyStop, match="Challenge"):
            client.get("https://example.invalid/data")
    with make_client(handler, budget) as restarted:
        allow(restarted)
        with pytest.raises(PolicyStop, match="disabled"):
            restarted.get("https://example.invalid/data")
    assert len(requests) == 1


def test_direct_low_level_call_cannot_bypass_robots():
    requests = []
    with make_client(lambda request: requests.append(request) or httpx.Response(200)) as client:
        client.policy.set_robots_txt("https://example.invalid", "User-agent: *\nDisallow: /\n")
        with pytest.raises(PolicyStop, match="disallowed"):
            client._execute_request("GET", "https://example.invalid/data")
    assert requests == []


def test_httpx_automatic_redirect_configuration_is_overridden():
    requests = []

    def handle(request):
        requests.append(request)
        return (
            httpx.Response(302, headers={"Location": "/next"})
            if request.url.path == "/data"
            else httpx.Response(200)
        )

    with make_client(handle) as client:
        allow(client)
        client._client.follow_redirects = True
        assert client.get("https://example.invalid/data").status_code == 200
        assert set(client.budget.counts.values()) == {2}
    assert len(requests) == 2


def test_cross_origin_strips_merged_defaults_auth_cookie_and_conditions():
    requests = []

    def handle(request):
        requests.append(request)
        return (
            httpx.Response(302, headers={"Location": "https://other.invalid/next"})
            if request.url.host == "example.invalid"
            else httpx.Response(200)
        )

    with make_client(handle) as client:
        allow(client)
        allow(client, "https://other.invalid")
        client._client.headers["aUtHoRiZaTiOn"] = "private"
        client._client.headers["Cookie"] = "private=1"
        client.get(
            "https://example.invalid/data",
            headers={"If-None-Match": "private", "User-Agent": "browser"},
        )
        assert requests[0].headers["Authorization"] == "private"
        for header in ("authorization", "cookie", "if-none-match"):
            assert header not in requests[1].headers
        assert all(
            request.headers.get_list("User-Agent") == [client.user_agent] for request in requests
        )


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/data",
        "ftp://example.invalid/data",
        "https://user:secret@example.invalid/data",
        "https://example.invalid:bad/data",
    ],
)
def test_unsafe_urls_emit_nothing(url):
    requests = []
    with make_client(lambda request: requests.append(request) or httpx.Response(200)) as client:
        with pytest.raises(PolicyStop):
            client.get(url)
    assert not requests


@pytest.mark.parametrize(
    "option",
    [
        {"follow_redirects": True},
        {"extensions": {}},
        {"auth": ("user", "secret")},
        {"auto_robots": False},
    ],
)
def test_unsafe_options_emit_nothing(option):
    requests = []
    with make_client(lambda request: requests.append(request) or httpx.Response(200)) as client:
        with pytest.raises(PolicyStop):
            client.get("https://example.invalid/data", **option)
    assert not requests


def test_offline_prevents_robots_and_admission(monkeypatch):
    requests = []
    monkeypatch.setenv("HTTP_OFFLINE", "1")
    with make_client(lambda request: requests.append(request) or httpx.Response(200)) as client:
        with pytest.raises(OfflineError):
            client.get("https://example.invalid/data")
        assert not client.budget.counts
    assert not requests


def test_retry_counts_each_network_attempt_and_stops_at_quota():
    requests = []

    def handle(request):
        requests.append(request)
        raise httpx.ReadTimeout("inert", request=request)

    with make_client(handle) as client:
        allow(client)
        client.bind_source("fixture_http_guard", 1, 5)
        execute = client._execute_request.retry_with(wait=wait_none())
        with pytest.raises(PolicyStop, match="exhausted"):
            execute(client, "GET", "https://example.invalid/data")
    assert len(requests) == 1


@pytest.mark.parametrize("value", ["nan", "inf", "-1", "0.2", "nonsense"])
def test_invalid_retry_after_rejected(value):
    with pytest.raises(PolicyStop, match="invalid_retry_after"):
        retry_after_delay(value, NOW)


def test_retry_after_date_and_local_ceiling():
    assert retry_after_delay("3", NOW) == 3
    assert retry_after_delay(format_datetime(NOW.replace(second=4), usegmt=True), NOW) == 4
    with pytest.raises(PolicyStop, match="exceeds_local_wait"):
        retry_after_delay("301", NOW)


def test_robots_origins_not_shared_and_unknown_denied():
    policy = PolicyEngine()
    policy.set_robots_txt("https://example.invalid", "User-agent: *\nDisallow:\n")
    assert policy.is_allowed_by_robots("https://example.invalid/data")
    assert not policy.is_allowed_by_robots("http://example.invalid/data")
    assert not policy.is_allowed_by_robots("https://example.invalid:444/data")


@pytest.mark.parametrize("status", [500, 400, 204])
def test_robots_error_never_allows_document(status):
    requests = []
    with make_client(lambda request: requests.append(request) or httpx.Response(status)) as client:
        with pytest.raises(PolicyStop, match="robots_unavailable"):
            client.get("https://example.invalid/data")
    assert [request.url.path for request in requests] == ["/robots.txt"]


def test_acquired_robots_denial_blocks_document():
    requests = []
    with make_client(
        lambda request: (
            requests.append(request) or httpx.Response(200, text="User-agent: *\nDisallow: /data\n")
        )
    ) as client:
        with pytest.raises(PolicyStop, match="disallowed"):
            client.get("https://example.invalid/data")
    assert [request.url.path for request in requests] == ["/robots.txt"]


def test_stop_during_pacing_wait_prevents_emission():
    requests = []
    budget = MemoryBudgetBackend()
    with make_client(
        lambda request: requests.append(request) or httpx.Response(200), budget
    ) as client:
        allow(client)
        client.get("https://example.invalid/data")
        client._sleep = lambda _: budget.stop(client.source_id, "https://example.invalid", 403)
        with pytest.raises(PolicyStop, match="disabled"):
            client.get("https://example.invalid/data")
    assert len(requests) == 1


@pytest.mark.parametrize("rate", [0, -1, float("nan"), float("inf")])
def test_invalid_caller_rate_cannot_hide_behind_registry_rate(rate):
    requests = []
    with make_client(lambda request: requests.append(request) or httpx.Response(200)) as client:
        with pytest.raises(PolicyStop, match="invalid_rate"):
            client.get("https://example.invalid/data", max_rps=rate)
    assert not requests


def test_redirect_loop_ceiling_is_explicit_and_every_hop_counted():
    requests = []
    with make_client(
        lambda request: (
            requests.append(request) or httpx.Response(302, headers={"Location": "/loop"})
        )
    ) as client:
        allow(client)
        with pytest.raises(PolicyStop, match="redirect_limit"):
            client.get("https://example.invalid/data")
        assert set(client.budget.counts.values()) == {11}
    assert len(requests) == 11


def test_robots_fetch_does_not_leak_shared_default_credentials():
    requests = []
    with make_client(lambda request: requests.append(request) or httpx.Response(404)) as client:
        client._client.headers["Authorization"] = "private"
        client._client.headers["Cookie"] = "private=1"
        client.fetch_robots_txt("https://other.invalid")
    assert len(requests) == 1
    assert "authorization" not in requests[0].headers and "cookie" not in requests[0].headers


def test_registered_source_limits_are_bound_before_any_wire(monkeypatch):
    from types import SimpleNamespace

    from ketrika.connectors.base import RunContext
    from ketrika.connectors.stages import authorize_collection

    requests = []
    definition = SimpleNamespace(
        status="active", crawl_permission="public_open_data", daily_request_budget=1, max_rps=0.2
    )
    monkeypatch.setattr("ketrika.connectors.stages.get_source", lambda _: definition)
    with make_client(lambda request: requests.append(request) or httpx.Response(404)) as client:
        ctx = RunContext(source_id=client.source_id, http_client=client)
        authorize_collection(SimpleNamespace(source_id=client.source_id), ctx)
        assert client.source_limit == 1 and client.source_rate == 0.2
        with pytest.raises(PolicyStop, match="exhausted"):
            client.get("https://example.invalid/data", max_rps=100)
    assert [request.url.path for request in requests] == ["/robots.txt"]


def test_304_without_known_artifact_never_writes_empty_bronze():
    from unittest.mock import MagicMock

    from ketrika.connectors.base import DiscoveredItem, RunContext

    with make_client(lambda _: httpx.Response(304)) as client:
        allow(client)
        store = MagicMock()
        ctx = RunContext(source_id=client.source_id, http_client=client, bronze_store=store)
        with pytest.raises(PolicyStop, match="not_modified_without_known_artifact"):
            ctx.fetch_and_store(DiscoveredItem("https://example.invalid/data"))
        store.put.assert_not_called()
