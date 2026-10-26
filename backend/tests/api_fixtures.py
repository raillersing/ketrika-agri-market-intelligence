"""Real login for isolated SQL/business tests; never bypasses API authentication."""

from fastapi.testclient import TestClient
from httpx import Client

from ketrika.core.settings import get_settings


def login_test_admin(client: Client | TestClient) -> str:
    settings = get_settings()
    response = client.post(
        "/v1/auth/login",
        json={"email": settings.demo_admin_email, "password": settings.demo_admin_password},
    )
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    assert isinstance(token, str)
    return token
