"""Ketrika Gold layer: materialized analytical views, KPI metrics and refresh pipelines."""

from ketrika.gold.compatibility import (
    check_and_upgrade_historical_gold_definitions,
    is_gold_definition_outdated,
)
from ketrika.gold.dq import (
    DqCheckResult,
    GoldDqRejected,
    PublicationDenominators,
    check_blocking_dq_gate,
    check_freshness_and_manage_alerts,
    check_llm_unverified_in_gold,
    check_parse_success_rate,
    check_price_range_sanity,
    check_provenance_complete,
    get_publication_denominators,
    run_all_dq_checks,
)
from ketrika.gold.kpi import (
    MarketHealthScoreResult,
    audit_source_family_independence,
    calculate_affordability_score,
    calculate_availability_score,
    calculate_calendar_aligned_variation,
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
    "check_and_upgrade_historical_gold_definitions",
    "is_gold_definition_outdated",
    "calculate_variation",
    "calculate_calendar_aligned_variation",
    "audit_source_family_independence",
    "calculate_robust_volatility",
    "calculate_robust_z_score",
    "calculate_import_dependency_ratio",
    "calculate_price_stability_score",
    "calculate_affordability_score",
    "calculate_availability_score",
    "calculate_climate_risk_score",
    "calculate_market_health_score",
    "MarketHealthScoreResult",
    "DqCheckResult",
    "GoldDqRejected",
    "PublicationDenominators",
    "check_provenance_complete",
    "check_parse_success_rate",
    "check_price_range_sanity",
    "check_llm_unverified_in_gold",
    "check_freshness_and_manage_alerts",
    "get_publication_denominators",
    "check_blocking_dq_gate",
    "run_all_dq_checks",
]
