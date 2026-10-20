"""Unit tests for edition discovery, bounded pagination, SSRF prevention and tracking (R1.2, C1)."""

from datetime import date

import pytest
from pytest_httpserver import HTTPServer

from ketrika.connectors.base import ParseResult
from ketrika.connectors.discovery import (
    CatalogDiscoveryEngine,
    DiscoveredEdition,
    DiscoveryResult,
    DiscoveryStatus,
    classify_ingestion_outcome,
)
from ketrika.connectors.records import PriceRecord
from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import MemoryBudgetBackend
from ketrika.core.policy import (
    PolicyEngine,
    PolicyStop,
    is_forbidden_network_target,
    validate_candidate_url,
)


@pytest.fixture(autouse=True)
def allow_fixture_loopback(monkeypatch: pytest.MonkeyPatch, httpserver: HTTPServer) -> None:
    """Allow loopback and register default robots.txt for local HTTPServer fixture calls."""
    monkeypatch.setenv("KETRIKA_ALLOW_TEST_LOOPBACK", "1")
    httpserver.expect_request("/robots.txt").respond_with_data(
        "User-agent: *\nDisallow:\n", status=200
    )


def test_ssrf_rejection_for_forbidden_targets() -> None:
    """Verify is_forbidden_network_target and validate_candidate_url reject SSRF targets."""
    forbidden_hosts = [
        "127.0.0.1",
        "127.0.0.2",
        "localhost",
        "sub.localhost",
        "169.254.169.254",  # AWS/GCP/Azure instance metadata
        "169.254.1.1",  # Link-local IPv4
        "10.0.0.1",  # RFC 1918 Class A
        "172.16.0.1",  # RFC 1918 Class B
        "192.168.1.1",  # RFC 1918 Class C
        "metadata.google.internal",
        "app.internal",
        "device.local",
        "::1",  # IPv6 loopback
    ]

    for host in forbidden_hosts:
        assert is_forbidden_network_target(host) is True, f"Host {host} should be forbidden"
        target = f"[{host}]" if ":" in host and not host.startswith("[") else host
        url = f"http://{target}/data"
        with pytest.raises(PolicyStop) as exc_info:
            validate_candidate_url(url, allow_loopback=False)
        assert "http_forbidden_destination_target" in str(exc_info.value)

    # Valid public hosts must pass
    allowed_hosts = [
        "www.agriculture.gov.mg",
        "data.humdata.org",
        "microdata.worldbank.org",
        "fenixservices.fao.org",
        "8.8.8.8",
    ]
    for host in allowed_hosts:
        assert is_forbidden_network_target(host) is False, f"Host {host} should be allowed"
        url = f"https://{host}/dataset"
        assert validate_candidate_url(url, allow_loopback=False) == url


def test_domain_whitelist_enforcement() -> None:
    """Verify validate_candidate_url enforces allowed_domains whitelist."""
    allowed = ["gov.mg", "fao.org"]

    valid_urls = [
        "http://www.commerce.gov.mg/ppn/bulletin.pdf",
        "https://fenixservices.fao.org/api/data",
        "https://fao.org/data",
    ]
    for u in valid_urls:
        assert validate_candidate_url(u, allowed_domains=allowed, allow_loopback=False) == u

    invalid_urls = [
        "https://evil.example.com/bulletin.pdf",
        "http://phishing-gov.mg.attacker.org/data",
    ]
    for u in invalid_urls:
        with pytest.raises(PolicyStop) as exc_info:
            validate_candidate_url(u, allowed_domains=allowed, allow_loopback=False)
        assert "http_domain_not_allowed" in str(exc_info.value)


def test_ssrf_redirect_is_blocked_before_emission(httpserver: HTTPServer) -> None:
    """Verify redirection to private/cloud metadata address raises PolicyStop without contacting target."""
    httpserver.expect_request("/redirect-to-metadata").respond_with_data(
        "",
        status=302,
        headers={"Location": "http://169.254.169.254/latest/meta-data/"},
    )

    policy = PolicyEngine()
    policy.set_robots_txt(httpserver.url_for("/"), "User-agent: *\nDisallow:\n")
    # allow_loopback=True allows contacting httpserver on 127.0.0.1, but candidate validation on metadata must still reject
    client = PoliteHttpClient(
        policy_engine=policy,
        budget_backend=MemoryBudgetBackend(),
        allow_loopback=True,
    )
    client.bind_source("fixture_test", 500, 100.0)

    # The redirect target is 169.254.169.254 which is not loopback
    with pytest.raises(PolicyStop) as exc_info:
        client.get(httpserver.url_for("/redirect-to-metadata"))
    assert "http_forbidden_destination_target" in str(exc_info.value)


def test_html_discovery_bounded_pagination(httpserver: HTTPServer) -> None:
    """Verify CatalogDiscoveryEngine scans catalog pages within max_pages and extracts links."""
    # Page 1 links to edition 1 & 2 and next page
    p1_html = """
    <html><body>
      <h2>Bulletins Page 1</h2>
      <a href="/bulletins/odr_bulletin_850.pdf">Bulletin 850</a>
      <a href="/bulletins/odr_bulletin_849.pdf">Bulletin 849</a>
      <a href="/catalog?page=2" class="next">Next Page</a>
    </body></html>
    """
    p2_html = """
    <html><body>
      <h2>Bulletins Page 2</h2>
      <a href="/bulletins/odr_bulletin_848.pdf">Bulletin 848</a>
      <a href="/bulletins/odr_bulletin_847.pdf">Bulletin 847</a>
      <a href="/catalog?page=3" class="next">Next Page</a>
    </body></html>
    """
    p3_html = """
    <html><body>
      <h2>Bulletins Page 3</h2>
      <a href="/bulletins/odr_bulletin_846.pdf">Bulletin 846</a>
      <a href="/catalog?page=1" class="next">Cycle back to page 1</a>
    </body></html>
    """

    httpserver.expect_request("/catalog", query_string="").respond_with_data(
        p1_html, content_type="text/html"
    )
    httpserver.expect_request("/catalog", query_string="page=2").respond_with_data(
        p2_html, content_type="text/html"
    )
    httpserver.expect_request("/catalog", query_string="page=3").respond_with_data(
        p3_html, content_type="text/html"
    )

    policy = PolicyEngine()
    policy.set_robots_txt(httpserver.url_for("/"), "User-agent: *\nDisallow:\n")
    client = PoliteHttpClient(
        policy_engine=policy, budget_backend=MemoryBudgetBackend(), allow_loopback=True
    )
    client.bind_source("miasa_odr", 500, 100.0)

    # Set max_pages = 2 -> Should only fetch page 1 and page 2, discovering 4 editions
    engine = CatalogDiscoveryEngine(
        source_id="miasa_odr",
        http_client=client,
        max_pages=2,
        allow_loopback=True,
    )

    result = engine.discover_html_editions(
        start_url=httpserver.url_for("/catalog"),
        link_pattern=r"/bulletins/odr_bulletin_(\d+)\.pdf",
        next_page_pattern=r"/catalog\?page=\d+",
    )

    assert result.status == DiscoveryStatus.NEW_EDITIONS_AVAILABLE
    assert result.pages_scanned == 2
    assert len(result.editions) == 4
    assert result.editions[0].edition_identifier == "850"
    assert result.editions[0].title == "Bulletin 850"
    assert result.editions[1].edition_identifier == "849"
    assert result.editions[2].edition_identifier == "848"
    assert result.editions[3].edition_identifier == "847"


def test_html_discovery_handles_304_not_modified(httpserver: HTTPServer) -> None:
    """Verify HTTP 304 response results in DiscoveryStatus.NO_NEW_EDITION."""
    httpserver.expect_request("/catalog", headers={"If-None-Match": '"etag-v1"'}).respond_with_data(
        "", status=304, headers={"ETag": '"etag-v1"'}
    )

    policy = PolicyEngine()
    policy.set_robots_txt(httpserver.url_for("/"), "User-agent: *\nDisallow:\n")
    client = PoliteHttpClient(
        policy_engine=policy, budget_backend=MemoryBudgetBackend(), allow_loopback=True
    )
    client.bind_source("miasa_odr", 500, 100.0)

    engine = CatalogDiscoveryEngine(source_id="miasa_odr", http_client=client, allow_loopback=True)
    result = engine.discover_html_editions(
        start_url=httpserver.url_for("/catalog"),
        link_pattern=r"/bulletins/.*\.pdf",
        etag='"etag-v1"',
    )

    assert result.status == DiscoveryStatus.NO_NEW_EDITION
    assert result.pages_scanned == 1
    assert len(result.editions) == 0
    assert result.unchanged_editions_count == 1


def test_rss_feed_discovery(httpserver: HTTPServer) -> None:
    """Verify discover_rss_editions parses RSS/XML feeds with enclosure links and publication dates."""
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>MinCC PPN Publications</title>
        <link>http://www.commerce.gov.mg/ppn/</link>
        <item>
          <title>Relevé Prix &amp; Stocks Semaine 10</title>
          <link>http://www.commerce.gov.mg/ppn/releve_s10.html</link>
          <pubDate>Mon, 11 Mar 2024 08:00:00 +0300</pubDate>
        </item>
        <item>
          <title>Relevé Prix &amp; Stocks Semaine 09</title>
          <enclosure url="http://www.commerce.gov.mg/ppn/releve_s09.html" length="1024" type="text/html" />
          <pubDate>Mon, 04 Mar 2024 08:00:00 +0300</pubDate>
        </item>
      </channel>
    </rss>
    """
    httpserver.expect_request("/feed.xml").respond_with_data(
        rss_xml, content_type="application/rss+xml"
    )

    policy = PolicyEngine()
    policy.set_robots_txt(httpserver.url_for("/"), "User-agent: *\nDisallow:\n")
    client = PoliteHttpClient(
        policy_engine=policy, budget_backend=MemoryBudgetBackend(), allow_loopback=True
    )
    client.bind_source("mincc_ppn", 500, 100.0)

    engine = CatalogDiscoveryEngine(source_id="mincc_ppn", http_client=client, allow_loopback=True)
    result = engine.discover_rss_editions(feed_url=httpserver.url_for("/feed.xml"))

    assert result.status == DiscoveryStatus.NEW_EDITIONS_AVAILABLE
    assert len(result.editions) == 2
    assert result.editions[0].title == "Relevé Prix & Stocks Semaine 10"
    assert result.editions[0].published_at is not None
    assert result.editions[0].published_at.year == 2024
    assert result.editions[1].title == "Relevé Prix & Stocks Semaine 09"


def test_filter_known_editions_and_deduplication() -> None:
    """Verify filter_known_editions separates new items from known unchanged SHA-256 artifacts."""
    engine = CatalogDiscoveryEngine(source_id="test_source", allow_loopback=True)

    ed1 = DiscoveredEdition(
        url="https://example.org/bulletin_1.pdf",
        source_id="test_source",
        parent_url="https://example.org/index",
        content_sha256="sha_known_111",
    )
    ed2 = DiscoveredEdition(
        url="https://example.org/bulletin_2.pdf",
        source_id="test_source",
        parent_url="https://example.org/index",
        content_sha256="sha_new_222",
    )
    ed3 = DiscoveredEdition(
        url="https://example.org/bulletin_3.pdf",
        source_id="test_source",
        parent_url="https://example.org/index",
        content_sha256=None,
    )

    known_shas = {"sha_known_111"}
    known_urls = {"https://example.org/bulletin_1.pdf"}

    new_editions, unchanged = engine.filter_known_editions(
        [ed1, ed2, ed3],
        known_shas=known_shas,
        known_urls=known_urls,
    )

    assert len(unchanged) == 1
    assert unchanged[0].url == "https://example.org/bulletin_1.pdf"
    assert unchanged[0].is_new is False

    assert len(new_editions) == 2
    assert new_editions[0].url == "https://example.org/bulletin_2.pdf"
    assert new_editions[1].url == "https://example.org/bulletin_3.pdf"


def test_classify_ingestion_outcomes() -> None:
    """Verify distinct qualification outcomes: discovery_failed, no_new_edition, empty_parsing, success."""
    # 1. Discovery failed
    failed_res = DiscoveryResult(
        status=DiscoveryStatus.DISCOVERY_FAILED,
        source_id="test",
        catalog_url="https://test.example",
        pages_scanned=1,
        error="Network error",
    )
    assert classify_ingestion_outcome(failed_res) == "discovery_failed"

    # 2. No new edition
    no_new_res = DiscoveryResult(
        status=DiscoveryStatus.NO_NEW_EDITION,
        source_id="test",
        catalog_url="https://test.example",
        pages_scanned=1,
        new_editions_count=0,
    )
    assert classify_ingestion_outcome(no_new_res) == "no_new_edition"

    # 3. Empty parsing (new edition discovered, but 0 records extracted)
    has_new_res = DiscoveryResult(
        status=DiscoveryStatus.NEW_EDITIONS_AVAILABLE,
        source_id="test",
        catalog_url="https://test.example",
        pages_scanned=1,
        new_editions_count=1,
    )
    empty_parse = ParseResult(records=[], issues=[{"kind": "empty_table"}], parser_version="1.0.0")
    assert classify_ingestion_outcome(has_new_res, parse_results=[empty_parse]) == "empty_parsing"

    # 4. Success (records extracted)
    valid_record = PriceRecord(
        product_raw="Riz blanc",
        location_raw="Analamanga",
        actor_level="retail",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        price_raw="2800",
        price_value=2800.0,
        unit_raw="kg",
        currency_raw="MGA",
    )
    success_parse = ParseResult(records=[valid_record], issues=[], parser_version="1.0.0")
    assert classify_ingestion_outcome(has_new_res, parse_results=[success_parse]) == "success"
