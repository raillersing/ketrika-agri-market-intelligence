"""The production app, without a fake principal, rejects every business route."""

import re

from fastapi.testclient import TestClient

from ketrika.api.main import app
from ketrika.api.rate_limit import rate_limiter


def test_all_business_routes_refuse_anonymous_before_database_use(record_property):
    client = TestClient(app)
    paths = []
    try:
        for declared_path, methods in app.openapi()["paths"].items():
            if declared_path.startswith("/v1/auth/") or declared_path == "/v1/health":
                continue
            assert declared_path.startswith("/v1/")
            path = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000001", declared_path)
            for method in methods:
                method = method.upper()
                if method not in {"GET", "POST", "PATCH", "PUT", "DELETE", "HEAD", "OPTIONS"}:
                    continue
                rate_limiter.reset()
                response = client.request(
                    method, path, json={} if method in {"POST", "PATCH", "PUT"} else None
                )
                assert response.status_code == 401, (
                    method,
                    path,
                    response.status_code,
                    response.text,
                )
                paths.append((method, path))
        assert len(paths) >= 40
        record_property("protected_methods_checked", len(paths))
    finally:
        rate_limiter.reset()


def test_arbitrary_cookie_is_not_a_session():
    client = TestClient(app)
    client.cookies.set("session_token", "arbitrary")
    response = client.get("/v1/prices")
    assert response.status_code == 401
