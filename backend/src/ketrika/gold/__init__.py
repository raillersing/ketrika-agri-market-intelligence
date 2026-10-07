"""Ketrika Gold layer: materialized analytical views, KPI metrics and refresh pipelines."""

from ketrika.gold.kpi import (
    MarketHealthScoreResult,
    calculate_affordability_score,
    calculate_availability_score,
    calculate_climate_risk_score,
    calculate_import_dependency_ratio,
    calculate_market_health_score,
    calculate_price_stability_score,
    calculate_robust_volatility,
    calculate_robust_z_score,
    calculate_variation,
)
from ketrika.gold.refresh import (
    ORDERED_GOLD_VIEWS,
    init_gold_views,
    refresh_gold_views,
)

__all__ = [
    "ORDERED_GOLD_VIEWS",
    "init_gold_views",
    "refresh_gold_views",
    "calculate_variation",
    "calculate_robust_volatility",
    "calculate_robust_z_score",
    "calculate_import_dependency_ratio",
    "calculate_price_stability_score",
    "calculate_affordability_score",
    "calculate_availability_score",
    "calculate_climate_risk_score",
    "calculate_market_health_score",
    "MarketHealthScoreResult",
]
