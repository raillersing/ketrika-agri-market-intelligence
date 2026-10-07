"""Dagster pipeline definitions for Ketrika Agri Market Intelligence."""

from dagster import Definitions

from ketrika.connectors.registry import list_registered_connectors
from ketrika.pipelines.factory import build_source_assets, gold_refresh_asset

all_assets = [gold_refresh_asset]
all_checks = []
all_schedules = []

for s_id, conn_cls in list_registered_connectors().items():
    if s_id.startswith("dummy_"):
        continue
    try:
        src_assets = build_source_assets(conn_cls)
        all_assets.extend([src_assets.bronze_asset, src_assets.silver_asset])
        all_checks.extend(src_assets.checks)
        if src_assets.schedule:
            all_schedules.append(src_assets.schedule)
    except Exception:
        continue

defs = Definitions(
    assets=all_assets,
    asset_checks=all_checks,
    schedules=all_schedules,
)
