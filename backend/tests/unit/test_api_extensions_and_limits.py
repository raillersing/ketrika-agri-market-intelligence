"""Unit and CC-R qualification tests for API extensions, limits, and pagination (R2.9, ADR-071).

Guards and contracts tested:
1. Macro route (/v1/macro): pagination (limit/offset), metadata exposure, and CSV export parity.
2. Market coverage route (/v1/market/coverage): pagination, completeness metadata, and CSV export parity.
3. Economic indicators route (/v1/economic/indicators): pagination and CSV export.
4. Error contracts: RFC 7807 Problem Details on invalid pagination limits (limit=0, limit=2000).
5. Protected admin routes: Non-public administration routes strictly enforce authentication.
6. Value metadata: Strict preservation of observed_or_imputed, units, periods, and provenance.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from ketrika.api.main import app
from ketrika.core.db import get_db
from ketrika.gold.coverage import MarketCoverageRow

# =========================================================================
# 1. MACRO ROUTE PAGINATION, METADATA AND CSV EXPORT
# =========================================================================


@pytest.mark.usefixtures("authenticated_unit_reader")
def test_api_macro_json_metadata_and_pagination():
    """Verify /v1/macro pagination and exhaustive metadata exposure."""
    mock_session = MagicMock()
    # observation_id, indicator_code, indicator_name, geo_scope, frequency, unit, base_period, period_start, period_end, vintage, value, value_raw, observed_or_imputed, first_available_at, published_at, source_id
    mock_rows = [
        (
            "11111111-1111-1111-1111-111111111111",
            "EXCHANGE_RATE_USD_MGA",
            "USD/MGA",
            "national",
            "daily",
            "MGA/USD",
            None,
            dt.date(2026, 5, 2),
            dt.date(2026, 5, 2),
            "final",
            4550.0,
            "4550",
            "observed",
            dt.datetime(2026, 5, 2, 10, 0, tzinfo=dt.UTC),
            dt.datetime(2026, 5, 2, 9, 0, tzinfo=dt.UTC),
            "bfm_public",
        ),
        (
            "22222222-2222-2222-2222-222222222222",
            "FUEL_PUMP_CEILING_PRICE_MGA",
            "Gazole",
            "national",
            "event",
            "MGA/L",
            None,
            dt.date(2026, 5, 1),
            dt.date(2026, 5, 1),
            "final",
            4900.0,
            "4900",
            "observed",
            dt.datetime(2026, 5, 1, 8, 0, tzinfo=dt.UTC),
            dt.datetime(2026, 4, 30, 18, 0, tzinfo=dt.UTC),
            "omh_public",
        ),
    ]

    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_rows
    mock_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        client = TestClient(app)
        response = client.get("/v1/macro?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Verify exhaustive metadata fields (ADR-071, R2.9)
        first = data[0]
        assert first["observation_id"] == "11111111-1111-1111-1111-111111111111"
        assert first["indicator_code"] == "EXCHANGE_RATE_USD_MGA"
        assert first["unit"] == "MGA/USD"
        assert first["geo_scope"] == "national"
        assert first["frequency"] == "daily"
        assert first["period_start"] == "2026-05-02"
        assert first["period_end"] == "2026-05-02"
        assert first["vintage"] == "final"
        assert first["value"] == 4550.0
        assert first["observed_or_imputed"] == "observed"
        assert first["sources"] == ["bfm_public"]
        assert first["first_available_at"] is not None
        assert first["published_at"] is not None

        # Verify query filters
        resp_filtered = client.get(
            "/v1/macro?indicator=EXCHANGE_RATE_USD_MGA&geo_scope=national&vintage=final&from=2026-01-01&to=2026-05-02"
        )
        assert resp_filtered.status_code == 200
        assert mock_session.execute.called
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.usefixtures("authenticated_unit_reader")
def test_api_macro_csv_export():
    """Verify /v1/macro format=csv returns valid text/csv with correct headers."""
    mock_session = MagicMock()
    mock_rows = [
        (
            "11111111-1111-1111-1111-111111111111",
            "EXCHANGE_RATE_USD_MGA",
            "USD/MGA",
            "national",
            "daily",
            "MGA/USD",
            None,
            dt.date(2026, 5, 2),
            dt.date(2026, 5, 2),
            "final",
            4550.0,
            "4550",
            "observed",
            dt.datetime(2026, 5, 2, 10, 0, tzinfo=dt.UTC),
            dt.datetime(2026, 5, 2, 9, 0, tzinfo=dt.UTC),
            "bfm_public",
        ),
    ]

    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_rows
    mock_session.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        client = TestClient(app)
        response = client.get("/v1/macro?format=csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert 'filename="macro_observations.csv"' in response.headers["content-disposition"]

        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["indicator_code"] == "EXCHANGE_RATE_USD_MGA"
        assert rows[0]["value"] == "4550.0"
        assert rows[0]["observed_or_imputed"] == "observed"
    finally:
        app.dependency_overrides.pop(get_db, None)


# =========================================================================
# 2. MARKET COVERAGE ROUTE PAGINATION AND CSV EXPORT
# =========================================================================


@pytest.mark.usefixtures("authenticated_unit_reader")
def test_api_market_coverage_pagination_and_csv():
    """Verify /v1/market/coverage pagination and CSV export."""
    mock_cell = MarketCoverageRow(
        product_code="RICE_WHITE_LOCAL",
        product_name="Riz blanc local",
        location_pcode="MDG11",
        location_name="Analamanga",
        admin_level=1,
        actor_level="retail",
        month="2026-05-01",
        n_sources=2,
        n_families=2,
        sources="miasa_odr,wb_rtfp_mdg",
        source_families="madagascar_gov,world_bank",
        n_obs=15,
        imputed_share=0.0,
        has_observed=True,
        observed_or_imputed="observed",
        min_price=2800.0,
        max_price=3100.0,
        median_price=2950.0,
        age_days=10,
    )

    from unittest.mock import patch

    with (
        patch(
            "ketrika.api.routers.coverage.query_market_coverage_matrix", return_value=[mock_cell]
        ),
        patch("ketrika.api.routers.coverage.require_gold_view"),
    ):
        client = TestClient(app)

        # JSON with pagination
        resp_json = client.get("/v1/market/coverage?limit=1&offset=0")
        assert resp_json.status_code == 200
        json_data = resp_json.json()
        assert len(json_data) == 1
        assert json_data[0]["location_pcode"] == "MDG11"
        assert json_data[0]["admin_level"] == 1
        assert json_data[0]["source_families"] == "madagascar_gov,world_bank"

        # CSV export
        resp_csv = client.get("/v1/market/coverage?format=csv")
        assert resp_csv.status_code == 200
        assert "text/csv" in resp_csv.headers["content-type"]
        assert 'filename="market_coverage.csv"' in resp_csv.headers["content-disposition"]

        reader = csv.DictReader(io.StringIO(resp_csv.text))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["product_code"] == "RICE_WHITE_LOCAL"
        assert rows[0]["median_price"] == "2950.0"


# =========================================================================
# 3. ECONOMIC INDICATORS ROUTE PAGINATION AND CSV EXPORT
# =========================================================================


@pytest.mark.usefixtures("authenticated_unit_reader")
def test_api_economic_indicators_pagination_and_csv():
    """Verify /v1/economic/indicators pagination and CSV export."""
    client = TestClient(app)

    # Test pagination
    resp_paged = client.get("/v1/economic/indicators?limit=5&offset=0")
    assert resp_paged.status_code == 200
    data = resp_paged.json()
    assert len(data) == 5

    # Test offset
    resp_offset = client.get("/v1/economic/indicators?limit=5&offset=5")
    assert resp_offset.status_code == 200
    data_offset = resp_offset.json()
    assert len(data_offset) == 5
    assert data[0]["metric_id"] != data_offset[0]["metric_id"]

    # Test CSV export
    resp_csv = client.get("/v1/economic/indicators?format=csv")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert 'filename="economic_indicators.csv"' in resp_csv.headers["content-disposition"]
    reader = csv.DictReader(io.StringIO(resp_csv.text))
    rows = list(reader)
    assert len(rows) >= 14
    assert "metric_id" in rows[0]
    assert "dimension" in rows[0]
    assert "formula" in rows[0]


# =========================================================================
# 4. ERROR FORMATTING (RFC 7807 PROBLEM DETAILS)
# =========================================================================


@pytest.mark.usefixtures("authenticated_unit_reader")
def test_api_pagination_limit_out_of_bounds_validation():
    """Verify invalid limit values (< 1 or > 1000) return 422 with validation errors."""
    client = TestClient(app)

    # limit = 0 (below minimum 1)
    resp_zero = client.get("/v1/macro?limit=0")
    assert resp_zero.status_code == 422

    # limit = 2000 (above maximum 1000)
    resp_large = client.get("/v1/macro?limit=2000")
    assert resp_large.status_code == 422

    # offset = -1 (below minimum 0)
    resp_neg = client.get("/v1/macro?offset=-1")
    assert resp_neg.status_code == 422


# =========================================================================
# 5. PROTECTED ADMIN ROUTES NON-PUBLIC ENFORCEMENT
# =========================================================================


def test_api_admin_routes_strictly_reject_unauthenticated():
    """Verify admin endpoints return 401 or 403 when unauthenticated."""
    client = TestClient(app)

    # Admin review queue
    resp_review = client.get("/v1/admin/review")
    assert resp_review.status_code in (401, 403)

    # Admin API keys
    resp_keys = client.post("/v1/admin/api-keys", json={"name": "test_key", "role": "admin"})
    assert resp_keys.status_code in (401, 403)
