"""Real HTTPX request construction on inert transports, no public collection."""

from unittest.mock import MagicMock

import httpx
import pytest
from tenacity import wait_none

from ketrika.core.http import PoliteHttpClient
from ketrika.core.policy import PolicyEngine


@pytest.mark.parametrize(
    "headers",
    [
        None,
        {"User-Agent": "Mozilla/5.0"},
        {"user-agent": "browser"},
        {"USER-AGENT": "browser"},
        {"User-Agent": "one", "user-agent": "two"},
    ],
)
def test_custom_headers_cannot_replace_mandatory_bot_identity(headers):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, content=b"fixture")

    with PoliteHttpClient() as client:
        client._client.close()
        client._client = httpx.Client(
            transport=httpx.MockTransport(handle), headers={"User-Agent": "wrong-default"}
        )
        supplied = dict(headers or {})
        supplied["If-None-Match"] = '"fixture-etag"'
        original = dict(supplied)
        response = client._execute_request(
            "GET", "https://example.invalid/fixture", headers=supplied
        )
        assert response.status_code == 200 and len(requests) == 1
        assert requests[0].headers.get_list("User-Agent") == [client.user_agent]
        assert requests[0].headers["If-None-Match"] == '"fixture-etag"'
        assert supplied == original


def test_mandatory_identity_survives_network_retry():
    requests = []

    def handle(request):
        requests.append(request)
        if len(requests) == 1:
            raise httpx.ReadTimeout("inert timeout", request=request)
        return httpx.Response(200, content=b"fixture")

    with PoliteHttpClient() as client:
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(handle))
        request = client._execute_request.retry_with(wait=wait_none())
        response = request(
            client, "GET", "https://example.invalid/fixture", headers={"user-agent": "browser"}
        )
        assert response.status_code == 200 and len(requests) == 2
        assert all(item.headers.get_list("User-Agent") == [client.user_agent] for item in requests)


def test_mandatory_identity_survives_httpx_redirect():
    requests = []

    def handle(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(302, headers={"Location": "/next"})
        return httpx.Response(200, content=b"fixture")

    with PoliteHttpClient() as client:
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(handle), follow_redirects=True)
        response = client._execute_request(
            "GET", "https://example.invalid/fixture", headers={"User-Agent": "browser"}
        )
        assert response.status_code == 200 and len(requests) == 2
        assert all(item.headers.get_list("User-Agent") == [client.user_agent] for item in requests)


@pytest.mark.parametrize("first_status", [200, 304, 429])
def test_public_get_preserves_identity_and_conditional_headers(first_status):
    requests = []
    policy = MagicMock(spec=PolicyEngine)

    def handle(request):
        requests.append(request)
        status = first_status if len(requests) == 1 else 200
        headers = {"Retry-After": "0"} if status == 429 else {}
        return httpx.Response(status, headers=headers, content=b"fixture")

    with PoliteHttpClient(policy_engine=policy) as client:
        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(handle))
        response = client.get(
            "https://example.invalid/fixture",
            etag='"fixture-etag"',
            last_modified="Mon, 01 Jan 2024 00:00:00 GMT",
            headers={"user-agent": "browser", "Accept": "text/csv"},
        )
        assert response.status_code == (304 if first_status == 304 else 200)
        assert response.is_not_modified is (first_status == 304)
        assert len(requests) == (2 if first_status == 429 else 1)
        policy.check_pre_fetch.assert_called_once_with(
            "https://example.invalid/fixture", max_rps=None
        )
        for request in requests:
            assert request.headers.get_list("User-Agent") == [client.user_agent]
            assert request.headers["If-None-Match"] == '"fixture-etag"'
            assert request.headers["If-Modified-Since"] == "Mon, 01 Jan 2024 00:00:00 GMT"
            assert request.headers["Accept"] == "text/csv"
