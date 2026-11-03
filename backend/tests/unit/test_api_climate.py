"""Tests for agroclimate API endpoints, explainability and transparency (ADR-087, SPECS §19, §26, R4.11)."""

from __future__ import annotations

import datetime
from collections.abc import Generator
from types import SimpleNamespace
from typing import Any, Self
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from ketrika.api.main import app
from ketrika.api.routers import climate
from ketrika.core.db import get_db
from ketrika.core.models.db import Location, WeatherForecast

pytestmark = pytest.mark.usefixtures("authenticated_unit_reader")


@pytest.fixture
def mock_db_session():
    """Create a mock database session returning controlled agroclimate records."""
    session = MagicMock()

    # Mock Location
    loc = Location(
        pcode="MDG11",
        name="Analamanga",
        admin_level=1,
    )
    session.query.return_value.filter.return_value.first.return_value = loc

    # Mock execute for SQL queries with side_effect
    def mock_execute(statement: Any, params: dict[str, Any] | None = None) -> MagicMock:
        sql_str = str(statement)
        mock_res = MagicMock()
        if "gold.weather_monthly" in sql_str and "LIMIT 1" in sql_str:
            mock_res.fetchone.return_value = ("2026-10-01", 120.5, 98.0, 22.1)
        elif "gold.weather_monthly" in sql_str:
            mock_res.fetchall.return_value = (
                [
                    (
                        "MDG11",
                        "Analamanga",
                        "2026-10-01",
                        120.5,
                        98.0,
                        22.1,
                        60.8586,
                        ["nasa_power"],
                    ),
                ]
                if "baseline_precip_mm" in sql_str
                else [
                    ("MDG11", "Analamanga", "2026-10-01", 120.5, 98.0, 22.1, ["nasa_power"]),
                ]
            )
        elif "obs.weather_observation" in sql_str:
            mock_res.fetchall.return_value = [("nasa_power",)]
        elif "obs.weather_forecast" in sql_str and "LIMIT 1" in sql_str:
            mock_res.fetchone.return_value = (
                "00000000-0000-0000-0000-000000000002",
                "ecmwf_ifs",
                "2026-10-16T00:00:00Z",
                15.4,
                7.2,
                29.8,
                72,
            )
        elif "obs.event" in sql_str:
            mock_res.fetchall.return_value = [
                (
                    "00000000-0000-0000-0000-000000000001",
                    "fewsnet_mdg",
                    "MDG11",
                    "Analamanga",
                    "food_security_outlook",
                    "warning",
                    "Perspective soudure Vakinankaratra / Analamanga",
                    "Conditions hydriques stables favorables aux cultures de bas-fonds.",
                    "2026-10-10T12:00:00Z",
                    True,
                    2,
                    "FEWS NET Madagascar Outlook Octobre 2026",
                )
            ]
        else:
            mock_res.fetchall.return_value = []
            mock_res.fetchone.return_value = None
        return mock_res

    session.execute.side_effect = mock_execute

    # Mock ORM query for WeatherForecast
    wf = WeatherForecast(
        model_name="ecmwf_ifs",
        issued_at=datetime.datetime(2026, 10, 16, 0, 0, tzinfo=datetime.UTC),
        valid_from=datetime.datetime(2026, 10, 17, 0, 0, tzinfo=datetime.UTC),
        valid_to=datetime.datetime(2026, 10, 19, 0, 0, tzinfo=datetime.UTC),
        horizon_hours=72,
        variable="precip_mm",
        predicted_value=15.4,
        predicted_p10=7.2,
        predicted_p90=29.8,
        unit="mm",
        method="zonal_mean",
        spatial_resolution="0.1_deg",
    )
    # Mock query(WeatherForecast, Location)
    session.query.return_value.join.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
        (wf, loc)
    ]
    session.query.return_value.join.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
        (wf, loc)
    ]

    return session


@pytest.fixture
def climate_clock(monkeypatch):
    class FixedDateTime(datetime.datetime):
        moment = datetime.datetime(2026, 10, 18, tzinfo=datetime.UTC)

        @classmethod
        def now(cls, tz: datetime.tzinfo | None = None) -> Self:
            return cls.fromtimestamp(cls.moment.timestamp(), tz=tz)

    monkeypatch.setattr(
        climate,
        "datetime",
        SimpleNamespace(
            datetime=FixedDateTime,
            date=datetime.date,
            timedelta=datetime.timedelta,
            UTC=datetime.UTC,
        ),
    )
    return FixedDateTime


@pytest.fixture
def client(mock_db_session, climate_clock) -> Generator[TestClient, None, None]:
    """Create FastAPI test client with mocked DB dependency."""
    app.dependency_overrides[get_db] = lambda: mock_db_session
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_climate_summary_endpoint(client: TestClient):
    """Verify /v1/climate/summary delivers multi-layer explainable agroclimate data."""
    res = client.get("/v1/climate/summary?location=MDG11&month=2026-10-01")
    assert res.status_code == 200

    data = res.json()
    assert data["location_pcode"] == "MDG11"
    assert data["current_month"] == "2026-10-01"

    # Layer 1: Observed Weather & Explanatory Aggregation Method
    assert data["observed_source"] == "nasa_power"
    assert "zonal_mean" in data["aggregation_method"]
    assert "sans masque agricole vérifié" in data["aggregation_method"]
    assert data["cropland_mask_applied"] is False

    # Layer 2: Climate Anomalies & Risk Level
    assert data["precipitation_risk_level"] is None  # Reference not qualified.

    # Layer 3: Forecast Weather (ECMWF Open Data)
    assert data["forecast_value_kind"] == "projected"
    assert data["forecast_model"] is not None
    assert data["forecast_next_72h_precip_mm"] is not None
    assert data["forecast_p10_mm"] is not None
    assert data["forecast_p90_mm"] is not None

    # Layer 4: Dynamic Active Crop Cycles & Trade Corridors
    active_cycles = data["active_crop_cycles"]
    assert len(active_cycles) >= 1
    # Check that phenological stage is detected for month 10 (October)
    vakiambiaty = next(c for c in active_cycles if c["crop_cycle"] == "vakiambiaty")
    assert vakiambiaty["current_phenological_stage"] == "planting"
    assert len(vakiambiaty["market_links"]) >= 1

    # Layer 5: Facultative Sources Transparency
    facultative = data["facultative_sources"]
    assert len(facultative) == 3
    for src in facultative:
        assert src["status"] == "unavailable"
        assert src["data_available"] is False
        assert "facultative" in src["reason"].lower() or "optionnelle" in src["reason"].lower()


def test_climate_anomalies_endpoint(client: TestClient):
    """Verify /v1/climate/anomalies returns time series with baseline and value_kind='observed'."""
    res = client.get("/v1/climate/anomalies?location=MDG11&from=2026-01-01&to=2026-10-01")
    assert res.status_code == 200

    items = res.json()
    assert len(items) >= 1
    first = items[0]
    assert first["location_pcode"] == "MDG11"
    assert first["value_kind"] == "observed"
    assert first["sources"] == ["nasa_power"]
    assert first["baseline_years"] is None
    assert first["baseline_mean"] == 60.8586
    assert first["aggregation_method"] == "zonal_mean"
    assert first["cropland_mask_applied"] is False


def test_climate_forecasts_endpoint(client: TestClient):
    """Verify /v1/climate/forecasts returns archived NWP projections with value_kind='projected'."""
    res = client.get("/v1/climate/forecasts?location=MDG11")
    assert res.status_code == 200

    items = res.json()
    assert len(items) >= 1
    fc = items[0]
    assert fc["model_name"] == "ecmwf_ifs"
    assert fc["horizon_hours"] == 72
    assert fc["value_kind"] == "projected"
    assert fc["predicted_p10"] <= fc["predicted_p90"]
    assert fc["source"] == "ecmwf_open"


def test_crop_calendars_endpoint(client: TestClient):
    """Verify /v1/climate/calendars dynamic evaluation and documented trade corridors."""
    # Test for Lac Alaotra in month 5 (May -> harvest)
    res = client.get("/v1/climate/calendars?zone_code=ZONE_ALAOTRA&month=5")
    assert res.status_code == 200

    calendars = res.json()
    assert len(calendars) >= 1
    alaotra = calendars[0]
    assert alaotra["zone_code"] == "ZONE_ALAOTRA"
    assert alaotra["current_phenological_stage"] in ("peak_harvest", "harvest")
    assert alaotra["eligible_for_alerts"] is True

    # Corridors to Antananarivo and Toamasina must be present
    destinations = {link["location_code"] for link in alaotra["market_links"]}
    assert "MDG11" in destinations
    assert "MDG31" in destinations

    # Test for Grand Sud maize in month 12 (December -> planting)
    res_sud = client.get("/v1/climate/calendars?zone_code=ZONE_SUD&product=MAIZE_GRAIN&month=12")
    assert res_sud.status_code == 200
    sud_maize = res_sud.json()
    assert len(sud_maize) >= 1
    assert sud_maize[0]["current_phenological_stage"] == "planting"


def test_climate_events_endpoint(client: TestClient):
    """Verify /v1/climate/events delivers food security outlooks with projection status."""
    res = client.get("/v1/climate/events?location=MDG11")
    assert res.status_code == 200

    events = res.json()
    assert len(events) >= 1
    ev = events[0]
    assert ev["source_id"] == "fewsnet_mdg"
    assert ev["is_projected"] is True
    assert ev["ipc_phase"] == 2


def test_facultative_sources_status_endpoint(client: TestClient):
    """Verify /v1/climate/facultative-status transparently lists unconfigured sources."""
    res = client.get("/v1/climate/facultative-status")
    assert res.status_code == 200

    sources = res.json()
    assert len(sources) == 3
    source_ids = {s["source_id"] for s in sources}
    assert "firms_mdg" in source_ids
    assert "glofas_mdg" in source_ids
    assert "copernicus_ndvi" in source_ids
    for s in sources:
        assert s["status"] == "unavailable"
        assert s["data_available"] is False


def test_weather_anomalies_backward_compatibility(client: TestClient):
    """Verify /v1/weather/anomalies endpoint remains functional for backward compatibility."""
    res = client.get("/v1/weather/anomalies?location=MDG11")
    assert res.status_code == 200

    items = res.json()
    assert len(items) >= 1
    assert items[0]["district_pcode"] == "MDG11"
    assert items[0]["value_kind"] == "observed"


def test_historical_month_never_receives_current_weather_forecast(
    client, climate_clock, mock_db_session
):
    climate_clock.moment = datetime.datetime(2026, 11, 18, tzinfo=datetime.UTC)
    response = client.get("/v1/climate/summary?location=MDG11&month=2026-10-01")
    assert response.status_code == 200
    data = response.json()
    assert data["forecast_model"] is None
    assert data["forecast_next_72h_precip_mm"] is None
    assert data["forecast_p10_mm"] is None and data["forecast_p90_mm"] is None
    assert not any(
        "FROM obs.weather_forecast" in str(call.args[0])
        for call in mock_db_session.execute.call_args_list
    )
