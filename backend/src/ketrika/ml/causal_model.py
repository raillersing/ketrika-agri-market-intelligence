"""Causal Multivariate Agricultural Forecasting Model for Madagascar Food Security (SPECS §17, R3.6).

Integrates:
1. Phenological crop seasonality: empirical calendar transitions capturing the Madagascar
   lean season (soudure Nov-March peak) and Asara harvest (April-June trough).
2. Macroeconomic pass-through: BCM exchange rate (MGA/USD) depreciation, OMH diesel fuel
   transport friction, and World Bank Pink Sheet FOB benchmarks.
3. Agroclimatic water stress: NASA POWER precipitation anomalies during critical phenological phases.
4. Geopolitical & climate event shocks: export bans, maritime freight surges, and cyclonic destruction.
5. Non-parametric conformal calibration: 80% empirical prediction intervals with horizon diffusion.
6. Strict anti-leakage: all exogenous regressors lagged by at least 1 month (C022).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from ketrika.ml.models import (
    ForecastPrediction,
    ModelForecastResult,
    _clean_quantiles,
    impute_training_gaps,
)


@dataclass(frozen=True)
class CausalDecomposition:
    """Explainable decomposition of forecast components for analyst transparency."""

    base_price: float
    seasonal_effects: list[float]
    macro_effects: list[float]
    climate_effects: list[float]
    shock_effects: list[float]


class CausalAgriculturalModel:
    """Causal multivariate forecasting model for staple agricultural commodities in Madagascar.

    Replaces flat naive martingales with economically grounded, seasonally dynamic
    trajectories that respond to macroeconomic cost push, climate shocks, and the
    annual Malagasy crop cycle.
    """

    def __init__(
        self,
        season_length: int = 12,
        shock_half_life_months: float = 3.0,
        name: str = "CausalAgriculturalModel",
    ) -> None:
        self.season_length = season_length
        self.shock_half_life_months = shock_half_life_months
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
        dates: list[date] | None = None,
        series_key: str | None = None,
        macro_series: dict[str, np.ndarray] | None = None,
        climate_series: dict[str, np.ndarray] | None = None,
        events: list[dict[str, Any]] | None = None,
    ) -> ModelForecastResult:
        """Fit causal model and predict h steps ahead with conformal calibration."""
        y_clean, reason = impute_training_gaps(y)
        if y_clean is None:
            valid = y[~np.isnan(y)]
            if len(valid) < 6:
                zeros = np.zeros(h, dtype=float)
                return ModelForecastResult(
                    model_requested=self.name,
                    model_effective="DeterministicBaseline",
                    status="abstained",
                    fallback_reason=reason or "insufficient_valid_points",
                    prediction=ForecastPrediction(mean=zeros, p10=zeros, p90=zeros),
                    unit=unit,
                    currency=currency,
                )
            y_clean = valid

        n = len(y_clean)
        if n < 12:
            last_val = float(y_clean[-1])
            mean_arr = np.full(h, last_val, dtype=float)
            std = float(np.std(y_clean)) if len(y_clean) > 1 else last_val * 0.08
            pred = _clean_quantiles(
                mean=mean_arr,
                lo_80=mean_arr - 1.28 * std,
                hi_80=mean_arr + 1.28 * std,
            )
            return ModelForecastResult(
                model_requested=self.name,
                model_effective="DeterministicBaseline",
                status="fallback",
                fallback_reason=f"short_history_{n}_points",
                prediction=pred,
                unit=unit,
                currency=currency,
            )

        # 1. Align monthly calendar sequence
        if dates is None or len(dates) != n:
            # Default to calendar ending in October (beginning of Malagasy lean season)
            dates = []
            for i in range(n):
                m = (10 - (n - 1 - i) - 1) % 12 + 1
                dates.append(date(2026, m, 1))

        # 2. Estimate empirical month-to-month seasonal transitions
        # Collect percentage price change between month m-1 and month m
        month_transitions: dict[int, list[float]] = {m: [] for m in range(1, 13)}
        for t in range(1, n):
            m = dates[t].month
            prev_p = float(y_clean[t - 1])
            cur_p = float(y_clean[t])
            if prev_p > 0:
                ret = (cur_p - prev_p) / prev_p
                # Filter out extreme outliers (>50% jump in a single month)
                if abs(ret) < 0.50:
                    month_transitions[m].append(ret)

        # Robust median transition per calendar month
        seasonal_lifts: dict[int, float] = {}
        for m in range(1, 13):
            rets = month_transitions[m]
            if rets:
                seasonal_lifts[m] = float(np.median(rets))
            else:
                # Biological default for Madagascar rice cycle:
                # Soudure (Nov-Feb): prices rise ~2-4% per month
                # Harvest (Apr-Jun): prices drop ~3-5% per month
                defaults = {
                    1: 0.035,  # Jan: peak lean season rise
                    2: 0.025,  # Feb: plateauing lean season
                    3: -0.010,  # Mar: early harvests approach
                    4: -0.035,  # Apr: Asara harvest begins
                    5: -0.045,  # May: peak harvest arrivals
                    6: -0.020,  # Jun: harvest concludes
                    7: 0.005,  # Jul: stable post-harvest
                    8: 0.010,  # Aug: steady trading
                    9: 0.015,  # Sep: stocks begin to decline
                    10: 0.020,  # Oct: early lean season onset
                    11: 0.030,  # Nov: soudure accelerates
                    12: 0.040,  # Dec: holidays and granary exhaustion
                }
                seasonal_lifts[m] = defaults.get(m, 0.0)

        # 3. Macroeconomic pass-through adjustments (lag >= 1)
        # Elasticities calibrated from Madagascar economic literature:
        # FX pass-through: ~0.35 on imported goods, ~0.15 on domestic staples
        # Fuel diesel pass-through: ~0.10 to transport friction
        is_imported = (
            "IMPORTED" in (series_key or "").upper() or "OIL" in (series_key or "").upper()
        )
        fx_elasticity = 0.35 if is_imported else 0.15
        fuel_elasticity = 0.12 if is_imported else 0.08
        fob_elasticity = 0.25 if is_imported else 0.10

        macro_lift_pct = 0.0
        if macro_series:
            # Check FX trend over recent 3 months
            if "FX_USD_MGA" in macro_series:
                fx_arr = macro_series["FX_USD_MGA"]
                if len(fx_arr) >= 3 and fx_arr[-3] > 0:
                    fx_pct = (fx_arr[-1] - fx_arr[-3]) / fx_arr[-3]
                    macro_lift_pct += fx_elasticity * max(-0.05, min(0.10, float(fx_pct))) / 3.0

            # Check fuel price trend
            if "FUEL_DIESEL" in macro_series:
                fuel_arr = macro_series["FUEL_DIESEL"]
                if len(fuel_arr) >= 3 and fuel_arr[-3] > 0:
                    fuel_pct = (fuel_arr[-1] - fuel_arr[-3]) / fuel_arr[-3]
                    macro_lift_pct += fuel_elasticity * max(-0.05, min(0.10, float(fuel_pct))) / 3.0

            # Check world FOB benchmark
            if (
                "WORLD_FOB_RICE_WHITE_25_USD_MT" in macro_series
                and "RICE" in (series_key or "").upper()
            ):
                fob_arr = macro_series["WORLD_FOB_RICE_WHITE_25_USD_MT"]
                if len(fob_arr) >= 3 and fob_arr[-3] > 0:
                    fob_pct = (fob_arr[-1] - fob_arr[-3]) / fob_arr[-3]
                    macro_lift_pct += fob_elasticity * max(-0.05, min(0.10, float(fob_pct))) / 3.0

        # 4. Agroclimatic water stress adjustments (lag >= 1)
        climate_lift_pct = 0.0
        if climate_series and "precip_mm" in climate_series:
            precip_arr = climate_series["precip_mm"]
            if len(precip_arr) >= 3:
                # Rainfall deficit during vegetative months increases price pressure
                recent_rain = float(np.mean(precip_arr[-3:]))
                if recent_rain < 30.0:  # Severe drought condition (<30mm)
                    climate_lift_pct += 0.015
                elif recent_rain > 300.0:  # Excessive flood condition
                    climate_lift_pct += 0.010

        # 5. Geopolitical & Climate Shock impulses (exponential decay)
        lambda_decay = math.log(2.0) / max(self.shock_half_life_months, 1.0)
        last_dt = dates[-1]
        active_shock_pct = 0.0
        if events:
            for ev in events:
                ev_dt = ev.get("event_date")
                if isinstance(ev_dt, str):
                    try:
                        ev_dt = date.fromisoformat(ev_dt)
                    except Exception:
                        ev_dt = None
                if ev_dt and ev_dt <= last_dt:
                    months_ago = (last_dt.year - ev_dt.year) * 12 + (last_dt.month - ev_dt.month)
                    if 0 <= months_ago <= 12:
                        sev = float(ev.get("severity", 3))
                        decay = math.exp(-lambda_decay * months_ago)
                        impact = (sev / 5.0) * 0.04 * decay
                        active_shock_pct += impact

        # 6. Multi-step recursive forecasting for horizons 1..h
        mean_forecasts: list[float] = []
        seasonal_decomp: list[float] = []
        macro_decomp: list[float] = []
        climate_decomp: list[float] = []
        shock_decomp: list[float] = []

        # Start from recent smoothed price (weighted 80% last value + 20% 3-month trailing mean)
        last_p = float(y_clean[-1])
        k = min(3, len(y_clean))
        trailing_mean = float(np.mean(y_clean[-k:]))
        cur_p = 0.85 * last_p + 0.15 * trailing_mean

        for step in range(1, h + 1):
            total_m = last_dt.month + step
            target_month = (total_m - 1) % 12 + 1

            # Monthly seasonal transition
            s_lift = seasonal_lifts.get(target_month, 0.0)

            # Dampen exogenous lifts across horizons (martingale reversion)
            step_decay = 0.85 ** (step - 1)
            m_lift = macro_lift_pct * step_decay
            c_lift = climate_lift_pct * step_decay
            sh_lift = active_shock_pct * (math.exp(-lambda_decay * step))

            # Total monthly multiplier
            total_lift = s_lift + m_lift + c_lift + sh_lift
            # Bound monthly change between -8% and +8%
            total_lift = max(-0.08, min(0.08, total_lift))

            cur_p = cur_p * (1.0 + total_lift)
            mean_forecasts.append(cur_p)

            seasonal_decomp.append(s_lift)
            macro_decomp.append(m_lift)
            climate_decomp.append(c_lift)
            shock_decomp.append(sh_lift)

        mean_arr = np.asarray(mean_forecasts, dtype=float)

        # 7. Non-parametric Conformal Calibration on rolling in-sample residuals
        # Compute one-step-ahead pseudo residuals over the past 24 months
        eval_window = min(24, n - 2)
        residuals: list[float] = []
        for t in range(n - eval_window, n):
            m = dates[t].month
            expected_p = float(y_clean[t - 1]) * (1.0 + seasonal_lifts.get(m, 0.0))
            residuals.append(abs(float(y_clean[t]) - expected_p))

        if len(residuals) >= 8:
            q80 = float(np.percentile(residuals, 80))
            is_calibrated = True
            calib_sample_size = len(residuals)
        else:
            q80 = float(np.std(y_clean)) * 0.80 if len(y_clean) > 1 else last_p * 0.08
            is_calibrated = False
            calib_sample_size = len(residuals)

        min_spread = max(last_p * 0.05, 20.0)
        q80 = max(q80, min_spread)

        # Horizon expansion factor: sqrt(1 + 0.12 * (step - 1))
        p10_list: list[float] = []
        p90_list: list[float] = []
        for step in range(1, h + 1):
            spread = q80 * math.sqrt(1.0 + 0.12 * (step - 1))
            val = mean_arr[step - 1]
            p10_list.append(max(val - spread, val * 0.50))
            p90_list.append(val + spread)

        p10_arr = np.asarray(p10_list, dtype=float)
        p90_arr = np.asarray(p90_list, dtype=float)
        widths = (p90_arr - p10_arr).tolist()

        prediction = ForecastPrediction(
            mean=mean_arr,
            p10=p10_arr,
            p90=p90_arr,
            is_calibrated=is_calibrated,
            calibration_sample_size=calib_sample_size,
            interval_width=widths,
        )

        return ModelForecastResult(
            model_requested=self.name,
            model_effective=self.name,
            status="fitted",
            prediction=prediction,
            parameters={
                "season_length": self.season_length,
                "base_price": round(last_p, 2),
                "q80_residual": round(q80, 2),
                "macro_lift_pct": round(macro_lift_pct * 100, 2),
                "climate_lift_pct": round(climate_lift_pct * 100, 2),
                "active_shock_pct": round(active_shock_pct * 100, 2),
                "seasonal_lifts_pct": {m: round(seasonal_lifts[m] * 100, 2) for m in range(1, 13)},
            },
            unit=unit,
            currency=currency,
        )
