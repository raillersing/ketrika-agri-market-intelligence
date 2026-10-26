"""Session invalidation on the real isolated PostgreSQL ledger, across processes."""

import hashlib
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from ketrika.api.main import app
from ketrika.api.rate_limit import rate_limiter
from ketrika.core.settings import get_settings
from tests.api_fixtures import login_test_admin


@pytest.mark.integration
def test_logout_is_shared_with_another_api_process():
    rate_limiter.reset()
    with TestClient(app) as first_worker, TestClient(app) as second_worker:
        token = login_test_admin(first_worker)
        headers = {"Authorization": f"Bearer {token}"}
        assert second_worker.get("/v1/auth/me", headers=headers).status_code == 200
        response = first_worker.post("/v1/auth/logout")
        assert response.status_code == 200 and response.json()["revoked"] is True
        assert second_worker.get("/v1/auth/me", headers=headers).status_code == 401
        assert second_worker.post("/v1/auth/logout", headers=headers).status_code == 200

    engine = create_engine(get_settings().database_url)
    try:
        with Session(engine) as session:
            assert (
                session.scalar(
                    text("SELECT count(*) FROM auth.token_revocation WHERE token_sha256=:digest"),
                    {"digest": hashlib.sha256(token.encode()).hexdigest()},
                )
                == 1
            )
    finally:
        engine.dispose()

    # A freshly started interpreter has neither the first session nor its memory.
    code = """
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from ketrika.api.auth import decode_access_token
from ketrika.api.errors import UnauthorizedException
from ketrika.core.settings import get_settings
engine = create_engine(get_settings().database_url)
try:
    with Session(engine) as session:
        try:
            decode_access_token(os.environ['SESSION_TEST_TOKEN'], session)
        except UnauthorizedException as error:
            assert 'terminated' in error.detail
        else:
            raise AssertionError('revoked session accepted by a fresh process')
finally:
    engine.dispose()
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "SESSION_TEST_TOKEN": token},
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, "Fresh process did not confirm PostgreSQL revocation"
    rate_limiter.reset()
