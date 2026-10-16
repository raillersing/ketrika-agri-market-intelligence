"""Candidate time-series forecasting models for agricultural commodity prices (SPECS §17, ADR-075).

Provides normative benchmarks (NaiveLast, SeasonalNaive annual) and candidate statistical
models (AutoETS, AutoARIMA with season_length=12), strict model_requested vs model_effective
traceability (A09), deterministic training gap imputation, and unit/currency conservation.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

# Suppress LaTeX docstring SyntaxWarnings emitted by statsforecast in Python 3.12+
warnings.filterwarnings("ignore", category=SyntaxWarning, module="statsforecast.*")

try:
    from statsforecast.models import AutoARIMA, AutoETS, SeasonalNaive
except ImportError:
    AutoARIMA = None  # type: ignore
    AutoETS = None  # type: ignore
    SeasonalNaive = None  # type: ignore


@dataclass(frozen=True)
class ForecastPrediction:
    """Prediction quantiles for horizons 1..h."""

    mean: np.ndarray  # p50 central forecast
    p10: np.ndarray  # p10 lower bound (80% conformal interval)
    p90: np.ndarray  # p90 upper bound (80% conformal interval)


@dataclass(frozen=True)
class ModelForecastResult:
    """Detailed forecast result enforcing ADR-075 transparency and traceability.

    Attributes:
        model_requested: Name of the model requested by the caller.
        model_effective: Name of the model actually fitted and executed.
        status: Execution status ('fitted', 'fallback', 'abstained').
        prediction: Prediction quantiles object.
        fallback_reason: Explicit explanation if fallback occurred.
        parameters: Hyperparameters or fitted model details.
        unit: Physical unit (e.g. 'kg', 'litre').
        currency: Currency code (e.g. 'MGA').
    """

    model_requested: str
    model_effective: str
    status: str
    prediction: ForecastPrediction
    fallback_reason: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    unit: str = "kg"
    currency: str = "MGA"

    @property
    def mean(self) -> np.ndarray:
        return self.prediction.mean

    @property
    def p10(self) -> np.ndarray:
        return self.prediction.p10

    @property
    def p90(self) -> np.ndarray:
        return self.prediction.p90


class ForecastModel(Protocol):
    """Protocol for candidate forecast models."""

    @property
    def name(self) -> str: ...

    def fit_predict(
        self,
        y: np.ndarray,
        h: int,
        unit: str = "kg",
        currency: str = "MGA",
    ) -> ModelForecastResult: ...


def _clean_quantiles(
    mean: np.ndarray,
    lo_80: np.ndarray | None,
    hi_80: np.ndarray | None,
) -> ForecastPrediction:
    """Sanitize predictions: ensure positivity, correct bounds (p10 <= p50 <= p90)."""
    mean_clean = np.maximum(mean, 0.0)

    if lo_80 is None:
        p10 = np.maximum(mean_clean * 0.9, 0.0)
    else:
        p10 = np.maximum(lo_80, 0.0)
        p10 = np.minimum(p10, mean_clean)

    if hi_80 is None:
        p90 = np.maximum(mean_clean * 1.1, p10)
    else:
        p90 = np.maximum(hi_80, mean_clean)

    return ForecastPrediction(mean=mean_clean, p10=p10, p90=p90)


def impute_training_gaps(
    y: np.ndarray,
    max_gap: int = 4,
    max_missing_ratio: float = 0.30,
) -> tuple[np.ndarray | None, str | None]:
    """Impute missing calendar gaps in the training series using linear interpolation.

    Strict anti-leakage: operates exclusively on the training series provided, without
    any knowledge of future values or test targets.

    Args:
        y: Raw training array with potential np.nan values.
        max_gap: Maximum allowed consecutive missing months (default 4).
        max_missing_ratio: Maximum allowed ratio of missing values in training (default 0.30).

    Returns:
        tuple (imputed_series, None) if clean or successfully imputed,
        or (None, abstention_reason) if missing values are excessive.
    """
    if len(y) == 0:
        return None, "empty_series"

    y_arr = np.asarray(y, dtype=float)
    is_nan = np.isnan(y_arr)

    if not np.any(is_nan):
        return y_arr, None

    nan_count = int(np.sum(is_nan))
    ratio = nan_count / len(y_arr)
    if ratio > max_missing_ratio:
        return None, f"excessive_missing_ratio: {ratio:.1%} > {max_missing_ratio:.1%}"

    # Check maximum consecutive gap length
    max_consec = 0
    cur_consec = 0
    for val in is_nan:
        if val:
            cur_consec += 1
            if cur_consec > max_consec:
                max_consec = cur_consec
        else:
            cur_consec = 0

    if max_consec > max_gap:
        return None, f"excessive_consecutive_gap: {max_consec} months > {max_gap} allowed"

    # Linear interpolation: valid points interpolate interior; boundary points use constant extension
    indices = np.arange(len(y_arr))
    valid_mask = ~is_nan
    valid_indices = indices[valid_mask]
    valid_values = y_arr[valid_mask]

    if len(valid_values) == 0:
        return None, "all_points_missing"

    imputed = y_arr.copy()
    imputed[is_nan] = np.interp(indices[is_nan], valid_indices, valid_values)
    return imputed, None


class DeterministicBaselineModel:
    """Deterministic fallback model: trailing average + variance interval."""

    def __init__(self, name: str = "DeterministicBaseline") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def fit_predict(
        self,
        y: np.ndarray,
        h: int,
        unit: str = "kg",
        currency: str = "MGA",
    ) -> ModelForecastResult:
        if len(y) == 0:
            zeros = np.zeros(h, dtype=float)
            return ModelForecastResult(
                model_requested=self.name,
                model_effective=self.name,
                status="abstained",
                fallback_reason="empty_series",
                prediction=ForecastPrediction(mean=zeros, p10=zeros, p90=zeros),
                unit=unit,
                currency=currency,
            )

        y_clean, reason = impute_training_gaps(y)
        if y_clean is None:
            # Series has excessive gaps: fallback to last available valid point
            valid = y[~np.isnan(y)]
            if len(valid) == 0:
                zeros = np.zeros(h, dtype=float)
                return ModelForecastResult(
                    model_requested=self.name,
                    model_effective=self.name,
                    status="abstained",
                    fallback_reason=reason or "excessive_missing",
                    prediction=ForecastPrediction(mean=zeros, p10=zeros, p90=zeros),
                    unit=unit,
                    currency=currency,
                )
            base_mean = float(valid[-1])
            std = base_mean * 0.10
        else:
            k = min(3, len(y_clean))
            base_mean = float(np.mean(y_clean[-k:]))
            std = float(np.std(y_clean)) if len(y_clean) > 1 else base_mean * 0.05
            if std <= 1e-4:
                std = max(base_mean * 0.05, 10.0)

        mean_arr = np.full(h, base_mean, dtype=float)
        lo_arr = np.maximum(mean_arr - 1.28 * std, 0.0)
        hi_arr = mean_arr + 1.28 * std
        pred = _clean_quantiles(mean=mean_arr, lo_80=lo_arr, hi_80=hi_arr)

        return ModelForecastResult(
            model_requested=self.name,
            model_effective=self.name,
            status="fitted",
            prediction=pred,
            parameters={"mean": base_mean, "std": std},
            unit=unit,
            currency=currency,
        )


class NaiveLastModel:
    """Normative benchmark: last observed price forward (y_{t+h} = y_t)."""

    def __init__(self, name: str = "NaiveLast") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def fit_predict(
        self,
        y: np.ndarray,
        h: int,
        unit: str = "kg",
        currency: str = "MGA",
    ) -> ModelForecastResult:
        if len(y) == 0:
            zeros = np.zeros(h, dtype=float)
            return ModelForecastResult(
                model_requested=self.name,
                model_effective=self.name,
                status="abstained",
                fallback_reason="empty_series",
                prediction=ForecastPrediction(mean=zeros, p10=zeros, p90=zeros),
                unit=unit,
                currency=currency,
            )

        y_clean, reason = impute_training_gaps(y)
        if y_clean is None:
            valid = y[~np.isnan(y)]
            if len(valid) == 0:
                zeros = np.zeros(h, dtype=float)
                return ModelForecastResult(
                    model_requested=self.name,
                    model_effective=self.name,
                    status="abstained",
                    fallback_reason=reason or "excessive_missing",
                    prediction=ForecastPrediction(mean=zeros, p10=zeros, p90=zeros),
                    unit=unit,
                    currency=currency,
                )
            last_val = float(valid[-1])
            std = last_val * 0.10
        else:
            last_val = float(y_clean[-1])
            std = float(np.std(y_clean)) if len(y_clean) > 1 else last_val * 0.05
            if std <= 1e-4:
                std = max(last_val * 0.05, 10.0)

        mean_arr = np.full(h, last_val, dtype=float)
        lo_arr = np.maximum(mean_arr - 1.28 * std, 0.0)
        hi_arr = mean_arr + 1.28 * std
        pred = _clean_quantiles(mean=mean_arr, lo_80=lo_arr, hi_80=hi_arr)

        return ModelForecastResult(
            model_requested=self.name,
            model_effective=self.name,
            status="fitted",
            prediction=pred,
            parameters={"last_value": last_val, "std": std},
            unit=unit,
            currency=currency,
        )


class SeasonalNaiveModel:
    """Seasonal Naive benchmark strictly configured with annual season_length=12 (SPECS §17).

    Artificial 2-4 month sub-seasons are strictly rejected (A09).
    If history is shorter than season_length, an explicit fallback to NaiveLast is recorded.
    """

    def __init__(self, season_length: int = 12, name: str = "SeasonalNaive") -> None:
        self.season_length = season_length
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def fit_predict(
        self,
        y: np.ndarray,
        h: int,
        unit: str = "kg",
        currency: str = "MGA",
    ) -> ModelForecastResult:
        y_clean, reason = impute_training_gaps(y)
        if y_clean is None:
            naive_fallback = NaiveLastModel().fit_predict(y, h, unit=unit, currency=currency)
            return ModelForecastResult(
                model_requested=self.name,
                model_effective="NaiveLast",
                status="fallback",
                fallback_reason=reason or "excessive_missing",
                prediction=naive_fallback.prediction,
                unit=unit,
                currency=currency,
            )

        if len(y_clean) < self.season_length:
            naive_fallback = NaiveLastModel().fit_predict(y_clean, h, unit=unit, currency=currency)
            return ModelForecastResult(
                model_requested=self.name,
                model_effective="NaiveLast",
                status="fallback",
                fallback_reason=f"insufficient_history: length {len(y_clean)} < season_length {self.season_length}",
                prediction=naive_fallback.prediction,
                unit=unit,
                currency=currency,
            )

        if SeasonalNaive is None:
            naive_fallback = NaiveLastModel().fit_predict(y_clean, h, unit=unit, currency=currency)
            return ModelForecastResult(
                model_requested=self.name,
                model_effective="NaiveLast",
                status="fallback",
                fallback_reason="statsforecast_not_installed",
                prediction=naive_fallback.prediction,
                unit=unit,
                currency=currency,
            )

        try:
            m = SeasonalNaive(season_length=self.season_length)
            m.fit(y=y_clean.astype(float))
            pred = m.predict(h=h, level=[80])
            mean = np.asarray(pred.get("mean", np.full(h, y_clean[-1])))
            lo_80 = np.asarray(pred.get("lo-80", mean * 0.9))
            hi_80 = np.asarray(pred.get("hi-80", mean * 1.1))
            cleaned = _clean_quantiles(mean=mean, lo_80=lo_80, hi_80=hi_80)
            return ModelForecastResult(
                model_requested=self.name,
                model_effective=self.name,
                status="fitted",
                prediction=cleaned,
                parameters={"season_length": self.season_length},
                unit=unit,
                currency=currency,
            )
        except Exception as exc:
            naive_fallback = NaiveLastModel().fit_predict(y_clean, h, unit=unit, currency=currency)
            return ModelForecastResult(
                model_requested=self.name,
                model_effective="NaiveLast",
                status="fallback",
                fallback_reason=f"statsforecast_fit_error: {exc}",
                prediction=naive_fallback.prediction,
                unit=unit,
                currency=currency,
            )


class AutoETSModel:
    """AutoETS model using statsforecast with annual season_length=12 (SPECS §17).

    Requires at least 2 * season_length (24 months) to estimate seasonal parameters.
    Transparently reports fallback if insufficient history or fit failure (A09).
    """

    def __init__(self, season_length: int = 12, name: str = "AutoETS") -> None:
        self.season_length = season_length
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def fit_predict(
        self,
        y: np.ndarray,
        h: int,
        unit: str = "kg",
        currency: str = "MGA",
    ) -> ModelForecastResult:
        y_clean, reason = impute_training_gaps(y)
        if y_clean is None:
            s_naive = SeasonalNaiveModel(season_length=self.season_length).fit_predict(
                y, h, unit=unit, currency=currency
            )
            return ModelForecastResult(
                model_requested=self.name,
                model_effective=s_naive.model_effective,
                status="fallback",
                fallback_reason=reason or "excessive_missing",
                prediction=s_naive.prediction,
                unit=unit,
                currency=currency,
            )

        min_required = 2 * self.season_length
        if len(y_clean) < min_required:
            s_naive = SeasonalNaiveModel(season_length=self.season_length).fit_predict(
                y_clean, h, unit=unit, currency=currency
            )
            return ModelForecastResult(
                model_requested=self.name,
                model_effective=s_naive.model_effective,
                status="fallback",
                fallback_reason=f"insufficient_history: length {len(y_clean)} < 2*season_length ({min_required})",
                prediction=s_naive.prediction,
                unit=unit,
                currency=currency,
            )

        if AutoETS is None:
            s_naive = SeasonalNaiveModel(season_length=self.season_length).fit_predict(
                y_clean, h, unit=unit, currency=currency
            )
            return ModelForecastResult(
                model_requested=self.name,
                model_effective=s_naive.model_effective,
                status="fallback",
                fallback_reason="statsforecast_not_installed",
                prediction=s_naive.prediction,
                unit=unit,
                currency=currency,
            )

        try:
            m = AutoETS(season_length=self.season_length)
            m.fit(y=y_clean.astype(float))
            pred = m.predict(h=h, level=[80])
            mean = np.asarray(pred.get("mean", np.full(h, y_clean[-1])))
            lo_80 = np.asarray(pred.get("lo-80", mean * 0.9))
            hi_80 = np.asarray(pred.get("hi-80", mean * 1.1))
            cleaned = _clean_quantiles(mean=mean, lo_80=lo_80, hi_80=hi_80)
            return ModelForecastResult(
                model_requested=self.name,
                model_effective=self.name,
                status="fitted",
                prediction=cleaned,
                parameters={"season_length": self.season_length},
                unit=unit,
                currency=currency,
            )
        except Exception as exc:
            s_naive = SeasonalNaiveModel(season_length=self.season_length).fit_predict(
                y_clean, h, unit=unit, currency=currency
            )
            return ModelForecastResult(
                model_requested=self.name,
                model_effective=s_naive.model_effective,
                status="fallback",
                fallback_reason=f"statsforecast_fit_error: {exc}",
                prediction=s_naive.prediction,
                unit=unit,
                currency=currency,
            )


class AutoARIMAModel:
    """AutoARIMA model using statsforecast with annual season_length=12 (SPECS §17).

    Requires at least 2 * season_length (24 months) for seasonal ARIMA.
    Never masks fallback behind an AutoARIMA label (A09).
    """

    def __init__(self, season_length: int = 12, name: str = "AutoARIMA") -> None:
        self.season_length = season_length
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def fit_predict(
        self,
        y: np.ndarray,
        h: int,
        unit: str = "kg",
        currency: str = "MGA",
    ) -> ModelForecastResult:
        y_clean, reason = impute_training_gaps(y)
        if y_clean is None:
            ets_fallback = AutoETSModel(season_length=self.season_length).fit_predict(
                y, h, unit=unit, currency=currency
            )
            return ModelForecastResult(
                model_requested=self.name,
                model_effective=ets_fallback.model_effective,
                status="fallback",
                fallback_reason=reason or "excessive_missing",
                prediction=ets_fallback.prediction,
                unit=unit,
                currency=currency,
            )

        min_required = 2 * self.season_length
        if len(y_clean) < min_required:
            ets_fallback = AutoETSModel(season_length=self.season_length).fit_predict(
                y_clean, h, unit=unit, currency=currency
            )
            return ModelForecastResult(
                model_requested=self.name,
                model_effective=ets_fallback.model_effective,
                status="fallback",
                fallback_reason=f"insufficient_history: length {len(y_clean)} < 2*season_length ({min_required})",
                prediction=ets_fallback.prediction,
                unit=unit,
                currency=currency,
            )

        if AutoARIMA is None:
            ets_fallback = AutoETSModel(season_length=self.season_length).fit_predict(
                y_clean, h, unit=unit, currency=currency
            )
            return ModelForecastResult(
                model_requested=self.name,
                model_effective=ets_fallback.model_effective,
                status="fallback",
                fallback_reason="statsforecast_not_installed",
                prediction=ets_fallback.prediction,
                unit=unit,
                currency=currency,
            )

        try:
            m = AutoARIMA(
                season_length=self.season_length,
                stepwise=True,
                approximation=True,
                max_p=2,
                max_q=2,
                max_P=1,
                max_Q=1,
            )
            m.fit(y=y_clean.astype(float))
            pred = m.predict(h=h, level=[80])
            mean = np.asarray(pred.get("mean", np.full(h, y_clean[-1])))
            lo_80 = np.asarray(pred.get("lo-80", mean * 0.9))
            hi_80 = np.asarray(pred.get("hi-80", mean * 1.1))
            cleaned = _clean_quantiles(mean=mean, lo_80=lo_80, hi_80=hi_80)
            return ModelForecastResult(
                model_requested=self.name,
                model_effective=self.name,
                status="fitted",
                prediction=cleaned,
                parameters={"season_length": self.season_length},
                unit=unit,
                currency=currency,
            )
        except Exception as exc:
            ets_fallback = AutoETSModel(season_length=self.season_length).fit_predict(
                y_clean, h, unit=unit, currency=currency
            )
            return ModelForecastResult(
                model_requested=self.name,
                model_effective=ets_fallback.model_effective,
                status="fallback",
                fallback_reason=f"statsforecast_fit_error: {exc}",
                prediction=ets_fallback.prediction,
                unit=unit,
                currency=currency,
            )


def get_default_candidate_models(season_length: int = 12) -> list[ForecastModel]:
    """Return the normative benchmark and candidate models defined in SPECS §17."""
    return [
        NaiveLastModel(),
        SeasonalNaiveModel(season_length=season_length),
        AutoETSModel(season_length=season_length),
        AutoARIMAModel(season_length=season_length),
    ]
