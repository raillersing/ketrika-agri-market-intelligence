"""API contract tests: no network, no fabricated ingestion and guarded publication."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from ketrika.api.auth import get_current_user
from ketrika.api.errors import ProblemDetailException, problem_exception_handler
from ketrika.api.routers import sources
from ketrika.core.db import get_db


@pytest.fixture
def api(monkeypatch):
    app = FastAPI()
    app.add_exception_handler(ProblemDetailException, problem_exception_handler)
    app.include_router(sources.router)
    session = MagicMock()
    session.scalar.return_value = True
    session.execute.return_value.fetchone.return_value = ("active",)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="admin")
    publish = MagicMock(return_value={"views_refreshed": ["price_obs_current"]})
    monkeypatch.setattr(sources, "refresh_gold_views", publish)
    return app, TestClient(app), session, publish


@pytest.mark.parametrize("path", ["/v1/sources/refresh", "/v1/sources/miasa_odr/refresh"])
def test_recompute_calls_guard_and_never_invents_ingestion(api, path):
    _, client, session, publish = api
    response = client.post(path)
    assert response.status_code == 200
    result = response.json()
    assert result["action"] == "recompute"
    assert result["collection_performed"] is False
    assert result["new_records_count"] == 0
    assert "records_count" not in result
    assert result["views_refreshed"] == ["price_obs_current"]
    publish.assert_called_once_with(session, views=sources.RECOMPUTE_VIEWS)
    assert "economic_dashboard" not in sources.RECOMPUTE_VIEWS
    statements = [str(call.args[0]).upper() for call in session.execute.call_args_list]
    assert not any("INSERT" in stmt or "REFRESH MATERIALIZED" in stmt for stmt in statements)
    session.commit.assert_called_once()


@pytest.mark.parametrize(
    "error", [ValueError("private-proof-or-key"), SQLAlchemyError("private-DSN")]
)
def test_failed_publication_rolls_back_and_hides_diagnostics(api, error):
    _, client, session, publish = api
    publish.side_effect = error
    response = client.post("/v1/sources/refresh")
    assert response.status_code == 503
    assert "private" not in response.text
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_busy_lock_refuses_duplicate_before_publication(api):
    _, client, session, publish = api
    session.scalar.return_value = False
    assert client.post("/v1/sources/refresh").status_code == 409
    publish.assert_not_called()
    session.rollback.assert_called_once()


@pytest.mark.parametrize("status", ["disabled", "degraded", "pending"])
def test_unavailable_source_is_not_recomputed(api, status):
    _, client, session, publish = api
    session.execute.return_value.fetchone.return_value = (status,)
    assert client.post("/v1/sources/wfp_hdx_mdg/refresh").status_code == 409
    publish.assert_not_called()
    session.commit.assert_not_called()


def test_unknown_source_is_not_recomputed(api):
    _, client, session, publish = api
    session.execute.return_value.fetchone.return_value = None
    assert client.post("/v1/sources/unknown/refresh").status_code == 404
    publish.assert_not_called()


@pytest.mark.parametrize("path", ["/v1/sources/refresh", "/v1/sources/miasa_odr/refresh"])
def test_non_admin_cannot_publish(api, path):
    app, client, session, publish = api
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="client")
    assert client.post(path).status_code == 403
    publish.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "path", ["/v1/sources/refresh", "/v1/sources/miasa_odr/refresh", "/v1/sources/runs"]
)
def test_anonymous_requests_are_rejected(api, path):
    app, client, _, publish = api
    del app.dependency_overrides[get_current_user]
    response = client.get(path) if path.endswith("/runs") else client.post(path)
    assert response.status_code == 401
    publish.assert_not_called()


def test_history_preserves_unknowns_and_redacts_error(api):
    _, client, session, _ = api
    session.execute.return_value.fetchall.return_value = [
        ("id", "source", "Name", "failed", datetime.now(UTC), None, None, None, None, "secret SQL")
    ]
    response = client.get("/v1/sources/runs?limit=500")
    assert response.status_code == 200
    record = response.json()[0]
    assert record["n_records"] is None and record["duration_seconds"] is None
    assert "secret" not in response.text
    assert session.execute.call_args.args[1] == {"lim": 50}
    session.commit.assert_not_called()
