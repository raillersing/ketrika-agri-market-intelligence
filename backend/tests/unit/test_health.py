"""Unit tests for /v1/health endpoint."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from ketrika.api.main import app

client = TestClient(app)


def test_health_check_healthy() -> None:
    """Test health check returns 200 when DB and S3 are connected."""
    with (
        patch("ketrika.api.main.check_db_connection", return_value=True),
        patch("ketrika.api.main.check_s3_connection", return_value=True),
    ):
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert data["storage"] == "connected"


def test_health_check_degraded() -> None:
    """Test health check returns 503 when a service is unreachable."""
    with (
        patch("ketrika.api.main.check_db_connection", return_value=False),
        patch("ketrika.api.main.check_s3_connection", return_value=True),
    ):
        response = client.get("/v1/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "unreachable"
