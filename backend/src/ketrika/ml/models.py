"""Candidate time-series forecasting models for agricultural commodity prices (SPECS §17).

Provides statistical models (AutoETS, AutoARIMA, SeasonalNaive) with conformal/prediction
intervals (level 80 -> p10, p50, p90) and deterministic fallback.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Protocol

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


class ForecastModel(Protocol):
    """Protocol for candidate forecast models."""

    @property
    def name(self) -> str: ...

    def fit_predict(self, y: np.ndarray, h: int) -> ForecastPrediction: ...


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


class DeterministicBaselineModel:
    """Deterministic fallback model: trailing average + variance interval."""

    def __init__(self, name: str = "DeterministicBaseline") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def fit_predict(self, y: np.ndarray, h: int) -> ForecastPrediction:
        if len(y) == 0:
            zeros = np.zeros(h, dtype=float)
            return ForecastPrediction(mean=zeros, p10=zeros, p90=zeros)

        # Trailing 3-month mean or last value
        k = min(3, len(y))
        base_mean = float(np.mean(y[-k:]))
        std = float(np.std(y)) if len(y) > 1 else base_mean * 0.05
        if std <= 1e-4:
            std = max(base_mean * 0.05, 10.0)

        mean_arr = np.full(h, base_mean, dtype=float)
        # 80% normal interval z ~ 1.28
        lo_arr = np.maximum(mean_arr - 1.28 * std, 0.0)
        hi_arr = mean_arr + 1.28 * std
        return _clean_quantiles(mean=mean_arr, lo_80=lo_arr, hi_80=hi_arr)


class SeasonalNaiveModel:
    """Seasonal Naive model using statsforecast with adaptive season length."""

    def __init__(self, season_length: int = 12, name: str = "SeasonalNaive") -> None:
        self.season_length = season_length
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def fit_predict(self, y: np.ndarray, h: int) -> ForecastPrediction:
        if SeasonalNaive is None or len(y) < 2:
            return DeterministicBaselineModel(name=self.name).fit_predict(y, h)

        # Adapt season length if historical points are fewer than requested season_length
        sl = self.season_length
        if len(y) < sl:
            if len(y) >= 6:
                sl = 3
            elif len(y) >= 4:
                sl = 2
            else:
                sl = 1

        try:
            m = SeasonalNaive(season_length=sl)
            m.fit(y=y.astype(float))
            pred = m.predict(h=h, level=[80])
            mean = np.asarray(pred.get("mean", np.full(h, y[-1])))
            lo_80 = np.asarray(pred.get("lo-80", mean * 0.9))
            hi_80 = np.asarray(pred.get("hi-80", mean * 1.1))
            return _clean_quantiles(mean=mean, lo_80=lo_80, hi_80=hi_80)
        except Exception:
            return DeterministicBaselineModel(name=self.name).fit_predict(y, h)


class AutoETSModel:
    """AutoETS model using statsforecast."""

    def __init__(self, season_length: int = 12, name: str = "AutoETS") -> None:
        self.season_length = season_length
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def fit_predict(self, y: np.ndarray, h: int) -> ForecastPrediction:
        if AutoETS is None or len(y) < 4:
            return DeterministicBaselineModel(name=self.name).fit_predict(y, h)

        sl = self.season_length
        # AutoETS requires at least 2 * season_length for seasonal models
        if len(y) < 2 * sl:
            if len(y) >= 8:
                sl = 4
            elif len(y) >= 4:
                sl = 2
            else:
                sl = 1

        try:
            m = AutoETS(season_length=sl)
            m.fit(y=y.astype(float))
            pred = m.predict(h=h, level=[80])
            mean = np.asarray(pred.get("mean", np.full(h, y[-1])))
            lo_80 = np.asarray(pred.get("lo-80", mean * 0.9))
            hi_80 = np.asarray(pred.get("hi-80", mean * 1.1))
            return _clean_quantiles(mean=mean, lo_80=lo_80, hi_80=hi_80)
        except Exception:
            return SeasonalNaiveModel(season_length=sl, name=self.name).fit_predict(y, h)


class AutoARIMAModel:
    """AutoARIMA model using statsforecast."""

    def __init__(self, season_length: int = 12, name: str = "AutoARIMA") -> None:
        self.season_length = season_length
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def fit_predict(self, y: np.ndarray, h: int) -> ForecastPrediction:
        if AutoARIMA is None or len(y) < 6:
            return DeterministicBaselineModel(name=self.name).fit_predict(y, h)

        sl = self.season_length
        if len(y) < 2 * sl:
            if len(y) >= 8:
                sl = 4
            else:
                sl = 1

        try:
            m = AutoARIMA(
                season_length=sl,
                stepwise=True,
                approximation=True,
                max_p=2,
                max_q=2,
                max_P=1,
                max_Q=1,
            )
            m.fit(y=y.astype(float))
            pred = m.predict(h=h, level=[80])
            mean = np.asarray(pred.get("mean", np.full(h, y[-1])))
            lo_80 = np.asarray(pred.get("lo-80", mean * 0.9))
            hi_80 = np.asarray(pred.get("hi-80", mean * 1.1))
            return _clean_quantiles(mean=mean, lo_80=lo_80, hi_80=hi_80)
        except Exception:
            return AutoETSModel(season_length=sl, name=self.name).fit_predict(y, h)


def get_default_candidate_models(season_length: int = 12) -> list[ForecastModel]:
    """Return the candidate models defined in SPECS §17."""
    return [
        SeasonalNaiveModel(season_length=season_length),
        AutoETSModel(season_length=season_length),
        AutoARIMAModel(season_length=season_length),
    ]
