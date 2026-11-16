"""Rolling-origin backtest, three-phase evaluation, and model selection engine (SPECS §17.3, ADR-076).

Enforces strict temporal separation across:
- Phase 1: Rolling-origin model selection across up to 6 validation windows.
- Phase 2: Calibration of prediction residuals prior to evaluation targets.
- Phase 3: Final holdout out-of-sample evaluation without feedback into model selection.
Calculates global and by-horizon WAPE, MAE, sMAPE, and coverage_80.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np

from ketrika.ml.models import (
    ForecastModel,
    get_default_candidate_models,
)

MODEL_SIMPLICITY: dict[str, int] = {
    "NaiveLast": 0,
    "SeasonalNaive": 1,
    "CausalAgriculturalModel": 2,
    "AutoETS": 3,
    "AutoARIMA": 4,
    "DeterministicBaseline": -1,
}


@dataclass(frozen=True)
class HorizonMetrics:
    """Metrics evaluated specifically for a single forecast step h in {1, 2, 3}."""

    horizon: int
    wape: float
    mae: float
    smape: float
    coverage_80: float
    sample_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "horizon": self.horizon,
            "wape": round(self.wape, 4),
            "mae": round(self.mae, 2),
            "smape": round(self.smape, 4),
            "coverage_80": round(self.coverage_80, 4),
            "sample_size": self.sample_size,
        }


@dataclass(frozen=True)
class SeriesMetrics:
    """Statistical evaluation metrics for a forecasted series (SPECS §17.3, ADR-076)."""

    wape: float  # Weighted Absolute Percentage Error (primary selection metric)
    mae: float  # Mean Absolute Error
    smape: float  # Symmetric Mean Absolute Percentage Error (0..1)
    coverage_80: float  # Empirical 80% interval coverage
    n_windows: int  # Number of evaluation windows
    sample_size: int = 0
    status: str = "valid"  # 'valid' | 'experimental_insufficient_windows' | 'no_data'
    by_horizon: dict[int, HorizonMetrics] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "wape": round(self.wape, 4),
            "mae": round(self.mae, 2),
            "smape": round(self.smape, 4),
            "coverage_80": round(self.coverage_80, 4),
            "n_windows": self.n_windows,
            "sample_size": self.sample_size,
            "status": self.status,
            "by_horizon": {h: m.to_dict() for h, m in self.by_horizon.items()},
        }


@dataclass(frozen=True)
class WindowEvaluation:
    """Explicit definition of a rolling origin evaluation window."""

    window_index: int
    origin_index: int
    train_slice: tuple[int, int]
    test_slice: tuple[int, int]
    train_length: int
    is_eligible: bool


@dataclass(frozen=True)
class BacktestResult:
    """Outcome of backtesting multiple candidate models on a single series."""

    series_key: str
    best_model_name: str
    best_metrics: SeriesMetrics
    evaluations: dict[str, SeriesMetrics]
    holdout_metrics: SeriesMetrics | None = None


def partition_backtest_windows(
    n_points: int,
    h: int = 3,
    max_windows: int = 6,
    min_train_len: int = 24,
    holdout_len: int = 0,
) -> tuple[list[WindowEvaluation], str]:
    """Partition series into rolling evaluation windows strictly before holdout (ADR-076).

    Args:
        n_points: Total points in historical series.
        h: Forecast horizon (default 3).
        max_windows: Target number of evaluation windows (default 6).
        min_train_len: Minimum required training points per fold (default 24).
        holdout_len: Final out-of-sample points reserved for testing (default 0).

    Returns:
        tuple (windows, status) where status is 'valid' or 'experimental_insufficient_windows'.
    """
    eval_n = n_points - holdout_len
    if eval_n <= h:
        return [], "no_data"

    max_possible_windows = eval_n - h - min_train_len + 1
    if max_possible_windows < max_windows:
        status = "experimental_insufficient_windows"
    else:
        status = "valid"

    n_windows = max(1, min(max_windows, eval_n - h))
    windows: list[WindowEvaluation] = []

    for i in range(n_windows):
        orig = eval_n - h - i
        train_len = orig
        is_eligible = train_len >= min_train_len
        windows.append(
            WindowEvaluation(
                window_index=i,
                origin_index=orig,
                train_slice=(0, orig),
                test_slice=(orig, orig + h),
                train_length=train_len,
                is_eligible=is_eligible,
            )
        )

    return windows, status


def compute_metrics(
    actuals: list[float],
    predictions: list[float],
    p10_bounds: list[float],
    p90_bounds: list[float],
    n_windows: int,
    horizon_steps: list[int] | None = None,
    status: str = "valid",
) -> SeriesMetrics:
    """Compute WAPE, MAE, sMAPE, coverage_80 and per-horizon metrics (ADR-076)."""
    y_true = np.array(actuals, dtype=float)
    y_pred = np.array(predictions, dtype=float)
    lo = np.array(p10_bounds, dtype=float)
    hi = np.array(p90_bounds, dtype=float)

    valid_mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    y_true = y_true[valid_mask]
    y_pred = y_pred[valid_mask]
    lo = lo[valid_mask]
    hi = hi[valid_mask]

    n_samples = len(y_true)
    if n_samples == 0:
        return SeriesMetrics(
            wape=0.0,
            mae=0.0,
            smape=0.0,
            coverage_80=1.0,
            n_windows=n_windows,
            sample_size=0,
            status="no_data",
        )

    abs_err = np.abs(y_true - y_pred)
    sum_actuals = float(np.sum(np.abs(y_true)))
    if sum_actuals <= 1e-9:
        wape = 0.0
    else:
        wape = float(np.sum(abs_err) / (sum_actuals + 1e-6))
    mae = float(np.mean(abs_err))

    denom = np.abs(y_true) + np.abs(y_pred) + 1e-6
    smape = float(np.mean(2.0 * abs_err / denom))

    covered = (y_true >= lo - 1e-4) & (y_true <= hi + 1e-4)
    coverage = float(np.mean(covered))

    # Calculate per-horizon breakdown if horizon steps are available
    by_horizon: dict[int, HorizonMetrics] = {}
    if horizon_steps is not None and len(horizon_steps) == len(actuals):
        h_arr = np.array(horizon_steps, dtype=int)[valid_mask]
        for step in np.unique(h_arr):
            step_int = int(step)
            step_mask = h_arr == step_int
            if np.any(step_mask):
                step_yt = y_true[step_mask]
                step_yp = y_pred[step_mask]
                step_lo = lo[step_mask]
                step_hi = hi[step_mask]
                step_err = np.abs(step_yt - step_yp)
                step_sum = float(np.sum(np.abs(step_yt)))
                step_wape = float(np.sum(step_err) / (step_sum + 1e-6)) if step_sum > 1e-9 else 0.0
                step_mae = float(np.mean(step_err))
                step_denom = np.abs(step_yt) + np.abs(step_yp) + 1e-6
                step_smape = float(np.mean(2.0 * step_err / step_denom))
                step_cov = float(np.mean((step_yt >= step_lo - 1e-4) & (step_yt <= step_hi + 1e-4)))
                by_horizon[step_int] = HorizonMetrics(
                    horizon=step_int,
                    wape=step_wape,
                    mae=step_mae,
                    smape=step_smape,
                    coverage_80=step_cov,
                    sample_size=int(np.sum(step_mask)),
                )

    return SeriesMetrics(
        wape=wape,
        mae=mae,
        smape=smape,
        coverage_80=coverage,
        n_windows=n_windows,
        sample_size=n_samples,
        status=status,
        by_horizon=by_horizon,
    )


def evaluate_model_rolling(
    model: ForecastModel,
    y: np.ndarray,
    h: int = 3,
    max_windows: int = 6,
    min_train_len: int = 24,
    holdout_len: int = 0,
    dates: list[date] | None = None,
    series_key: str | None = None,
    macro_series: dict[str, np.ndarray] | None = None,
    climate_series: dict[str, np.ndarray] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> SeriesMetrics:
    """Execute rolling-origin backtest for a single model (Phase 1 selection).

    Strict temporal anti-leakage:
    - Excludes holdout_len final points from the selection protocol.
    - Each window fits model strictly on y[:orig].
    """
    windows, status = partition_backtest_windows(
        n_points=len(y),
        h=h,
        max_windows=max_windows,
        min_train_len=min_train_len,
        holdout_len=holdout_len,
    )

    if not windows:
        return SeriesMetrics(
            wape=0.0,
            mae=0.0,
            smape=0.0,
            coverage_80=1.0,
            n_windows=0,
            status="no_data",
        )

    all_actuals: list[float] = []
    all_preds: list[float] = []
    all_lo: list[float] = []
    all_hi: list[float] = []
    all_horizons: list[int] = []

    for win in windows:
        train_y = y[win.train_slice[0] : win.train_slice[1]]
        test_y = y[win.test_slice[0] : win.test_slice[1]]
        step_count = len(test_y)
        train_dates = dates[win.train_slice[0] : win.train_slice[1]] if dates else None
        train_macro = (
            {k: v[win.train_slice[0] : win.train_slice[1]] for k, v in macro_series.items()}
            if macro_series
            else None
        )
        train_climate = (
            {k: v[win.train_slice[0] : win.train_slice[1]] for k, v in climate_series.items()}
            if climate_series
            else None
        )
        try:
            if getattr(model, "name", "") == "CausalAgriculturalModel":
                pred = model.fit_predict(  # type: ignore
                    train_y,
                    h=step_count,
                    dates=train_dates,
                    series_key=series_key,
                    macro_series=train_macro,
                    climate_series=train_climate,
                    events=events,
                )
            else:
                pred = model.fit_predict(train_y, h=step_count)
            all_actuals.extend(test_y.tolist())
            all_preds.extend(pred.mean[:step_count].tolist())
            all_lo.extend(pred.p10[:step_count].tolist())
            all_hi.extend(pred.p90[:step_count].tolist())
            all_horizons.extend(list(range(1, step_count + 1)))
        except Exception:
            # On fit error, penalize with naive projection
            valid_train = train_y[~np.isnan(train_y)]
            last_val = float(valid_train[-1]) if len(valid_train) > 0 else 0.0
            all_actuals.extend(test_y.tolist())
            all_preds.extend([last_val] * step_count)
            all_lo.extend([last_val * 0.8] * step_count)
            all_hi.extend([last_val * 1.2] * step_count)
            all_horizons.extend(list(range(1, step_count + 1)))

    return compute_metrics(
        actuals=all_actuals,
        predictions=all_preds,
        p10_bounds=all_lo,
        p90_bounds=all_hi,
        n_windows=len(windows),
        horizon_steps=all_horizons,
        status=status,
    )


def evaluate_final_holdout(
    model: ForecastModel,
    y: np.ndarray,
    holdout_len: int = 3,
) -> SeriesMetrics:
    """Evaluate winning model on untouched holdout test period (Phase 3 of ADR-076)."""
    if len(y) <= holdout_len:
        return SeriesMetrics(
            wape=0.0,
            mae=0.0,
            smape=0.0,
            coverage_80=1.0,
            n_windows=0,
            status="no_data",
        )

    train_y = y[:-holdout_len]
    test_y = y[-holdout_len:]
    step_count = len(test_y)

    pred = model.fit_predict(train_y, h=step_count)
    return compute_metrics(
        actuals=test_y.tolist(),
        predictions=pred.mean[:step_count].tolist(),
        p10_bounds=pred.p10[:step_count].tolist(),
        p90_bounds=pred.p90[:step_count].tolist(),
        n_windows=1,
        horizon_steps=list(range(1, step_count + 1)),
        status="holdout_evaluated",
    )


def select_best_model(
    series_key: str,
    y: np.ndarray,
    candidates: list[ForecastModel] | None = None,
    h: int = 3,
    max_windows: int = 6,
    min_train_len: int = 24,
    holdout_len: int = 0,
    dates: list[date] | None = None,
    macro_series: dict[str, np.ndarray] | None = None,
    climate_series: dict[str, np.ndarray] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> BacktestResult:
    """Evaluate candidate models on Phase 1 validation folds and select the winner (SPECS §17.3).

    Strict separation:
    - Never evaluates candidates on holdout_len during model selection.
    - If holdout_len > 0, evaluates winner on holdout period after selection.
    - Tie-breaking within 1 percentage point prefers simpler models.
    """
    models = candidates or get_default_candidate_models()
    evaluations: dict[str, SeriesMetrics] = {}

    for m in models:
        metrics = evaluate_model_rolling(
            m,
            y,
            h=h,
            max_windows=max_windows,
            min_train_len=min_train_len,
            holdout_len=holdout_len,
            dates=dates,
            series_key=series_key,
            macro_series=macro_series,
            climate_series=climate_series,
            events=events,
        )
        evaluations[m.name] = metrics

    # SPECS §17.3: select lowest WAPE. If within 1 percentage point (0.01), pick simplest model.
    best_name = models[0].name
    best_metrics = evaluations[best_name]

    for name, met in evaluations.items():
        diff = met.wape - best_metrics.wape
        rel_improvement = -diff / max(best_metrics.wape, 1e-4)
        if diff < -0.01 or (diff < 0 and rel_improvement >= 0.20):
            # Strictly lower WAPE by > 1 percentage point or >= 20% relative error reduction
            best_name = name
            best_metrics = met
        elif abs(diff) <= 0.01:
            # Within 1 percentage point: compare model simplicity
            simp_current = MODEL_SIMPLICITY.get(name, 99)
            simp_best = MODEL_SIMPLICITY.get(best_name, 99)
            if simp_current < simp_best:
                best_name = name
                best_metrics = met

    # Phase 3: if holdout requested, evaluate selected winner on holdout
    holdout_metrics: SeriesMetrics | None = None
    if holdout_len > 0:
        winner_model = next((m for m in models if m.name == best_name), models[0])
        holdout_metrics = evaluate_final_holdout(winner_model, y, holdout_len=holdout_len)

    return BacktestResult(
        series_key=series_key,
        best_model_name=best_name,
        best_metrics=best_metrics,
        evaluations=evaluations,
        holdout_metrics=holdout_metrics,
    )
