"""Shared revocation semantics, without touching active or qualification SQL."""

import os
import subprocess
import sys
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ketrika.api.auth import create_access_token, decode_access_token, revoke_token
from ketrika.api.errors import ProblemDetailException, UnauthorizedException
from ketrika.core.models.db import TokenRevocation, UserAccount
from ketrika.core.settings import Settings
from tests.session_fixtures import session_store_engine


def test_revocation_survives_new_connection_and_process(tmp_path):
    path = tmp_path / "revocation.db"
    engine = session_store_engine(path)
    user = UserAccount(user_id=uuid4(), email="test@ketrika.local", role="client")
    token = create_access_token(user)
    another_token = create_access_token(user)
    assert token != another_token
    with Session(engine) as session:
        assert decode_access_token(token, session)["sub"] == str(user.user_id)
        revoke_token(token, session)
        revoke_token(token, session)  # Duplicate logout is safe and durable.
    with Session(engine) as session:
        assert decode_access_token(another_token, session)["sub"] == str(user.user_id)
        with pytest.raises(UnauthorizedException, match="terminated"):
            decode_access_token(token, session)
        record = session.query(TokenRevocation).one()
        assert len(record.token_sha256) == 64 and record.token_sha256 != token
    code = """
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from ketrika.api.auth import decode_access_token
from ketrika.api.errors import UnauthorizedException
engine=create_engine('sqlite://')
@event.listens_for(engine,'connect')
def attach(connection, record):
    connection.execute('ATTACH DATABASE ? AS auth', (os.environ['SESSION_TEST_DB'],))
with Session(engine) as session:
    try:
        decode_access_token(os.environ['SESSION_TEST_TOKEN'], session)
    except UnauthorizedException as error:
        assert "terminated" in error.detail
        print('revoked')
    else:
        raise SystemExit('revocation was lost')
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "SESSION_TEST_DB": str(path), "SESSION_TEST_TOKEN": token},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "revoked"
    engine.dispose()


def test_invalid_expired_and_storage_failures_refuse_access():
    session = MagicMock()
    user = UserAccount(user_id=uuid4(), email="test@ketrika.local", role="client")
    for token in ("arbitrary", create_access_token(user, timedelta(seconds=-1))):
        with pytest.raises(UnauthorizedException):
            decode_access_token(token, session)
        session.get.assert_not_called()
    session.get.side_effect = OperationalError("test", {}, Exception("private detail"))
    with pytest.raises(ProblemDetailException) as error:
        decode_access_token(create_access_token(user), session)
    assert error.value.status_code == 503
    assert "private detail" not in error.value.detail


def test_production_refuses_demo_configuration_without_echoing_inputs():
    with pytest.raises(ValueError) as error:
        Settings(app_env="prod", jwt_secret="a-sensitive-test-input")
    assert "a-sensitive-test-input" not in str(error.value)
    with pytest.raises(ValueError):
        Settings(app_env="production")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("postgres_password", ""),
        ("postgres_password", "change-me"),
        ("copilot_db_password", ""),
        ("copilot_db_password", "change-me-ro"),
        ("s3_secret_key", ""),
        ("s3_secret_key", "minioadmin"),
    ],
)
def test_production_rejects_empty_or_matching_demo_secrets(field, value):
    config: dict[str, Any] = {
        "app_env": "prod",
        "bootstrap_demo_admin": False,
        "jwt_secret": "test-only-signing-material-with-more-than-32-characters",
        "postgres_password": "test-only-database-passphrase",
        "database_url": "postgresql+psycopg://test:test-only-database-passphrase@db/test",
        "copilot_db_password": "test-only-readonly-passphrase",
        "s3_secret_key": "test-only-object-store-passphrase",
    }
    config[field] = value
    with pytest.raises(ValueError, match="credentials are required"):
        Settings(**config)


def test_login_rate_key_ignores_untrusted_credentials_and_never_keeps_tokens():
    from starlette.requests import Request

    from ketrika.api.rate_limit import RateLimitMiddleware

    middleware = RateLimitMiddleware(lambda scope, receive, send: None)

    def request(path, headers):
        return Request(
            {
                "type": "http",
                "path": path,
                "headers": headers,
                "client": ("127.0.0.1", 1),
                "method": "POST",
            }
        )

    keys = {
        middleware._extract_client_key(request("/v1/auth/login", [(b"x-api-key", str(n).encode())]))
        for n in range(3)
    }
    assert keys == {"ip:127.0.0.1"}
    for header in (
        [(b"authorization", b"Bearer private-test-value")],
        [(b"cookie", b"session_token=private-test-value")],
    ):
        key = middleware._extract_client_key(request("/v1/auth/me", header))
        assert "private-test-value" not in key
        assert len(key.rsplit(":", 1)[1]) == 64
