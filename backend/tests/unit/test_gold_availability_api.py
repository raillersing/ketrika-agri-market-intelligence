"""A cache unavailable for publication is not an empty market or CSV success."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from ketrika.api.errors import ProblemDetailException, problem_exception_handler
from ketrika.api.routers import coverage, forecasts, kpis, prices, stocks, trade, weather
from ketrika.core.db import get_db
from ketrika.gold.coverage import (
    compute_series_gaps_independent_sql,
    query_market_coverage_matrix,
)

PATHS = (
    "/v1/prices",
    "/v1/prices?source=wb_rtfp_mdg",
    "/v1/prices?format=csv",
    "/v1/prices/latest",
    "/v1/stocks",
    "/v1/trade",
    "/v1/weather/anomalies",
    "/v1/kpis/market-health",
    "/v1/forecasts",
    "/v1/forecasts?format=csv",
    "/v1/market/coverage",
    "/v1/market/coverage?format=csv",
    "/v1/market/coverage/gaps?product=RICE_WHITE_LOCAL",
)


def make_api(value):
    app = FastAPI()
    app.add_exception_handler(ProblemDetailException, problem_exception_handler)
    for module in (coverage, forecasts, kpis, prices, stocks, trade, weather):
        app.include_router(module.router)
    session = MagicMock()
    session.execute.return_value.scalar.return_value = value
    session.execute.return_value.fetchall.return_value = []
    app.dependency_overrides[get_db] = lambda: session
    return TestClient(app), session


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("state", [False, None, "storage_error"])
def test_unpublished_or_unknown_never_returns_successful_empty_market(path, state):
    client, session = make_api(state)
    if state == "storage_error":
        session.execute.side_effect = SQLAlchemyError("private-database-description")
    response = client.get(path)
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "gold_not_published"
    assert "private-database" not in response.text
    assert session.execute.call_count == 1


@pytest.mark.parametrize("path", PATHS[:10])
def test_published_but_no_matching_rows_can_be_empty(path):
    client, _ = make_api(True)
    response = client.get(path)
    assert response.status_code == 200
    if "format=csv" not in path:
        assert response.json() == []


def test_historical_run_does_not_require_latest_gold_cache():
    client, session = make_api(False)
    response = client.get("/v1/forecasts?model_run_id=12345678-1234-1234-1234-123456789abc")
    assert response.status_code == 200
    assert response.json() == []
    assert "pg_matviews" not in str(session.execute.call_args)


def test_internal_coverage_cannot_fabricate_zero_coverage_from_unpublished_cache():
    _, session = make_api(False)
    with pytest.raises(ValueError, match="gold_not_published"):
        query_market_coverage_matrix(session)
    with pytest.raises(ValueError, match="gold_not_published"):
        compute_series_gaps_independent_sql(session, "RICE_WHITE_LOCAL", "MDG11", "retail")
