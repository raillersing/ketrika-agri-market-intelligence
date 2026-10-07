"""Performance, latency benchmarks (P95 < 1s) and rate limit tests (SPECS §19, §23, T6.2)."""

from __future__ import annotations

import time
import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ketrika.api.auth import ensure_demo_admin
from ketrika.api.main import app
from ketrika.api.rate_limit import rate_limiter
from ketrika.core.db import check_db_connection
from ketrika.core.settings import get_settings
from ketrika.gold.refresh import init_gold_views, refresh_gold_views
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.e2e_data.synthetic_gold_dataset import seed_synthetic_gold_data


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


@pytest.mark.integration
def test_rate_limiter_strict_60_req_per_minute(client: TestClient):
    """Verify rate limit: 60 requests succeed, 61st returns 429 (SPECS §23)."""
    test_key = f"ketrika_live_perf_{uuid.uuid4().hex[:16]}"
    headers = {"X-API-Key": test_key}

    # Reset any records for this key
    rate_limiter.reset(f"key:{test_key}")

    # Fire 60 requests - all must succeed (200 OK)
    for i in range(60):
        res = client.get("/v1/products", headers=headers)
        assert res.status_code == 200, f"Request {i + 1} failed with status {res.status_code}"
        assert "X-RateLimit-Remaining" in res.headers

    # 61st request must be rejected with 429 Too Many Requests
    res_61 = client.get("/v1/products", headers=headers)
    assert res_61.status_code == 429
    assert "Retry-After" in res_61.headers
    assert int(res_61.headers["Retry-After"]) >= 1
    assert "application/problem+json" in res_61.headers["content-type"]

    data_429 = res_61.json()
    assert data_429["status"] == 429
    assert data_429["title"] == "Too Many Requests"
    assert "Rate limit" in data_429["detail"]

    # Another client key must still be allowed
    other_key = f"ketrika_live_other_{uuid.uuid4().hex[:16]}"
    res_other = client.get("/v1/products", headers={"X-API-Key": other_key})
    assert res_other.status_code == 200

    # Exempt path (/v1/health) must not be throttled even with the exhausted key
    res_health = client.get("/v1/health", headers=headers)
    assert res_health.status_code == 200


@pytest.mark.integration
def test_aggregated_endpoints_latency_p95(db_session: Session, client: TestClient):
    """Benchmark aggregated endpoints on demo dataset (≥ 200 requests, P95 < 1s)."""
    # Ensure database has demo data populated and gold views refreshed
    wipe_silver_gold_tables(db_session)
    db_session.commit()
    seed_synthetic_gold_data(db_session)
    db_session.commit()
    refresh_gold_views(db_session)
    db_session.commit()

    endpoints_to_benchmark = [
        "/v1/prices?product=rice_milled",
        "/v1/prices/latest?product=rice_milled&level=1",
        "/v1/stocks?product=rice_milled",
        "/v1/trade?product=rice_milled",
        "/v1/kpis/market-health",
        "/v1/weather/anomalies",
    ]

    n_requests = 200
    perf_results: dict[str, dict[str, float]] = {}

    for endpoint in endpoints_to_benchmark:
        latencies_ms: list[float] = []

        # Reset rate limiter before benchmarking this endpoint to avoid throttling
        rate_limiter.reset()

        for req_idx in range(n_requests):
            # Rotate client key every 50 requests so rate limit does not interfere
            client_key = f"perf_bench_{req_idx // 50}_{endpoint[:10]}"
            headers = {"X-API-Key": client_key}

            t0 = time.perf_counter()
            resp = client.get(endpoint, headers=headers)
            t1 = time.perf_counter()

            assert resp.status_code == 200, (
                f"Benchmark request to {endpoint} returned {resp.status_code}"
            )
            latency_ms = (t1 - t0) * 1000.0
            latencies_ms.append(latency_ms)

        lat_arr = np.array(latencies_ms)
        p50 = float(np.percentile(lat_arr, 50))
        p90 = float(np.percentile(lat_arr, 90))
        p95 = float(np.percentile(lat_arr, 95))
        p99 = float(np.percentile(lat_arr, 99))
        mean_lat = float(np.mean(lat_arr))
        max_lat = float(np.max(lat_arr))

        perf_results[endpoint] = {
            "p50_ms": p50,
            "p90_ms": p90,
            "p95_ms": p95,
            "p99_ms": p99,
            "mean_ms": mean_lat,
            "max_ms": max_lat,
        }

        # Print detailed benchmark stats
        print(
            f"\n[BENCHMARK] {endpoint} ({n_requests} reqs): "
            f"P50={p50:.2f}ms, P90={p90:.2f}ms, P95={p95:.2f}ms, P99={p99:.2f}ms, Mean={mean_lat:.2f}ms"
        )

        # Normative criterion: P95 < 1000 ms (1 second)
        assert p95 < 1000.0, f"Endpoint {endpoint} exceeded P95 SLA: {p95:.2f}ms >= 1000ms"

    # Verify all 6 endpoints were successfully benchmarked
    assert len(perf_results) == 6
