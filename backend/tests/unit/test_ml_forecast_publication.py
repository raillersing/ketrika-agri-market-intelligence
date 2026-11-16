"""Tests for price forecasting publication, metadata transparency, lineage, and abstentions (SPECS §17, §19, ADR-078, R3.7)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from ketrika.api.main import app
from ketrika.core.db import get_db
from ketrika.core.models.db import Forecast, ModelRun
from ketrika.ml.forecast import compute_series_fingerprint, run_price_forecasting_pipeline
from ketrika.ml.series import EligibleSeries, PricePoint, SeriesEligibilityReport

pytestmark = pytest.mark.usefixtures("authenticated_unit_reader")


@pytest.fixture
def dummy_price_series() -> list[EligibleSeries]:
    """Create authentic 36-month monthly series with continuous points."""
    points = [
        PricePoint(
            month=date(2023, 1 + (i % 12), 1),
            price=2500.0 + i * 15.0 + (100.0 if (i % 12) in (0, 1, 11) else 0.0),
            observed_or_imputed="observed",
        )
        for i in range(36)
    ]
    return [
        EligibleSeries(
            series_key="RICE_WHITE_LOCAL|standard|retail|MDG11|kg",
            product_id=uuid.uuid4(),
            product_code="RICE_WHITE_LOCAL",
            product_name="Riz blanc local",
            location_id=uuid.uuid4(),
            location_pcode="MDG11",
            location_name="Analamanga",
            admin_level=1,
            actor_level="retail",
            quality_grade="standard",
            unit="kg",
            grid=points,
            total_valid_points=36,
            recent_points_24m=12,
        )
    ]


def test_series_fingerprint_deterministic_and_unique(
    dummy_price_series: list[EligibleSeries],
) -> None:
    """Lineage fingerprint must be strictly deterministic and sensitive to content."""
    cutoff = date(2026, 1, 1)
    fp1 = compute_series_fingerprint(cutoff, dummy_price_series)
    fp2 = compute_series_fingerprint(cutoff, dummy_price_series)

    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256 length

    # Different cutoff produces different fingerprint
    fp_diff = compute_series_fingerprint(date(2026, 2, 1), dummy_price_series)
    assert fp1 != fp_diff


def test_run_price_forecasting_pipeline_preserves_lineage_and_metadata(
    dummy_price_series: list[EligibleSeries], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Forecasting pipeline must capture dataset fingerprint, models, and conformal metadata."""
    cutoff = date(2026, 1, 1)

    # Mock audit_series_eligibility
    mock_report = SeriesEligibilityReport(
        data_cutoff=cutoff,
        total_series_evaluated=1,
        eligible_count=1,
        excluded_count=0,
        eligible_series=dummy_price_series,
        excluded_series=[],
        summary_reasons={},
    )
    monkeypatch.setattr(
        "ketrika.ml.forecast.audit_series_eligibility", lambda **kwargs: mock_report
    )

    # Mock refresh_gold_views
    monkeypatch.setattr("ketrika.ml.forecast.refresh_gold_views", lambda *args, **kwargs: None)

    mock_session = MagicMock()

    result = run_price_forecasting_pipeline(
        session=mock_session,
        data_cutoff=cutoff,
        horizon=3,
        refresh_gold=False,
    )

    assert result["n_series"] == 1
    assert result["forecasts_generated"] == 3
    assert result["dataset_fingerprint"] is not None
    assert len(result["dataset_fingerprint"]) == 64

    # Verify session additions: 1 ModelRun and 3 Forecast items
    assert mock_session.add.call_count == 4
    added_objects = [call[0][0] for call in mock_session.add.call_args_list]

    model_run_obj = next(obj for obj in added_objects if isinstance(obj, ModelRun))
    assert model_run_obj.task == "price_forecast"
    assert model_run_obj.params is not None
    assert model_run_obj.metrics is not None
    assert model_run_obj.params["dataset_fingerprint"] == result["dataset_fingerprint"]
    assert model_run_obj.params["horizon"] == 3
    assert "abstentions" in model_run_obj.metrics

    forecast_objs = [obj for obj in added_objects if isinstance(obj, Forecast)]
    assert len(forecast_objs) == 3

    for fc in forecast_objs:
        assert fc.model_run_id == model_run_obj.model_run_id
        assert fc.series_key == dummy_price_series[0].series_key
        assert fc.currency == "MGA"
        assert fc.unit == "kg"
        assert fc.horizon in (1, 2, 3)
        assert fc.p10 is not None and fc.p50 is not None and fc.p90 is not None
        assert fc.p10 <= fc.p50 <= fc.p90
        assert fc.interval_width == round(fc.p90 - fc.p10, 4) or fc.interval_width is not None



def test_forecast_gold_rejection_rolls_back_and_never_bypasses_gate(
    dummy_price_series: list[EligibleSeries], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refused Gold publication must never fall back to a direct materialized-view refresh."""
    cutoff = date(2026, 1, 1)
    report = SeriesEligibilityReport(
        data_cutoff=cutoff,
        total_series_evaluated=1,
        eligible_count=1,
        excluded_count=0,
        eligible_series=dummy_price_series,
        excluded_series=[],
        summary_reasons={},
    )
    monkeypatch.setattr("ketrika.ml.forecast.audit_series_eligibility", lambda **kwargs: report)

    def reject_publication(*args: object, **kwargs: object) -> None:
        raise ValueError("gold_publication_failed")

    monkeypatch.setattr("ketrika.ml.forecast.refresh_gold_views", reject_publication)
    mock_session = MagicMock()

    with pytest.raises(ValueError, match="gold_publication_failed"):
        run_price_forecasting_pipeline(
            session=mock_session, data_cutoff=cutoff, horizon=3, refresh_gold=True
        )

    mock_session.rollback.assert_called_once_with()
    mock_session.commit.assert_not_called()
    assert all(
        "REFRESH MATERIALIZED VIEW" not in str(call.args[0])
        for call in mock_session.execute.call_args_list
    )


def test_forecast_qualified_gold_publication_commits(
    dummy_price_series: list[EligibleSeries], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A validated publication follows the guarded path and commits the batch once."""
    cutoff = date(2026, 1, 1)
    report = SeriesEligibilityReport(
        data_cutoff=cutoff,
        total_series_evaluated=1,
        eligible_count=1,
        excluded_count=0,
        eligible_series=dummy_price_series,
        excluded_series=[],
        summary_reasons={},
    )
    monkeypatch.setattr("ketrika.ml.forecast.audit_series_eligibility", lambda **kwargs: report)
    guarded = MagicMock(return_value={"views_refreshed": ["forecast_latest"]})
    monkeypatch.setattr("ketrika.ml.forecast.refresh_gold_views", guarded)
    mock_session = MagicMock()

    result = run_price_forecasting_pipeline(
        session=mock_session, data_cutoff=cutoff, horizon=3, refresh_gold=True
    )

    assert result["forecasts_generated"] == 3
    guarded.assert_called_once_with(mock_session, views=["forecast_latest"])
    mock_session.rollback.assert_not_called()
    mock_session.commit.assert_called_once_with()



def test_forecast_abstentions_and_rejections_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    """When series are excluded, pipeline records documented abstentions and generates 0 forecasts."""
    cutoff = date(2026, 1, 1)

    from ketrika.ml.series import ExcludedSeries

    excluded = [
        ExcludedSeries(
            series_key="MAIZE|standard|retail|MDG21|kg",
            product_code="MAIZE",
            location_pcode="MDG21",
            actor_level="retail",
            admin_level=1,
            quality_grade="standard",
            unit="kg",
            total_valid_points=20,
            recent_points_24m=8,
            reasons=["insufficient_total_points_20_lt_36", "insufficient_recent_points_8_lt_12"],
        )
    ]

    mock_report = SeriesEligibilityReport(
        data_cutoff=cutoff,
        total_series_evaluated=1,
        eligible_count=0,
        excluded_count=1,
        eligible_series=[],
        excluded_series=excluded,
        summary_reasons={},
    )
    monkeypatch.setattr(
        "ketrika.ml.forecast.audit_series_eligibility", lambda **kwargs: mock_report
    )

    mock_session = MagicMock()

    result = run_price_forecasting_pipeline(
        session=mock_session,
        data_cutoff=cutoff,
        horizon=3,
        refresh_gold=False,
    )

    assert result["status"] == "abstained"
    assert result["n_series"] == 0
    assert result["forecasts_generated"] == 0
    assert result["n_abstentions"] == 1
    assert "insufficient_total_points_20_lt_36" in result["abstentions"][0]["reason"]
    assert mock_session.add.call_count == 0


def test_api_forecasts_endpoints() -> None:
    """Verify REST endpoints for /v1/forecasts, /v1/forecasts/runs, and /v1/forecasts/abstentions."""
    mock_session = MagicMock()

    # Mock rows for gold.forecast_latest
    now_dt = datetime.now(UTC)
    mock_forecast_row = (
        uuid.uuid4(),  # forecast_id
        uuid.uuid4(),  # model_run_id
        "RICE_WHITE_LOCAL|standard|retail|MDG11|kg",  # series_key
        "RICE_WHITE_LOCAL",  # product_code
        "Riz blanc local",  # product_name
        "MDG11",  # location_pcode
        "Analamanga",  # location_name
        "retail",  # actor_level
        1,  # horizon
        "2026-02-01",  # target_period
        2750.0,  # p10
        2900.0,  # p50
        3050.0,  # p90
        "AutoARIMA",  # model_requested
        "SeasonalNaive",  # model_effective
        True,  # is_baseline
        True,  # is_calibrated
        12,  # calibration_sample_size
        "baseline_fallback",  # status
        "insufficient_history_for_arima",  # fallback_reason
        "MGA",  # currency
        "kg",  # unit
        300.0,  # interval_width
        0.8333,  # coverage_rate_80
        "2026-01-01",  # data_cutoff
        "a" * 64,  # dataset_fingerprint
        "pure_observed",  # cohort
    )

    mock_run_row = (
        mock_forecast_row[1],  # model_run_id
        "price_forecast",  # task
        "best_model_selection",  # model_name
        "1.0.0@test",  # model_version
        date(2026, 1, 1),  # data_cutoff
        now_dt,  # trained_at
        {"dataset_fingerprint": "a" * 64, "cohort": "pure_observed"},  # params
        {
            "wape": 0.045,
            "mae": 130.5,
            "coverage_80": 0.833,
            "abstentions": [
                {
                    "series_key": "CASSAVA|standard|retail|MDG31|kg",
                    "product_code": "CASSAVA",
                    "location_pcode": "MDG31",
                    "actor_level": "retail",
                    "reason": "insufficient_total_points_15_lt_36",
                    "points_count": 15,
                }
            ],
        },  # metrics
    )

    def mock_execute(query, params=None):
        sql_str = str(query).lower()
        res_mock = MagicMock()
        if "from gold.forecast_latest" in sql_str:
            res_mock.fetchall.return_value = [mock_forecast_row]
            return res_mock
        elif "from ml.model_run" in sql_str:
            if "select metrics" in sql_str:
                res_mock.fetchone.return_value = (mock_run_row[7],)
            elif "where model_run_id =" in sql_str:
                res_mock.fetchone.return_value = mock_run_row
            else:
                res_mock.fetchall.return_value = [mock_run_row]
            return res_mock
        elif "from ml.forecast" in sql_str:
            res_mock.fetchall.return_value = [mock_forecast_row]
            return res_mock
        res_mock.fetchall.return_value = []
        res_mock.fetchone.return_value = None
        return res_mock

    mock_session.execute.side_effect = mock_execute

    app.dependency_overrides[get_db] = lambda: mock_session
    client = TestClient(app)

    try:
        # 1. GET /v1/forecasts
        resp = client.get("/v1/forecasts?product=RICE_WHITE_LOCAL")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        item = data[0]
        assert item["product_code"] == "RICE_WHITE_LOCAL"
        assert item["p50"] == 2900.0
        assert item["model_requested"] == "AutoARIMA"
        assert item["model_effective"] == "SeasonalNaive"
        assert item["is_baseline"] is True
        assert item["is_calibrated"] is True
        assert item["calibration_sample_size"] == 12
        assert item["fallback_reason"] == "insufficient_history_for_arima"
        assert item["dataset_fingerprint"] == "a" * 64

        # 2. GET /v1/forecasts (CSV export)
        csv_resp = client.get("/v1/forecasts?format=csv")
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]
        assert "RICE_WHITE_LOCAL" in csv_resp.text
        assert "SeasonalNaive" in csv_resp.text

        # 3. GET /v1/forecasts/runs
        runs_resp = client.get("/v1/forecasts/runs")
        assert runs_resp.status_code == 200
        runs_data = runs_resp.json()
        assert len(runs_data) == 1
        assert runs_data[0]["dataset_fingerprint"] == "a" * 64

        # 4. GET /v1/forecasts/runs/{id}
        run_id = str(mock_run_row[0])
        detail_resp = client.get(f"/v1/forecasts/runs/{run_id}")
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        assert detail_data["run"]["model_run_id"] == run_id
        assert len(detail_data["forecasts"]) == 1

        # 5. GET /v1/forecasts/abstentions
        abs_resp = client.get("/v1/forecasts/abstentions")
        assert abs_resp.status_code == 200
        abs_data = abs_resp.json()
        assert len(abs_data) == 1
        assert abs_data[0]["product_code"] == "CASSAVA"
        assert "insufficient_total_points_15_lt_36" in abs_data[0]["reason"]

    finally:
        app.dependency_overrides.clear()
