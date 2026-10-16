"""Rolling-origin backtest and model selection engine (SPECS §17).

Executes rolling-origin evaluation over up to 6 windows with horizon h=3,
calculates WAPE, MAE, sMAPE, and coverage_80, and selects the optimal model per series.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ketrika.ml.models import (
    ForecastModel,
    get_default_candidate_models,
)

MODEL_SIMPLICITY: dict[str, int] = {
    "NaiveLast": 0,
    "SeasonalNaive": 1,
    "AutoETS": 2,
    "AutoARIMA": 3,
    "DeterministicBaseline": -1,
}


@dataclass(frozen=True)
class SeriesMetrics:
    """Statistical evaluation metrics for a forecasted series."""

    wape: float  # Weighted Absolute Percentage Error (primary selection metric)
    mae: float  # Mean Absolute Error
    smape: float  # Symmetric Mean Absolute Percentage Error (0..1)
    coverage_80: float  # Empirical 80% interval coverage
    n_windows: int  # Number of evaluation windows

    def to_dict(self) -> dict[str, Any]:
        return {
            "wape": round(self.wape, 4),
            "mae": round(self.mae, 2),
            "smape": round(self.smape, 4),
            "coverage_80": round(self.coverage_80, 4),
            "n_windows": self.n_windows,
        }


@dataclass(frozen=True)
class BacktestResult:
    """Outcome of backtesting multiple candidate models on a single series."""

    series_key: str
    best_model_name: str
    best_metrics: SeriesMetrics
    evaluations: dict[str, SeriesMetrics]


def compute_metrics(
    actuals: list[float],
    predictions: list[float],
    p10_bounds: list[float],
    p90_bounds: list[float],
    n_windows: int,
) -> SeriesMetrics:
    """Compute WAPE, MAE, sMAPE and coverage_80 from paired evaluation vectors."""
    y_true = np.array(actuals, dtype=float)
    y_pred = np.array(predictions, dtype=float)
    lo = np.array(p10_bounds, dtype=float)
    hi = np.array(p90_bounds, dtype=float)

    valid_mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    y_true = y_true[valid_mask]
    y_pred = y_pred[valid_mask]
    lo = lo[valid_mask]
    hi = hi[valid_mask]

    if len(y_true) == 0:
        return SeriesMetrics(wape=0.0, mae=0.0, smape=0.0, coverage_80=1.0, n_windows=0)

    abs_err = np.abs(y_true - y_pred)
    sum_actuals = float(np.sum(np.abs(y_true)))
    wape = float(np.sum(abs_err) / (sum_actuals + 1e-6))
    mae = float(np.mean(abs_err))

    denom = np.abs(y_true) + np.abs(y_pred) + 1e-6
    smape = float(np.mean(2.0 * abs_err / denom))

    covered = (y_true >= lo - 1e-4) & (y_true <= hi + 1e-4)
    coverage = float(np.mean(covered))

    return SeriesMetrics(
        wape=wape,
        mae=mae,
        smape=smape,
        coverage_80=coverage,
        n_windows=n_windows,
    )


def evaluate_model_rolling(
    model: ForecastModel,
    y: np.ndarray,
    h: int = 3,
    max_windows: int = 6,
    min_train_len: int = 4,
) -> SeriesMetrics:
    """Execute rolling-origin backtest for a single model."""
    n = len(y)
    if n <= h:
        # Fallback for short series: in-sample fit
        pred = model.fit_predict(y, h)
        return compute_metrics(
            actuals=y.tolist(),
            predictions=pred.mean[:n].tolist(),
            p10_bounds=pred.p10[:n].tolist(),
            p90_bounds=pred.p90[:n].tolist(),
            n_windows=1,
        )

    # Determine eligible rolling origins
    # origin is index where training set ends and test set begins
    # test slice is y[origin : origin + h]
    # training history is y[:origin]
    max_possible_windows = n - h - min_train_len + 1
    if max_possible_windows < 1:
        # At least one window with whatever history is available
        origins = [n - h]
    else:
        n_windows = min(max_windows, max_possible_windows)
        # Windows step backward 1 month from most recent
        origins = [n - h - i for i in range(n_windows)]

    all_actuals: list[float] = []
    all_preds: list[float] = []
    all_lo: list[float] = []
    all_hi: list[float] = []

    for orig in origins:
        train_y = y[:orig]
        test_y = y[orig : orig + h]
        try:
            pred = model.fit_predict(train_y, h=len(test_y))
            all_actuals.extend(test_y.tolist())
            all_preds.extend(pred.mean[: len(test_y)].tolist())
            all_lo.extend(pred.p10[: len(test_y)].tolist())
            all_hi.extend(pred.p90[: len(test_y)].tolist())
        except Exception:
            # If a model fails on an origin window, penalize with naive
            last_val = float(train_y[-1]) if len(train_y) > 0 else 0.0
            all_actuals.extend(test_y.tolist())
            all_preds.extend([last_val] * len(test_y))
            all_lo.extend([last_val * 0.8] * len(test_y))
            all_hi.extend([last_val * 1.2] * len(test_y))

    return compute_metrics(
        actuals=all_actuals,
        predictions=all_preds,
        p10_bounds=all_lo,
        p90_bounds=all_hi,
        n_windows=len(origins),
    )


def select_best_model(
    series_key: str,
    y: np.ndarray,
    candidates: list[ForecastModel] | None = None,
    h: int = 3,
    max_windows: int = 6,
) -> BacktestResult:
    """Evaluate candidate models and select the winner per SPECS §17 rules."""
    models = candidates or get_default_candidate_models()
    evaluations: dict[str, SeriesMetrics] = {}

    for m in models:
        metrics = evaluate_model_rolling(m, y, h=h, max_windows=max_windows)
        evaluations[m.name] = metrics

    # SPECS §17: select lowest WAPE. If within 1 percentage point (0.01), pick simplest model.
    best_name = models[0].name
    best_metrics = evaluations[best_name]

    for name, met in evaluations.items():
        diff = met.wape - best_metrics.wape
        if diff < -0.01:
            # Strictly lower WAPE by > 1 percentage point
            best_name = name
            best_metrics = met
        elif abs(diff) <= 0.01:
            # Within 1 percentage point: compare model simplicity
            simp_current = MODEL_SIMPLICITY.get(name, 99)
            simp_best = MODEL_SIMPLICITY.get(best_name, 99)
            if simp_current < simp_best:
                best_name = name
                best_metrics = met

    return BacktestResult(
        series_key=series_key,
        best_model_name=best_name,
        best_metrics=best_metrics,
        evaluations=evaluations,
    )
