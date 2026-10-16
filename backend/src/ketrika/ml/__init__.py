"""Ketrika Machine Learning module: price forecasting and anomaly detection."""

from ketrika.ml.anomalies import (
    PriceAnomaly,
    detect_price_anomalies,
    record_anomaly_model_run,
)
from ketrika.ml.backtest import BacktestResult, SeriesMetrics, select_best_model
from ketrika.ml.dataset import (
    AsOfDataset,
    DatasetRecord,
    DatasetSplit,
    build_as_of_dataset,
    compute_canonical_fingerprint,
    resolve_point_in_time_records,
)
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
    "AsOfDataset",
    "AutoARIMAModel",
    "AutoETSModel",
    "BacktestResult",
    "DatasetRecord",
    "DatasetSplit",
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
    "build_as_of_dataset",
    "build_series_key",
    "compute_canonical_fingerprint",
    "detect_price_anomalies",
    "evaluate_series_eligibility_records",
    "extract_eligible_series",
    "get_default_candidate_models",
    "parse_series_key",
    "record_anomaly_model_run",
    "resolve_point_in_time_records",
    "run_price_forecasting_pipeline",
    "select_best_model",
]
