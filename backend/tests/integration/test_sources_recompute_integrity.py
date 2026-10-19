"""Real isolated SQL/API integrity; no claim of newly acquired market data."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from ketrika.api.main import app
from ketrika.core.db import get_session


def counts():
    with get_session() as session:
        return tuple(
            session.scalar(text("SELECT count(*) FROM " + table))
            for table in ("meta.ingestion_run", "meta.source_record", "obs.price_observation")
        )


@pytest.mark.integration
def test_recompute_does_not_fabricate_runs_or_acquisition():
    before = counts()
    client = TestClient(app)
    anonymous = client.post("/v1/sources/refresh")
    assert anonymous.status_code == 401
    assert counts() == before
    login = client.post(
        "/v1/auth/login", json={"email": "admin@ketrika.local", "password": "change-me"}
    )
    assert login.status_code == 200
    response = client.post("/v1/sources/refresh")
    # Existing synthetic QA rows can correctly fail the real provenance gate.
    assert response.status_code in (200, 503)
    if response.status_code == 200:
        assert response.json()["collection_performed"] is False
        assert response.json()["new_records_count"] == 0
    assert counts() == before
    history = client.get("/v1/sources/runs?limit=6")
    assert history.status_code == 200 and len(history.json()) <= 6
