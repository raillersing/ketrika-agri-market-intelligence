"""Ketrika Machine Learning module: price forecasting and anomaly detection."""

from ketrika.ml.anomalies import (
    PriceAnomaly,
    detect_price_anomalies,
    record_anomaly_model_run,
)
from ketrika.ml.backtest import BacktestResult, SeriesMetrics, select_best_model
from ketrika.ml.forecast import run_price_forecasting_pipeline
from ketrika.ml.models import (
    AutoARIMAModel,
    AutoETSModel,
    DeterministicBaselineModel,
    ForecastPrediction,
    SeasonalNaiveModel,
    get_default_candidate_models,
)
from ketrika.ml.series import (
    EligibleSeries,
    ExcludedSeries,
    PricePoint,
    SeriesEligibilityReport,
    audit_series_eligibility,
    build_series_key,
    evaluate_series_eligibility_records,
    extract_eligible_series,
    parse_series_key,
)

__all__ = [
    "AutoARIMAModel",
    "AutoETSModel",
    "BacktestResult",
    "DeterministicBaselineModel",
    "EligibleSeries",
    "ExcludedSeries",
    "ForecastPrediction",
    "PriceAnomaly",
    "PricePoint",
    "SeasonalNaiveModel",
    "SeriesEligibilityReport",
    "SeriesMetrics",
    "audit_series_eligibility",
    "build_series_key",
    "detect_price_anomalies",
    "evaluate_series_eligibility_records",
    "extract_eligible_series",
    "get_default_candidate_models",
    "parse_series_key",
    "record_anomaly_model_run",
    "run_price_forecasting_pipeline",
    "select_best_model",
]
