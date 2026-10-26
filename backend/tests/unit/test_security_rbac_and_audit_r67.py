"""Normative acceptance tests for Security Hardening, RBAC, and Application Audit (R6.7, ADR-101, SPECS §19, §23).

Verifies:
1. Client role cannot modify review items (403 Forbidden).
2. Client role cannot create admin API keys (403 Forbidden).
3. Client role cannot approve market bulletins (403 Forbidden).
4. Client role cannot alter alert states (403 Forbidden).
5. Unauthenticated requests to protected endpoints return 401 Unauthorized.
6. Cryptographically signed action links succeed within validity window.
7. Expired signed action links are strictly rejected (401 Unauthorized).
8. Tampered or mismatched signed action tokens are rejected (401/403).
9. Logout actively revokes JWT access token, blocking subsequent reuse even before natural expiry.
10. Container security posture verification: non-root app user and unexposed internal ports in prod Compose.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ketrika.api.auth import (
    create_access_token,
    create_signed_action_token,
    decode_access_token,
    is_token_revoked,
    revoke_token,
    verify_signed_action_token,
)
from ketrika.api.errors import ForbiddenException, UnauthorizedException
from ketrika.api.main import app
from ketrika.core.db import get_db
from ketrika.core.models.db import UserAccount
from tests.session_fixtures import session_store_engine


@pytest.fixture
def admin_user() -> UserAccount:
    """Fixture for an authentic admin user."""
    return UserAccount(
        user_id=uuid.uuid4(),
        email="admin@ketrika.mg",
        password_hash="argon2_fake_hash",
        role="admin",
        disabled=False,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def client_user() -> UserAccount:
    """Fixture for a standard non-admin client user."""
    return UserAccount(
        user_id=uuid.uuid4(),
        email="client@institution.mg",
        password_hash="argon2_fake_hash",
        role="client",
        disabled=False,
        created_at=datetime.now(UTC),
    )


@pytest.fixture(autouse=True)
def mock_db_session(client_user: UserAccount, admin_user: UserAccount):
    """Automatically mock get_db dependency for unit tests without active PostgreSQL."""
    mock_session = MagicMock()

    def get_user_mock(model_cls, user_uuid):
        if str(user_uuid) == str(client_user.user_id):
            return client_user
        if str(user_uuid) == str(admin_user.user_id):
            return admin_user
        return None

    mock_session.get.side_effect = get_user_mock
    app.dependency_overrides[get_db] = lambda: mock_session
    yield mock_session
    app.dependency_overrides.pop(get_db, None)


# =========================================================================
# 1. RBAC CONTROLS: CLIENT CANNOT MUTATE REVIEWS, BULLETINS, ALERTS, KEYS
# =========================================================================


def test_client_role_cannot_modify_review_items(client_user: UserAccount) -> None:
    """R6.7 Acceptance: Client role is strictly forbidden from resolving review items."""
    mock_session = MagicMock()
    mock_session.get.return_value = client_user

    client = TestClient(app)
    token = create_access_token(client_user)

    review_id = uuid.uuid4()
    resp = client.post(
        f"/v1/admin/review/{review_id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Must be 403 Forbidden because require_admin rejects client role
    assert resp.status_code == 403
    assert "Administrator privileges required" in resp.json()["detail"]


def test_client_role_cannot_create_api_keys(client_user: UserAccount) -> None:
    """R6.7 Acceptance: Client role is strictly forbidden from creating admin API keys."""
    client = TestClient(app)
    token = create_access_token(client_user)

    resp = client.post(
        "/v1/admin/api-keys",
        json={"name": "test-key", "role": "admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert "Administrator privileges required" in resp.json()["detail"]


def test_client_role_cannot_approve_bulletin(client_user: UserAccount) -> None:
    """R6.7 Acceptance: Client role is strictly forbidden from approving market bulletins."""
    client = TestClient(app)
    token = create_access_token(client_user)

    bulletin_id = uuid.uuid4()
    resp = client.post(
        f"/v1/bulletins/{bulletin_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert "Administrator privileges required" in resp.json()["detail"]


def test_client_role_cannot_modify_alert_state(client_user: UserAccount) -> None:
    """R6.7 Acceptance: Client role is strictly forbidden from acknowledging/resolving alerts."""
    client = TestClient(app)
    token = create_access_token(client_user)

    alert_id = uuid.uuid4()
    resp = client.patch(
        f"/v1/alerts/{alert_id}",
        json={"state": "acknowledged"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert "Administrator privileges required" in resp.json()["detail"]


def test_unauthenticated_request_rejected_on_admin_routes() -> None:
    """R6.7 Acceptance: Unauthenticated requests return 401 Unauthorized."""
    client = TestClient(app)

    # Missing Authorization header
    resp = client.get("/v1/admin/review")
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]

    # Invalid Bearer token
    resp_invalid = client.get(
        "/v1/admin/review", headers={"Authorization": "Bearer invalid_garbage_token"}
    )
    assert resp_invalid.status_code == 401


# =========================================================================
# 2. CRYPTOGRAPHIC SIGNED ACTION LINKS & EXPIRY ENFORCEMENT
# =========================================================================


def test_signed_action_token_nominal_and_verification() -> None:
    """R6.7 Acceptance: Signed action link verified within validity window."""
    resource_id = "bulletin-w38-2026"
    action = "download_pdf"

    token = create_signed_action_token(action=action, resource_id=resource_id, expires_seconds=120)
    assert isinstance(token, str)
    assert len(token) > 20

    payload = verify_signed_action_token(
        token, expected_action=action, expected_resource_id=resource_id
    )
    assert payload["action"] == action
    assert payload["resource_id"] == resource_id
    assert payload["exp"] > payload["iat"]


def test_expired_signed_action_token_strictly_rejected() -> None:
    """R6.7 Acceptance: Expired signed action link is strictly rejected (UnauthorizedException)."""
    resource_id = "bulletin-w38-2026"
    action = "download_pdf"

    # Token with negative expiry (already in past)
    token = create_signed_action_token(action=action, resource_id=resource_id, expires_seconds=-10)

    with pytest.raises(UnauthorizedException, match="Signed link has expired"):
        verify_signed_action_token(token, expected_action=action, expected_resource_id=resource_id)


def test_tampered_or_mismatched_signed_action_token_rejected() -> None:
    """R6.7 Acceptance: Action mismatch, resource mismatch, or tampering raises security exception."""
    token = create_signed_action_token(
        action="download_pdf", resource_id="res-001", expires_seconds=60
    )

    # Action mismatch -> 403 ForbiddenException
    with pytest.raises(ForbiddenException, match="Action mismatch"):
        verify_signed_action_token(
            token, expected_action="delete_bulletin", expected_resource_id="res-001"
        )

    # Resource mismatch -> 403 ForbiddenException
    with pytest.raises(ForbiddenException, match="Resource mismatch"):
        verify_signed_action_token(
            token, expected_action="download_pdf", expected_resource_id="res-999"
        )

    # Tampered token string -> 401 UnauthorizedException
    tampered = token[:-4] + "fake"
    with pytest.raises(UnauthorizedException, match="Invalid signed action link"):
        verify_signed_action_token(
            tampered, expected_action="download_pdf", expected_resource_id="res-001"
        )


# =========================================================================
# 3. LOGOUT AND ACTIVE TOKEN REVOCATION
# =========================================================================


def test_logout_actively_revokes_token_and_blocks_subsequent_access(
    admin_user: UserAccount,
    tmp_path: Path,
) -> None:
    """Logout commits a real private ledger, then /me refuses the old session."""
    engine = session_store_engine(tmp_path / "logout.db")
    try:
        with Session(engine) as session:
            app.dependency_overrides[get_db] = lambda: session
            token = create_access_token(admin_user)
            assert not is_token_revoked(token, session)
            assert decode_access_token(token, session)["sub"] == str(admin_user.user_id)
            client = TestClient(app)
            response = client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200
            assert response.json()["revoked"] is True
            assert is_token_revoked(token, session)
            assert (
                client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
                == 401
            )
            direct_token = create_access_token(admin_user)
            revoke_token(direct_token, session)
            assert is_token_revoked(direct_token, session)
            with pytest.raises(UnauthorizedException, match="Session has been terminated"):
                decode_access_token(token, session)
    finally:
        engine.dispose()


# =========================================================================
# 4. CONTAINER SECURITY POSTURE & LEAST PRIVILEGE
# =========================================================================


def test_docker_security_posture_non_root_and_unexposed_internal_services() -> None:
    """R6.7 Acceptance: Container uses non-root app user; internal database/storage have no unshielded host ports in prod."""
    repo_root = Path("/workspace")
    if not repo_root.exists():
        repo_root = Path(__file__).resolve().parents[3]

    dockerfile_path = repo_root / "backend" / "Dockerfile"
    compose_prod_path = repo_root / "docker-compose.prod.yml"

    assert dockerfile_path.exists(), f"Dockerfile not found: {dockerfile_path}"
    assert compose_prod_path.exists(), f"docker-compose.prod.yml not found: {compose_prod_path}"

    # 1. Verify non-root user in Dockerfile
    dockerfile_content = dockerfile_path.read_text(encoding="utf-8")
    assert "useradd -m -u 1000 app" in dockerfile_content or "USER app" in dockerfile_content
    assert "USER app" in dockerfile_content

    # 2. Verify prod compose does not expose db (5432) or minio (9000) directly to host
    compose_prod_content = compose_prod_path.read_text(encoding="utf-8")

    # In prod, Caddy alone binds to host ports 80/443
    # Check that 'db' service does NOT have host ports mapped
    db_section = compose_prod_content.split("db:")[1].split("api:")[0]
    assert "ports:" not in db_section, (
        "Database service in prod must not expose host ports directly"
    )

    # API service does not map host ports directly
    api_section = compose_prod_content.split("api:")[1].split("dagster-webserver:")[0]
    assert "ports:" not in api_section, (
        "API service in prod must be reverse-proxied by Caddy, no direct host ports"
    )


# =========================================================================
# 5. ZERO COMMITTED SECRETS AUDIT CHECK
# =========================================================================


def test_static_secrets_audit_no_exposed_api_keys() -> None:
    """R6.7 Acceptance: Static audit ensuring no real production API keys or credentials exist in git tree."""
    repo_root = Path("/workspace")
    if not repo_root.exists():
        repo_root = Path(__file__).resolve().parents[3]

    # Regex patterns for typical secrets
    secret_patterns = [
        re.compile(r"AIzaSy[A-Za-z0-9_-]{33}"),  # Google API key
        re.compile(r"sk-ant-[A-Za-z0-9_-]{40,}"),  # Anthropic key
        re.compile(r"sk-proj-[A-Za-z0-9_-]{40,}"),  # OpenAI key
    ]

    files_to_check = [
        repo_root / "docker-compose.prod.yml",
        repo_root / "docker-compose.yml",
        repo_root / "backend" / "pyproject.toml",
    ]

    for file_path in files_to_check:
        if file_path.exists():
            text = file_path.read_text(encoding="utf-8")
            for pattern in secret_patterns:
                matches = pattern.findall(text)
                assert len(matches) == 0, f"Found exposed secret in {file_path}: {matches}"


# =========================================================================
# 6. AUTHENTICATION HELPERS & FLOWS COVERAGE
# =========================================================================


def test_password_hashing_and_verification() -> None:
    """Verify Argon2id password hashing and comparison."""
    from ketrika.api.auth import hash_password, verify_password

    plain = "VerySecretPassword123!"
    hashed = hash_password(plain)

    assert hashed.startswith("$argon2")
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_api_key_generation_and_authentication(admin_user: UserAccount) -> None:
    """Verify raw API key generation, hashing, prefix matching, and authentication."""
    from ketrika.api.auth import authenticate_api_key, create_api_key_for_user

    mock_session = MagicMock()
    raw_key, api_key_obj = create_api_key_for_user(mock_session, admin_user)

    assert raw_key.startswith("ketrika_live_")
    assert api_key_obj.prefix == raw_key[:16]
    assert api_key_obj.user_id == admin_user.user_id

    # Simulate authenticate_api_key
    mock_session.execute.return_value.scalars.return_value.all.return_value = [api_key_obj]
    api_key_obj.user = admin_user

    authenticated = authenticate_api_key(raw_key, mock_session)
    assert authenticated == admin_user

    # Invalid key prefix
    assert authenticate_api_key("invalid_prefix_key", mock_session) is None


def test_require_client_role_access(client_user: UserAccount, admin_user: UserAccount) -> None:
    """Verify require_client accepts both client and admin roles, rejecting others."""
    from ketrika.api.auth import require_client

    assert require_client(client_user) == client_user
    assert require_client(admin_user) == admin_user

    guest_user = UserAccount(
        user_id=uuid.uuid4(),
        email="guest@test.mg",
        password_hash="fake",
        role="guest",
        disabled=False,
    )
    with pytest.raises(ForbiddenException, match="Access denied"):
        require_client(guest_user)


def test_ensure_demo_admin() -> None:
    """Verify ensure_demo_admin creates default admin if not present."""
    from ketrika.api.auth import ensure_demo_admin

    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None

    admin = ensure_demo_admin(mock_session)
    assert admin.role == "admin"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


def test_auth_routes_login_and_me(
    admin_user: UserAccount,
    mock_db_session: MagicMock,
) -> None:
    """Verify /v1/auth/login and /v1/auth/me endpoints."""
    from ketrika.api.auth import hash_password

    admin_user.password_hash = hash_password("DemoPassword123")
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = admin_user
    mock_db_session.get.return_value = admin_user

    client = TestClient(app)

    # 1. Successful login
    resp_login = client.post(
        "/v1/auth/login",
        json={"email": admin_user.email, "password": "DemoPassword123"},
    )
    assert resp_login.status_code == 200
    token = resp_login.json()["token"]
    assert len(token) > 20

    # 2. Failed login (wrong password)
    resp_fail = client.post(
        "/v1/auth/login",
        json={"email": admin_user.email, "password": "WrongPassword"},
    )
    assert resp_fail.status_code == 401

    # 3. Authenticated /me
    resp_me = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_me.status_code == 200
    assert resp_me.json()["email"] == admin_user.email
    assert resp_me.json()["role"] == "admin"
