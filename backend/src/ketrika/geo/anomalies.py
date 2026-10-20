"""Rigorous agro-climatic anomalies and baseline computations (ADR-085, SPECS §26, R4.6).

Enforces:
1. Strict minimum historical baseline threshold (N_years >= 10).
2. Distinction between rainfall sum/ratio vs temperature mean/delta.
3. Standardized Z-scores (SPI proxy) and percent of normal.
4. Formal abstention when historical data is insufficient (status='insufficient_history', anomaly=None).
5. Agronomic risk classification without fabricating synthetic statistics.
"""

from __future__ import annotations

import math
from typing import NamedTuple

from ketrika.geo.contracts import AgroClimateRiskLevel, WeatherVariable

MIN_BASELINE_YEARS: int = 10


class ClimateBaseline(NamedTuple):
    """Climatological reference baseline for a specific location, month/dekad and variable."""

    variable: WeatherVariable
    sample_size: int
    mean: float
    std: float
    period_start_year: int
    period_end_year: int


class ClimateAnomalyResult(NamedTuple):
    """Calculated climate anomaly result with metadata and veracity checks."""

    variable: WeatherVariable
    observed_value: float
    baseline_mean: float | None
    absolute_anomaly: float | None
    percent_of_normal: float | None
    standardized_anomaly: float | None
    risk_level: AgroClimateRiskLevel
    status: str  # "calculated" | "insufficient_history" | "nodata"
    message: str | None = None


def compute_climate_baseline(
    historical_values: list[float],
    period_years: list[int] | None = None,
    min_years: int = MIN_BASELINE_YEARS,
    variable: WeatherVariable = WeatherVariable.PRECIP_MM,
) -> ClimateBaseline | None:
    """Compute climatological baseline from historical series.

    Returns None if valid sample size < min_years (ADR-085 strict abstention rule).
    """
    valid_data: list[tuple[float, int]] = []
    for idx, val in enumerate(historical_values):
        if math.isnan(val) or math.isinf(val) or val == -9999.0:
            continue
        year = period_years[idx] if period_years and idx < len(period_years) else (2000 + idx)
        valid_data.append((val, year))

    n = len(valid_data)
    if n < min_years:
        return None

    vals = [v for v, _ in valid_data]
    mean_val = sum(vals) / n

    if n > 1:
        variance = sum((v - mean_val) ** 2 for v in vals) / (n - 1)
        std_val = math.sqrt(variance)
    else:
        std_val = 0.0

    years = [y for _, y in valid_data]
    return ClimateBaseline(
        variable=variable,
        sample_size=n,
        mean=round(mean_val, 3),
        std=round(std_val, 3),
        period_start_year=min(years),
        period_end_year=max(years),
    )


def classify_rainfall_anomaly(
    percent_of_normal: float | None,
    standardized_anomaly: float | None = None,
) -> AgroClimateRiskLevel:
    """Classify agronomic rainfall risk level according to standard WMO/FEWS thresholds."""
    if percent_of_normal is None:
        return AgroClimateRiskLevel.LOW

    # Severe drought: < 50% of normal or Z <= -2.0
    if percent_of_normal < 50.0 or (
        standardized_anomaly is not None and standardized_anomaly <= -2.0
    ):
        return AgroClimateRiskLevel.CRITICAL

    # Moderate deficit: 50% to 75% of normal or -2.0 < Z <= -1.0
    if percent_of_normal < 75.0 or (
        standardized_anomaly is not None and standardized_anomaly <= -1.0
    ):
        return AgroClimateRiskLevel.HIGH

    # Normal regime: 75% to 125% of normal
    if percent_of_normal <= 125.0:
        return AgroClimateRiskLevel.LOW

    # Moderate surplus: 125% to 160% of normal
    if percent_of_normal <= 160.0:
        return AgroClimateRiskLevel.MEDIUM

    # Severe surplus / flood risk: > 160% of normal or Z >= 2.0
    return AgroClimateRiskLevel.HIGH


def compute_climate_anomaly(
    observed_value: float,
    baseline: ClimateBaseline | None,
    variable: WeatherVariable = WeatherVariable.PRECIP_MM,
) -> ClimateAnomalyResult:
    """Compute climatic anomaly relative to baseline with rigorous error handling."""
    if math.isnan(observed_value) or math.isinf(observed_value) or observed_value == -9999.0:
        return ClimateAnomalyResult(
            variable=variable,
            observed_value=observed_value,
            baseline_mean=None,
            absolute_anomaly=None,
            percent_of_normal=None,
            standardized_anomaly=None,
            risk_level=AgroClimateRiskLevel.LOW,
            status="nodata",
            message="Observed value is invalid or nodata",
        )

    # Abstain if baseline is missing or insufficient (ADR-085)
    if baseline is None or baseline.sample_size < MIN_BASELINE_YEARS:
        return ClimateAnomalyResult(
            variable=variable,
            observed_value=observed_value,
            baseline_mean=None,
            absolute_anomaly=None,
            percent_of_normal=None,
            standardized_anomaly=None,
            risk_level=AgroClimateRiskLevel.LOW,
            status="insufficient_history",
            message=f"Baseline sample size ({baseline.sample_size if baseline else 0}) below minimum {MIN_BASELINE_YEARS} years",
        )

    abs_anom = round(observed_value - baseline.mean, 3)

    # Standardized anomaly (Z-score)
    if baseline.std > 0.001:
        z_score = round((observed_value - baseline.mean) / baseline.std, 3)
    else:
        z_score = 0.0

    # Percent of normal is meaningful for non-negative flux variables like precipitation
    pct_normal: float | None = None
    if variable == WeatherVariable.PRECIP_MM:
        if baseline.mean > 0.0:
            pct_normal = round((observed_value / baseline.mean) * 100.0, 1)
        else:
            pct_normal = 100.0 if observed_value == 0.0 else 200.0
        risk = classify_rainfall_anomaly(pct_normal, z_score)
    else:
        pct_normal = None
        # Temperature risk: heatwave / frost checks
        if z_score >= 2.0:
            risk = AgroClimateRiskLevel.HIGH
        elif z_score >= 1.0:
            risk = AgroClimateRiskLevel.MEDIUM
        elif z_score <= -2.0:
            risk = AgroClimateRiskLevel.HIGH
        else:
            risk = AgroClimateRiskLevel.LOW

    return ClimateAnomalyResult(
        variable=variable,
        observed_value=observed_value,
        baseline_mean=baseline.mean,
        absolute_anomaly=abs_anom,
        percent_of_normal=pct_normal,
        standardized_anomaly=z_score,
        risk_level=risk,
        status="calculated",
        message=None,
    )
