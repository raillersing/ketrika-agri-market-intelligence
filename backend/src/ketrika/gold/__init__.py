"""Ketrika Gold layer: materialized analytical views, KPI metrics and refresh pipelines."""

from ketrika.gold.refresh import (
    ORDERED_GOLD_VIEWS,
    init_gold_views,
    refresh_gold_views,
)

__all__ = [
    "ORDERED_GOLD_VIEWS",
    "init_gold_views",
    "refresh_gold_views",
]
