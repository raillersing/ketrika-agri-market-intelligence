"""Integration tests for FastAPI /v1 API endpoints, auth, and schema contracts (SPECS §19, T6.1)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ketrika.api.auth import ensure_demo_admin, hash_password
from ketrika.api.main import app
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import check_db_connection
from ketrika.core.models.db import (
    Alert,
    Bulletin,
    PriceObservation,
    ReviewItem,
    SourceRecord,
    UserAccount,
)
from ketrika.core.settings import get_settings
from ketrika.gold.refresh import init_gold_views, refresh_gold_views
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.e2e_data.synthetic_gold_dataset import (
    seed_synthetic_gold_data,
)


@pytest.fixture
def db_session():
    """Create a database session connected to PostgreSQL."""
    if not check_db_connection():
        pytest.skip("Database is not reachable (skipping integration tests)")
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session = Session(engine)
    try:
        init_gold_views(session)
        ensure_demo_admin(session)
        session.commit()
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.fixture
def client():
    """Create a test client bound to FastAPI application."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_user(db_session: Session) -> UserAccount:
    """Ensure a regular client (non-admin) user exists."""
    user = db_session.execute(
        select(UserAccount).where(UserAccount.email == "client@ketrika.local")
    ).scalar_one_or_none()
    if not user:
        user = UserAccount(
            user_id=uuid.uuid4(),
            email="client@ketrika.local",
            password_hash=hash_password("client-pass-123"),
            role="client",
            disabled=False,
            created_at=datetime.now(UTC),
        )
        db_session.add(user)
        db_session.commit()
    return user


@pytest.mark.integration
def test_api_public_and_analytical_endpoints_200(db_session: Session, client: httpx.Client):
    """Verify all public analytical endpoints return 200 OK and valid schemas."""
    # Seed synthetic gold data and refresh views
    wipe_silver_gold_tables(db_session)
    db_session.commit()
    seed_synthetic_gold_data(db_session)
    db_session.commit()
    refresh_gold_views(db_session)
    db_session.commit()

    # 1. GET /v1/health
    r_health = client.get("/v1/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"
    assert r_health.json()["database"] == "connected"

    # 2. GET /v1/products
    r_products = client.get("/v1/products")
    assert r_products.status_code == 200
    products = r_products.json()
    assert len(products) >= 2
    assert any(p["product_code"] == "rice_milled" for p in products)

    # 3. GET /v1/locations
    r_locations = client.get("/v1/locations?level=1")
    assert r_locations.status_code == 200
    locations = r_locations.json()
    assert len(locations) >= 1
    assert any(loc["name"] == "Analamanga" for loc in locations)

    # 4. GET /v1/locations?geometry=true
    r_geo = client.get("/v1/locations?geometry=true&level=1")
    assert r_geo.status_code == 200
    geo_data = r_geo.json()
    assert geo_data["type"] == "FeatureCollection"

    # 5. GET /v1/prices (JSON and CSV)
    r_prices = client.get("/v1/prices?product=rice_milled")
    assert r_prices.status_code == 200
    prices = r_prices.json()
    assert len(prices) >= 1
    assert "median_price" in prices[0]
    assert prices[0]["value_kind"] in ("observed", "imputed")

    r_prices_csv = client.get("/v1/prices?product=rice_milled&format=csv")
    assert r_prices_csv.status_code == 200
    assert "text/csv" in r_prices_csv.headers["content-type"]
    assert "median_price" in r_prices_csv.text

    # 6. GET /v1/prices/latest
    r_latest = client.get("/v1/prices/latest?product=rice_milled&level=1")
    assert r_latest.status_code == 200
    latest = r_latest.json()
    assert len(latest) >= 1
    assert "value_kind" in latest[0]

    # 7. GET /v1/stocks
    r_stocks = client.get("/v1/stocks?product=rice_milled")
    assert r_stocks.status_code == 200
    stocks = r_stocks.json()
    assert len(stocks) >= 1
    assert stocks[0]["stock_status"] in ("sufficient", "tight", "shortage")
    assert stocks[0]["value_kind"] == "observed"

    # 8. GET /v1/trade
    r_trade = client.get("/v1/trade?product=rice_milled")
    assert r_trade.status_code == 200
    trade_flows = r_trade.json()
    assert len(trade_flows) >= 1
    assert "weight_tons" in trade_flows[0]
    assert trade_flows[0]["value_kind"] == "observed"

    # 9. GET /v1/weather/anomalies
    r_weather = client.get("/v1/weather/anomalies")
    assert r_weather.status_code == 200
    weather = r_weather.json()
    assert len(weather) >= 1
    assert "precip_total_mm" in weather[0]
    assert weather[0]["value_kind"] == "observed"

    # 10. GET /v1/kpis/market-health
    r_kpi = client.get("/v1/kpis/market-health?product=rice_milled")
    assert r_kpi.status_code == 200
    kpis = r_kpi.json()
    assert len(kpis) >= 1
    assert "coverage" in kpis[0]
    assert kpis[0]["value_kind"] == "composite"

    # 11. GET /v1/forecasts
    r_forecasts = client.get("/v1/forecasts?product=rice_milled")
    assert r_forecasts.status_code == 200
    forecasts = r_forecasts.json()
    assert len(forecasts) >= 1
    assert "p50" in forecasts[0]
    assert forecasts[0]["value_kind"] == "forecast"

    # 12. GET /v1/sources & /v1/sources/{id}/health
    r_sources = client.get("/v1/sources")
    assert r_sources.status_code == 200
    sources = r_sources.json()
    assert len(sources) >= 1

    r_s_health = client.get("/v1/sources/miasa_odr/health")
    assert r_s_health.status_code == 200
    s_health = r_s_health.json()
    assert s_health["source_id"] == "miasa_odr"
    assert "is_stale" in s_health


@pytest.mark.integration
def test_observation_provenance_and_presigned_bronze_url(db_session: Session, client: httpx.Client):
    """Verify /v1/observations/{id} returns evidence, source_url, parser_version and a valid presigned Bronze link."""
    # Setup test source record in Bronze storage
    bronze = BronzeStore()
    now = datetime.now(UTC)
    unique_key = f"obs_test_{uuid.uuid4().hex[:8]}"
    content_bytes = f"date,product,price\n2024-01-15,vary,{unique_key}\n".encode()

    artifact = bronze.put(
        source_id="miasa_odr",
        url=f"https://example.com/bulletin_prov_{unique_key}.pdf",
        content=content_bytes,
        mime_type="application/pdf",
    )

    srec = SourceRecord(
        source_record_id=uuid.uuid4(),
        source_id="miasa_odr",
        source_url="https://example.com/bulletin_prov_test.pdf",
        retrieved_via="direct",
        object_key=artifact.object_key,
        content_sha256=artifact.content_sha256,
        mime_type="application/pdf",
        fetched_at=now,
        parser_version="1.2.0",
        extraction_status="parsed",
    )
    db_session.add(srec)

    obs_id = uuid.uuid4()
    p_obs = PriceObservation(
        observation_id=obs_id,
        source_record_id=srec.source_record_id,
        natural_key=f"nat_{unique_key}",
        product_raw="Riz makalioka",
        actor_level="retail",
        period_start=now.date(),
        period_end=now.date(),
        price_raw="3 200 Ar",
        price_value=3200.0,
        currency_raw="MGA",
        unit_raw="kg",
        price_mga_per_base=3200.0,
        base_unit="kg",
        conversion_status="converted",
        observed_or_imputed="observed",
        extraction_method="deterministic",
        confidence=1.0,
        evidence={"page": 3, "table_row": 5, "raw_text": "Riz blanc 3 200 Ar/kg"},
        review_status="accepted",
    )
    db_session.add(p_obs)
    db_session.commit()

    # Query /v1/observations/{id}
    res = client.get(f"/v1/observations/{obs_id}")
    assert res.status_code == 200
    data = res.json()

    # Acceptance criteria verification
    assert data["observation_id"] == str(obs_id)
    assert data["source_url"] == "https://example.com/bulletin_prov_test.pdf"
    assert data["parser_version"] == "1.2.0"
    assert data["evidence"]["page"] == 3
    assert data["evidence"]["raw_text"] == "Riz blanc 3 200 Ar/kg"
    assert data["value_kind"] == "observed"
    assert "bronze_presigned_url" in data
    assert data["bronze_presigned_url"].startswith("http")
    assert "bronze" in data["bronze_presigned_url"]

    # 404 test on unknown ID
    r_404 = client.get(f"/v1/observations/{uuid.uuid4()}")
    assert r_404.status_code == 404
    assert r_404.headers["content-type"] == "application/problem+json"


@pytest.mark.integration
def test_api_auth_roles_and_status_codes(
    db_session: Session,
    client: httpx.Client,
    client_user: UserAccount,
):
    """Verify 401 Unauthorized, 403 Forbidden based on roles, and 422 validation errors (RFC 7807)."""
    settings = get_settings()

    # 1. 401 Unauthorized tests
    r_unauth = client.get("/v1/auth/me")
    assert r_unauth.status_code == 401
    assert r_unauth.headers["content-type"] == "application/problem+json"
    assert r_unauth.json()["status"] == 401

    r_copilot_unauth = client.post("/v1/copilot/ask", json={"question": "Prix du riz ?"})
    assert r_copilot_unauth.status_code == 401

    # Invalid login -> 401
    r_login_fail = client.post(
        "/v1/auth/login",
        json={"email": settings.demo_admin_email, "password": "wrong-password"},
    )
    assert r_login_fail.status_code == 401

    # 2. 422 Unprocessable Entity test (RFC 7807)
    r_val_err = client.post("/v1/auth/login", json={})
    assert r_val_err.status_code == 422
    assert r_val_err.headers["content-type"] == "application/problem+json"
    assert r_val_err.json()["status"] == 422
    assert "invalid_params" in r_val_err.json()

    # 3. Successful login as admin
    r_login_admin = client.post(
        "/v1/auth/login",
        json={"email": settings.demo_admin_email, "password": settings.demo_admin_password},
    )
    assert r_login_admin.status_code == 200
    admin_token = r_login_admin.json()["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Verify session cookie was set
    assert "session_token" in r_login_admin.cookies

    # GET /v1/auth/me with admin token
    r_me = client.get("/v1/auth/me", headers=admin_headers)
    assert r_me.status_code == 200
    assert r_me.json()["role"] == "admin"

    # 4. Successful login as regular client
    r_login_client = client.post(
        "/v1/auth/login",
        json={"email": "client@ketrika.local", "password": "client-pass-123"},
    )
    assert r_login_client.status_code == 200
    client_token = r_login_client.json()["token"]
    client_headers = {"Authorization": f"Bearer {client_token}"}

    # Copilot endpoint works for authenticated client
    r_copilot_client = client.post(
        "/v1/copilot/ask",
        json={"question": "Quel est le prix moyen du riz ?"},
        headers=client_headers,
    )
    assert r_copilot_client.status_code == 200
    assert "answer_markdown" in r_copilot_client.json()

    # 5. 403 Forbidden tests: client attempting admin endpoints
    # A) /v1/admin/api-keys
    r_forbid_apikey = client.post(
        "/v1/admin/api-keys",
        json={"name": "Forbidden Key"},
        headers=client_headers,
    )
    assert r_forbid_apikey.status_code == 403
    assert r_forbid_apikey.headers["content-type"] == "application/problem+json"

    # B) /v1/admin/review
    r_forbid_review = client.get("/v1/admin/review", headers=client_headers)
    assert r_forbid_review.status_code == 403

    # C) /v1/bulletins/{id}/approve
    r_forbid_bulletin = client.post(
        f"/v1/bulletins/{uuid.uuid4()}/approve",
        headers=client_headers,
    )
    assert r_forbid_bulletin.status_code == 403

    # D) /v1/alerts/{id} PATCH
    r_forbid_alert = client.patch(
        f"/v1/alerts/{uuid.uuid4()}",
        json={"state": "acknowledged"},
        headers=client_headers,
    )
    assert r_forbid_alert.status_code == 403

    # 6. Admin operations succeed with admin token
    # Create programmatic API key
    r_apikey_admin = client.post(
        "/v1/admin/api-keys",
        json={"name": "Prod API Key"},
        headers=admin_headers,
    )
    assert r_apikey_admin.status_code == 200
    raw_key = r_apikey_admin.json()["raw_key"]
    assert raw_key.startswith("ketrika_live_")

    # Use programmatic X-API-Key to authenticate
    r_me_api_key = client.get("/v1/auth/me", headers={"X-API-Key": raw_key})
    assert r_me_api_key.status_code == 200
    assert r_me_api_key.json()["role"] == "admin"

    # Admin review queue
    rev_id = uuid.uuid4()
    rev = ReviewItem(
        review_id=rev_id,
        kind="unknown_product",
        payload={"raw_text": "vary gasy tsipala"},
        status="open",
        created_at=datetime.now(UTC),
    )
    db_session.add(rev)
    db_session.commit()

    r_review = client.get("/v1/admin/review", headers=admin_headers)
    assert r_review.status_code == 200
    assert len(r_review.json()) >= 1

    r_resolve = client.post(
        f"/v1/admin/review/{rev_id}",
        json={"status": "approved", "resolution_note": "Resolved to canonical"},
        headers=admin_headers,
    )
    assert r_resolve.status_code == 200
    assert r_resolve.json()["status"] == "approved"

    # Bulletin workflow
    bul_id = uuid.uuid4()
    bulletin = Bulletin(
        bulletin_id=bul_id,
        period_start=datetime.now(UTC).date(),
        period_end=datetime.now(UTC).date(),
        status="draft",
        facts={"f1": {"label": "Prix", "val": 3000}},
        created_at=datetime.now(UTC),
    )
    db_session.add(bulletin)
    db_session.commit()

    r_app_bul = client.post(f"/v1/bulletins/{bul_id}/approve", headers=admin_headers)
    assert r_app_bul.status_code == 200
    assert r_app_bul.json()["status"] == "approved"

    # Alert update
    alert_id = uuid.uuid4()
    al = Alert(
        alert_id=alert_id,
        rule_code="PRICE_SPIKE",
        dedupe_key=f"TEST_ALERT_{uuid.uuid4().hex[:6]}",
        severity="high",
        title="Flambée des prix",
        evidence={},
        state="open",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    db_session.add(al)
    db_session.commit()

    r_patch_al = client.patch(
        f"/v1/alerts/{alert_id}",
        json={"state": "acknowledged"},
        headers=admin_headers,
    )
    assert r_patch_al.status_code == 200
    assert r_patch_al.json()["state"] == "acknowledged"


@pytest.mark.integration
def test_api_security_headers(client: httpx.Client):
    """Verify standard security headers are injected into HTTP responses (SPECS §23, T11.2)."""
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation=()" in resp.headers.get("Permissions-Policy", "")
