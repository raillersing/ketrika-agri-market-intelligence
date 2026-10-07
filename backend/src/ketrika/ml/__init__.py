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
from ketrika.ml.series import EligibleSeries, extract_eligible_series

__all__ = [
    "AutoARIMAModel",
    "AutoETSModel",
    "BacktestResult",
    "DeterministicBaselineModel",
    "EligibleSeries",
    "ForecastPrediction",
    "PriceAnomaly",
    "SeasonalNaiveModel",
    "SeriesMetrics",
    "detect_price_anomalies",
    "extract_eligible_series",
    "get_default_candidate_models",
    "record_anomaly_model_run",
    "run_price_forecasting_pipeline",
    "select_best_model",
]
