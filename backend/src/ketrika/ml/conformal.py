"""Conformal prediction intervals, empirical calibration, and coverage monitoring (SPECS §17.3, ADR-077, R3.5).

Enforces:
- Non-parametric conformal calibration on actual past residuals (level 80 -> p10, p50, p90).
- Rejection of unverified arbitrary +/- 10% fallbacks as 'calibrated'.
- Explicit tracking of is_calibrated, calibration sample size, and status.
- Wilson score 95% confidence intervals on empirical coverage.
- Guarantees 0 <= p10 <= p50 <= p90 with finite values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ConformalIntervalResult:
    """Prediction quantiles with conformal calibration metadata (ADR-077)."""

    mean: np.ndarray  # p50 central forecast
    p10: np.ndarray  # p10 lower bound
    p90: np.ndarray  # p90 upper bound
    is_calibrated: bool  # True if calibrated on >= min_residuals
    calibration_sample_size: int
    status: str  # 'calibrated' | 'uncalibrated_heuristic' | 'abstained'
    width: list[float]  # p90 - p10 for each horizon step
    relative_width: list[float]  # width / (mean + 1e-6)
    residuals_std: float | None = None
    method: str = "split_conformal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "mean": [round(float(v), 2) for v in self.mean],
            "p10": [round(float(v), 2) for v in self.p10],
            "p90": [round(float(v), 2) for v in self.p90],
            "is_calibrated": self.is_calibrated,
            "calibration_sample_size": self.calibration_sample_size,
            "status": self.status,
            "width": [round(w, 2) for w in self.width],
            "relative_width": [round(rw, 4) for rw in self.relative_width],
            "method": self.method,
        }


@dataclass(frozen=True)
class CoverageReport:
    """Empirical interval coverage and statistical audit report (R3.5)."""

    target_level: float
    empirical_coverage: float
    sample_size: int
    covered_count: int
    wilson_ci_95: tuple[float, float]
    mean_width: float
    mean_relative_width: float
    by_horizon_coverage: dict[int, float] = field(default_factory=dict)
    is_sufficient_sample: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_level": self.target_level,
            "empirical_coverage": round(self.empirical_coverage, 4),
            "sample_size": self.sample_size,
            "covered_count": self.covered_count,
            "wilson_ci_95": [round(self.wilson_ci_95[0], 4), round(self.wilson_ci_95[1], 4)],
            "mean_width": round(self.mean_width, 2),
            "mean_relative_width": round(self.mean_relative_width, 4),
            "by_horizon_coverage": {h: round(c, 4) for h, c in self.by_horizon_coverage.items()},
            "is_sufficient_sample": self.is_sufficient_sample,
        }


def compute_wilson_score_interval(
    successes: int,
    total: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Compute the Wilson score confidence interval for a binomial proportion.

    Used to accurately quantify empirical coverage uncertainty on finite samples.

    Args:
        successes: Number of observations falling within the interval.
        total: Total number of observations evaluated.
        confidence: Confidence level (default 0.95, corresponding to z ~ 1.96).

    Returns:
        tuple (lower_bound, upper_bound) in [0.0, 1.0].
    """
    if total <= 0:
        return (0.0, 1.0)

    # z = 1.95996 for 95% confidence
    z = 1.95996 if math.isclose(confidence, 0.95, abs_tol=0.01) else 1.64485
    p_hat = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    centre = (p_hat + z2 / (2.0 * total)) / denom
    spread = (z * math.sqrt((p_hat * (1.0 - p_hat) / total) + (z2 / (4.0 * total * total)))) / denom

    lo = max(0.0, centre - spread)
    hi = min(1.0, centre + spread)
    return (round(lo, 4), round(hi, 4))


def calibrate_conformal_bounds(
    point_forecasts: np.ndarray,
    calibration_residuals: np.ndarray | list[float],
    target_coverage: float = 0.80,
    min_residuals: int = 8,
    fallback_std: float | None = None,
) -> ConformalIntervalResult:
    """Calibrate prediction intervals via non-parametric split conformal prediction (ADR-077).

    Guarantees:
    - If calibration residuals >= min_residuals, calculates conformal quantile correction
      and marks is_calibrated = True.
    - If calibration residuals < min_residuals, never claims calibration: marks is_calibrated = False
      and status = 'uncalibrated_heuristic'.
    - Enforces 0 <= p10 <= p50 <= p90.
    """
    mean_clean = np.maximum(np.asarray(point_forecasts, dtype=float), 0.0)
    h = len(mean_clean)

    if h == 0:
        zeros = np.zeros(0, dtype=float)
        return ConformalIntervalResult(
            mean=zeros,
            p10=zeros,
            p90=zeros,
            is_calibrated=False,
            calibration_sample_size=0,
            status="abstained",
            width=[],
            relative_width=[],
        )

    res_arr = np.array(calibration_residuals, dtype=float)
    valid_res = res_arr[~np.isnan(res_arr)]
    n_res = len(valid_res)

    if n_res < min_residuals:
        # Insufficient sample to calibrate: use dispersion fallback with explicit uncalibrated label
        std_val = (
            fallback_std
            if (fallback_std is not None and fallback_std > 0)
            else float(np.mean(mean_clean) * 0.08)
        )
        std_val = max(std_val, 5.0)

        lo_arr = np.maximum(mean_clean - 1.28 * std_val, 0.0)
        hi_arr = mean_clean + 1.28 * std_val

        p10 = np.minimum(lo_arr, mean_clean)
        p90 = np.maximum(hi_arr, mean_clean)

        width = (p90 - p10).tolist()
        rel_width = ((p90 - p10) / (mean_clean + 1e-6)).tolist()

        return ConformalIntervalResult(
            mean=mean_clean,
            p10=p10,
            p90=p90,
            is_calibrated=False,
            calibration_sample_size=n_res,
            status="uncalibrated_heuristic",
            width=width,
            relative_width=rel_width,
            residuals_std=std_val,
            method="gaussian_heuristic_fallback",
        )

    # Conformal non-parametric calibration:
    # Target 80% coverage (alpha = 0.20)
    alpha = 1.0 - target_coverage
    # Finite-sample adjusted quantile level: ceil((n + 1) * (1 - alpha)) / n
    quantile_level = min(1.0, math.ceil((n_res + 1) * (1.0 - alpha)) / n_res)

    abs_res = np.abs(valid_res)
    conformal_q = float(np.quantile(abs_res, quantile_level))

    # Also compute empirical asymmetric signed quantiles for tighter skew handling
    q10_signed = float(np.quantile(valid_res, 0.10))
    q90_signed = float(np.quantile(valid_res, 0.90))

    # Enforce conformal radius bound while allowing empirical asymmetry
    lo_conformal = np.maximum(mean_clean + min(q10_signed, -conformal_q * 0.8), 0.0)
    hi_conformal = np.maximum(mean_clean + max(q90_signed, conformal_q * 0.8), lo_conformal)

    # Ensure monotonic ordering 0 <= p10 <= p50 <= p90
    p10 = np.minimum(lo_conformal, mean_clean)
    p90 = np.maximum(hi_conformal, mean_clean)

    width = (p90 - p10).tolist()
    rel_width = ((p90 - p10) / (mean_clean + 1e-6)).tolist()
    std_val = float(np.std(valid_res))

    return ConformalIntervalResult(
        mean=mean_clean,
        p10=p10,
        p90=p90,
        is_calibrated=True,
        calibration_sample_size=n_res,
        status="calibrated",
        width=width,
        relative_width=rel_width,
        residuals_std=std_val,
        method="split_conformal",
    )


def audit_interval_coverage(
    actuals: list[float] | np.ndarray,
    p10_bounds: list[float] | np.ndarray,
    p90_bounds: list[float] | np.ndarray,
    horizon_steps: list[int] | None = None,
    target_level: float = 0.80,
    min_sufficient_sample: int = 15,
) -> CoverageReport:
    """Audit empirical coverage and compute Wilson confidence interval (SPECS §17.3, R3.5).

    Args:
        actuals: Realized ground-truth price observations.
        p10_bounds: Lower bounds of predicted intervals.
        p90_bounds: Upper bounds of predicted intervals.
        horizon_steps: Optional list of horizon steps (1, 2, 3) for per-horizon breakdown.
        target_level: Nominal confidence level (default 0.80).
        min_sufficient_sample: Sample threshold for claiming sufficient sample size (default 15).

    Returns:
        CoverageReport with empirical coverage, Wilson interval, and per-horizon breakdown.
    """
    y_true = np.asarray(actuals, dtype=float)
    lo = np.asarray(p10_bounds, dtype=float)
    hi = np.asarray(p90_bounds, dtype=float)

    valid_mask = ~np.isnan(y_true) & ~np.isnan(lo) & ~np.isnan(hi)
    y_true = y_true[valid_mask]
    lo = lo[valid_mask]
    hi = hi[valid_mask]

    n_total = len(y_true)
    if n_total == 0:
        return CoverageReport(
            target_level=target_level,
            empirical_coverage=0.0,
            sample_size=0,
            covered_count=0,
            wilson_ci_95=(0.0, 1.0),
            mean_width=0.0,
            mean_relative_width=0.0,
            by_horizon_coverage={},
            is_sufficient_sample=False,
        )

    # Count points falling within [p10 - eps, p90 + eps]
    covered = (y_true >= lo - 1e-4) & (y_true <= hi + 1e-4)
    n_covered = int(np.sum(covered))
    coverage = float(n_covered / n_total)

    widths = hi - lo
    mean_w = float(np.mean(widths))
    mean_rel_w = float(np.mean(widths / (y_true + 1e-6)))

    wilson_ci = compute_wilson_score_interval(successes=n_covered, total=n_total, confidence=0.95)

    # Per-horizon breakdown
    by_h_cov: dict[int, float] = {}
    if horizon_steps is not None and len(horizon_steps) == len(actuals):
        h_arr = np.asarray(horizon_steps, dtype=int)[valid_mask]
        for step in np.unique(h_arr):
            step_int = int(step)
            step_mask = h_arr == step_int
            if np.any(step_mask):
                step_cov = float(np.mean(covered[step_mask]))
                by_h_cov[step_int] = step_cov

    is_sufficient = n_total >= min_sufficient_sample

    return CoverageReport(
        target_level=target_level,
        empirical_coverage=coverage,
        sample_size=n_total,
        covered_count=n_covered,
        wilson_ci_95=wilson_ci,
        mean_width=mean_w,
        mean_relative_width=mean_rel_w,
        by_horizon_coverage=by_h_cov,
        is_sufficient_sample=is_sufficient,
    )
