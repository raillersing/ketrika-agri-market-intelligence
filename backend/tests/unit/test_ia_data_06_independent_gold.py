"""Tests for IA-DATA-06: Independent Gold publication domains and isolated savepoints."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ketrika.api.auth import get_current_user
from ketrika.api.main import app
from ketrika.gold.dq import GoldDqRejected, PublicationDenominators
from ketrika.gold.provenance_gate import PublicationCheck
from ketrika.gold.refresh import (
    GOLD_DOMAINS,
    UNPUBLISHED_GOLD_VIEWS,
    VIEW_TO_DOMAIN,
    get_domain_views,
    get_view_domain,
    refresh_all_domains_independent,
    refresh_domain_views,
    refresh_gold_views,
)


@pytest.fixture(autouse=True)
def isolate_dq_checks(monkeypatch):
    """Bypass deep SQL DQ checks for unit tests of transactional control."""
    monkeypatch.setattr("ketrika.gold.refresh.check_blocking_dq_gate", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "ketrika.gold.refresh.get_publication_denominators",
        lambda *args, **kwargs: PublicationDenominators(0, 0, 0, 0, 0, 0, 0, 0, 0),
    )


def test_gold_domain_definitions_and_mappings():
    """Verify that domain boundaries match the four formal analytical domains."""
    assert set(GOLD_DOMAINS.keys()) == {"price", "trade", "climate", "macro"}

    # Price views
    price_views = get_domain_views("price")
    assert "price_obs_current" in price_views
    assert "price_monthly" in price_views
    assert "price_monthly_best" in price_views
    assert "price_changes" in price_views
    assert "market_coverage" in price_views

    # Trade views
    trade_views = get_domain_views("trade")
    assert "stock_latest" in trade_views
    assert "trade_monthly" in trade_views
    assert "import_dependency" in trade_views

    # Climate views
    climate_views = get_domain_views("climate")
    assert climate_views == ["weather_monthly"]

    # Macro views
    macro_views = get_domain_views("macro")
    assert "cpi_food" in macro_views
    assert "market_health" in macro_views
    assert "source_health" in macro_views
    assert "forecast_latest" in macro_views

    # Unpublished views are excluded from publication domains
    for unpub in UNPUBLISHED_GOLD_VIEWS:
        assert unpub not in VIEW_TO_DOMAIN

    # Reverse lookup
    assert get_view_domain("price_monthly") == "price"
    assert get_view_domain("trade_monthly") == "trade"
    assert get_view_domain("weather_monthly") == "climate"
    assert get_view_domain("cpi_food") == "macro"
    assert get_view_domain("unknown_view") is None

    # Unsupported domain
    with pytest.raises(ValueError, match="unsupported_gold_domain"):
        get_domain_views("invalid_domain")


def test_refresh_single_domain_executes_only_domain_views():
    """Refreshing 'price' domain only executes price-related views."""
    session, reader = MagicMock(spec=Session), MagicMock()
    session.execute.return_value.scalar.return_value = 1

    with (
        patch(
            "ketrika.gold.refresh.require_gold_provenance",
            return_value=PublicationCheck("empty", (), None),
        ),
        patch(
            "ketrika.gold.refresh.require_gold_structure",
            return_value=SimpleNamespace(state="ok", receipts=[], total=0, valid=0),
        ),
    ):
        res = refresh_domain_views(session, domain="price", reader=reader)

    assert set(res["views_refreshed"]) == set(get_domain_views("price"))
    assert "weather_monthly" not in res["views_refreshed"]
    assert "stock_latest" not in res["views_refreshed"]


def test_refresh_domain_with_views_outside_domain_rejected():
    """Requesting views outside the specified domain raises a clear validation error."""
    session, reader = MagicMock(spec=Session), MagicMock()

    with pytest.raises(ValueError, match="views_outside_requested_domain"):
        refresh_gold_views(session, views=["weather_monthly"], domain="price", reader=reader)


def test_independent_domain_refresh_all_success():
    """When all domains succeed, status is 'success' and all domains are recorded."""
    session, reader = MagicMock(spec=Session), MagicMock()
    session.execute.return_value.scalar.return_value = 1

    with (
        patch(
            "ketrika.gold.refresh.require_gold_provenance",
            return_value=PublicationCheck("empty", (), None),
        ),
        patch(
            "ketrika.gold.refresh.require_gold_structure",
            return_value=SimpleNamespace(state="ok", receipts=[], total=0, valid=0),
        ),
    ):
        res = refresh_all_domains_independent(session, reader=reader)

    assert res["status"] == "success"
    assert set(res["domains_succeeded"]) == {"price", "trade", "climate", "macro"}
    assert res["domains_failed"] == []
    assert res["count"] > 0


def test_independent_domain_refresh_error_isolation():
    """A failure in 'macro' does not prevent or rollback valid 'price', 'trade', or 'climate' publication."""
    session, reader = MagicMock(spec=Session), MagicMock()
    session.execute.return_value.scalar.return_value = 1

    original_refresh = refresh_gold_views

    def conditional_refresh(s, *args, **kwargs):
        if kwargs.get("domain") == "macro":
            raise GoldDqRejected("macro_source_health_dq_failure")
        return original_refresh(s, *args, **kwargs)

    with (
        patch(
            "ketrika.gold.refresh.require_gold_provenance",
            return_value=PublicationCheck("empty", (), None),
        ),
        patch(
            "ketrika.gold.refresh.require_gold_structure",
            return_value=SimpleNamespace(state="ok", receipts=[], total=0, valid=0),
        ),
        patch("ketrika.gold.refresh.refresh_gold_views", side_effect=conditional_refresh),
    ):
        res = refresh_all_domains_independent(session, reader=reader)

    assert res["status"] == "partial_success"
    assert "price" in res["domains_succeeded"]
    assert "trade" in res["domains_succeeded"]
    assert "climate" in res["domains_succeeded"]
    assert "macro" in res["domains_failed"]
    assert "macro_source_health_dq_failure" in res["domain_errors"]["macro"]


def test_admin_api_gold_refresh_single_domain():
    """POST /v1/admin/gold/refresh?domain=price succeeds for authorized admin."""
    client = TestClient(app)
    admin_mock = SimpleNamespace(
        user_id="00000000-0000-0000-0000-000000000001",
        email="admin@ketrika.com",
        role="admin",
    )
    app.dependency_overrides[get_current_user] = lambda: admin_mock

    try:
        with patch("ketrika.gold.refresh.refresh_domain_views") as mock_refresh:
            mock_refresh.return_value = {
                "views_refreshed": ["price_obs_current", "price_monthly"],
                "count": 2,
            }
            resp = client.post("/v1/admin/gold/refresh?domain=price")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "success"
            assert data["domains_succeeded"] == ["price"]
            assert data["views_refreshed"] == ["price_obs_current", "price_monthly"]
            assert data["count"] == 2
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_api_gold_refresh_invalid_domain():
    """POST /v1/admin/gold/refresh?domain=invalid raises 400 Bad Request."""
    client = TestClient(app)
    admin_mock = SimpleNamespace(
        user_id="00000000-0000-0000-0000-000000000001",
        email="admin@ketrika.com",
        role="admin",
    )
    app.dependency_overrides[get_current_user] = lambda: admin_mock

    try:
        resp = client.post("/v1/admin/gold/refresh?domain=invalid_domain")
        assert resp.status_code == 400
        assert "unsupported_gold_domain" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_api_gold_refresh_all_domains():
    """POST /v1/admin/gold/refresh without domain refreshes all domains independently."""
    client = TestClient(app)
    admin_mock = SimpleNamespace(
        user_id="00000000-0000-0000-0000-000000000001",
        email="admin@ketrika.com",
        role="admin",
    )
    app.dependency_overrides[get_current_user] = lambda: admin_mock

    try:
        with patch("ketrika.gold.refresh.refresh_all_domains_independent") as mock_refresh_all:
            mock_refresh_all.return_value = {
                "status": "partial_success",
                "domains_succeeded": ["price", "trade"],
                "domains_failed": ["climate", "macro"],
                "domain_errors": {"macro": "timeout"},
                "views_refreshed": ["price_monthly", "stock_latest"],
                "count": 2,
            }
            resp = client.post("/v1/admin/gold/refresh")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "partial_success"
            assert data["domains_succeeded"] == ["price", "trade"]
            assert data["domains_failed"] == ["climate", "macro"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
