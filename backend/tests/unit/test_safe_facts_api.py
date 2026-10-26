"""No demonstration facts escape missing data or invalid API parameters (ADR-121)."""

from collections.abc import Iterator
from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from ketrika.api.main import app
from ketrika.core.db import get_db
from ketrika.core.models.db import Location

pytestmark = pytest.mark.usefixtures("authenticated_unit_reader")


@pytest.fixture
def safe_client() -> Iterator[tuple[TestClient, MagicMock]]:
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = Location(
        pcode="MDG99", name="Test zone", admin_level=1
    )
    session.execute.return_value.fetchone.return_value = None
    session.execute.return_value.fetchall.return_value = []
    app.dependency_overrides[get_db] = lambda: session
    try:
        with patch("ketrika.api.routers.climate.is_gold_view_populated", return_value=True):
            yield TestClient(app, raise_server_exceptions=False), session
    finally:
        app.dependency_overrides.clear()


def test_empty_climate_has_no_numbers_model_source_risk_or_default_basin(safe_client):
    client, _ = safe_client
    response = client.get("/v1/climate/summary?location=MDG99")
    assert response.status_code == 200
    data = response.json()
    for key in (
        "observed_precipitation_mm",
        "temperature_mean_c",
        "precipitation_anomaly_pct",
        "precipitation_risk_level",
        "observed_source",
        "forecast_model",
        "forecast_issued_at",
        "forecast_next_72h_precip_mm",
        "forecast_p10_mm",
        "forecast_p90_mm",
    ):
        assert data[key] is None, key
    assert data["active_crop_cycles"] == []


def test_requested_month_is_bound_and_forecasts_excluded_for_history(safe_client):
    client, session = safe_client
    response = client.get("/v1/climate/summary?location=MDG99&month=2020-03-01")
    assert response.status_code == 200
    calls = session.execute.call_args_list
    observed = next(call for call in calls if "gold.weather_monthly" in str(call.args[0]))
    assert observed.args[1]["requested_month"] == date(2020, 3, 1)
    assert "CAST(:requested_month AS date)" in str(observed.args[0])
    assert all("obs.weather_forecast" not in str(call.args[0]) for call in calls)


def test_forecast_query_limits_variable_unit_horizon_cutoff_revision_and_validity(safe_client):
    client, session = safe_client
    assert client.get("/v1/climate/summary?location=MDG99").status_code == 200
    query = next(
        call
        for call in session.execute.call_args_list
        if "obs.weather_forecast" in str(call.args[0])
    )
    sql = str(query.args[0])
    for condition in (
        "wf.variable = 'precip_mm'",
        "wf.unit = 'mm'",
        "wf.horizon_hours = 72",
        "wf.issued_at <= :now",
        "wf.valid_from <= :now",
        "wf.valid_to > :now",
        "wf.superseded_by IS NULL",
    ):
        assert condition in sql
    assert isinstance(query.args[1]["now"], datetime)
    assert query.args[1]["now"].tzinfo == UTC


@pytest.mark.parametrize(
    "url",
    [
        "/v1/climate/summary?month=wrong",
        "/v1/climate/summary?month=2026-10-02",
        "/v1/climate/anomalies?variable=wind",
        "/v1/climate/anomalies?from=wrong",
        "/v1/climate/anomalies?from=2026-10-01&to=2026-01-01",
        "/v1/weather/anomalies?from=2026-10-01&to=2026-01-01",
        "/v1/supply/peak-forecast?campaign=wrong",
        "/v1/supply/peak-forecast",
    ],
)
def test_invalid_parameters_do_not_become_fallbacks(safe_client, url):
    client, _ = safe_client
    assert client.get(url).status_code == 422


def test_unknown_zone_is_not_substituted(safe_client):
    client, session = safe_client
    session.query.return_value.filter.return_value.first.return_value = None
    assert client.get("/v1/climate/summary?location=UNKNOWN").status_code == 404
    session.execute.assert_not_called()


def test_supply_sql_error_is_not_empty_history(safe_client):
    client, session = safe_client
    session.query.return_value.join.side_effect = OperationalError("SQL", {}, Exception("test"))
    assert (
        client.get("/v1/supply/sufficiency?market_code=MDG99&product=RICE_PADDY").status_code == 500
    )


def test_temperature_is_not_reported_as_rainfall_anomaly(safe_client):
    client, session = safe_client
    session.execute.return_value.fetchall.return_value = [
        ("MDG99", "Test zone", "2026-10-01", 123.0, 35.0, 0.0, 91.0, ["nasa_power"])
    ]
    with patch("ketrika.api.routers.climate.require_gold_view"):
        response = client.get("/v1/climate/anomalies?variable=t2m_c")
    assert response.status_code == 200
    row = response.json()[0]
    assert row["observed_value"] == 0.0
    assert row["anomaly_pct"] is None
    assert row["baseline_mean"] is None
    assert row["risk_level"] is None
