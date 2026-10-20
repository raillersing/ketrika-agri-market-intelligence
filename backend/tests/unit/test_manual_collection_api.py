"""No collection is authorized by a reader or an unauthenticated request."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ketrika.api.auth import get_current_user
from ketrika.api.errors import ProblemDetailException, problem_exception_handler
from ketrika.api.routers import sources


@pytest.fixture
def api(monkeypatch):
    app = FastAPI()
    app.add_exception_handler(ProblemDetailException, problem_exception_handler)
    app.include_router(sources.router)
    owner = Mock(return_value={"status": "failed"})
    monkeypatch.setattr(sources.manual_collection, "collect", owner)
    return app, TestClient(app), owner


@pytest.mark.parametrize("role,expected", [(None, 401), ("analyst", 403), ("admin", 200)])
def test_role_is_checked_before_collect(api, role, expected):
    app, client, owner = api
    if role:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=role)
    response = client.post("/v1/sources/collect", json={"request_id": str(uuid4())})
    assert response.status_code == expected
    assert owner.call_count == int(expected == 200)


@pytest.mark.parametrize(
    "body",
    [{}, {"request_id": "invalid"}, {"request_id": str(uuid4()), "source_id": "https://private/"}],
)
def test_invalid_selection_is_not_executed(api, body):
    app, client, owner = api
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="admin")
    assert client.post("/v1/sources/collect", json=body).status_code == 422
    owner.assert_not_called()


@pytest.mark.parametrize(
    "path", ["/collections", "/collections/" + str(uuid4()), "/collection-options"]
)
def test_tracking_is_authenticated(api, path):
    _, client, _ = api
    assert client.get("/v1/sources" + path).status_code == 401
