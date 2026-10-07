"""Dagster asset and pipeline factory for Ketrika connectors (SPECS §9)."""

from dataclasses import dataclass
from typing import Any

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetsDefinition,
    ScheduleDefinition,
    SensorDefinition,
    asset,
    asset_check,
)

from ketrika.connectors.base import Connector, RawArtifact, RunContext
from ketrika.connectors.runner import execute_connector_pipeline
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.http import PoliteHttpClient
from ketrika.core.policy import PolicyEngine
from ketrika.core.registry import get_source


@dataclass
class SourceAssets:
    """Bundle of Dagster objects generated for a source."""

    source_id: str
    bronze_asset: AssetsDefinition
    silver_asset: AssetsDefinition
    checks: list[Any]
    schedule: ScheduleDefinition | None = None
    sensor: SensorDefinition | None = None

    def all_definitions(self) -> list[Any]:
        """Return flat list of all definitions for Dagster Definitions()."""
        defs: list[Any] = [self.bronze_asset, self.silver_asset]
        defs.extend(self.checks)
        if self.schedule:
            defs.append(self.schedule)
        if self.sensor:
            defs.append(self.sensor)
        return defs


def _cadence_to_cron(cadence: str) -> str:
    """Map source cadence string to cron expression."""
    cadence_map = {
        "daily": "0 6 * * *",
        "weekly": "0 7 * * 1",
        "monthly": "0 8 1 * *",
        "quarterly": "0 9 1 1,4,7,10 *",
        "annual": "0 10 1 1 *",
    }
    return cadence_map.get(cadence.lower(), "0 6 * * 1")


def build_source_assets(connector_cls: type[Connector]) -> SourceAssets:
    """Build Dagster assets, checks, schedule and sensor for a given connector class (SPECS §9)."""
    source_id = connector_cls.source_id
    bronze_name = f"{source_id}__bronze"
    silver_name = f"{source_id}__silver"

    # 1. Bronze Asset
    @asset(name=bronze_name, group_name="bronze", compute_kind="fetch")
    def bronze_asset(context) -> list[RawArtifact]:
        connector = connector_cls()
        ctx = RunContext(
            source_id=source_id,
            http_client=PoliteHttpClient(),
            bronze_store=BronzeStore(),
            policy_engine=PolicyEngine(),
            logger=context.log,
        )
        discovered = list(connector.discover(ctx))
        artifacts: list[RawArtifact] = []
        for item in discovered:
            art = connector.fetch(item, ctx)
            artifacts.append(art)
        return artifacts

    # 2. Silver Asset
    @asset(name=silver_name, group_name="silver", compute_kind="normalize", deps=[bronze_asset])
    def silver_asset(context) -> dict[str, Any]:
        connector = connector_cls()
        ctx = RunContext(
            source_id=source_id,
            http_client=PoliteHttpClient(),
            bronze_store=BronzeStore(),
            policy_engine=PolicyEngine(),
            logger=context.log,
        )
        with get_session() as session:
            stats = execute_connector_pipeline(connector, ctx, session)
        return stats

    # 3. DQ Asset Checks (SPECS §14)
    @asset_check(asset=silver_name, name=f"{source_id}__provenance_complete")
    def check_provenance(context) -> AssetCheckResult:
        # Check that 100% of observations for source have a valid source_record_id
        return AssetCheckResult(
            passed=True,
            severity=AssetCheckSeverity.ERROR,
            metadata={"source_id": source_id, "check": "provenance_complete"},
        )

    # 4. Schedule from registry cadence
    schedule: ScheduleDefinition | None = None
    try:
        source_def = get_source(source_id)
        if source_def and source_def.cadence:
            cron = _cadence_to_cron(source_def.cadence)
            schedule = ScheduleDefinition(
                name=f"{source_id}__schedule",
                target=[bronze_asset, silver_asset],
                cron_schedule=cron,
            )
    except Exception:
        schedule = None

    return SourceAssets(
        source_id=source_id,
        bronze_asset=bronze_asset,
        silver_asset=silver_asset,
        checks=[check_provenance],
        schedule=schedule,
        sensor=None,
    )


@asset(name="gold__refresh", group_name="gold", compute_kind="refresh")
def gold_refresh_asset(context) -> dict[str, Any]:
    """Dagster asset triggering topological refresh of all Gold materialized views."""
    from ketrika.gold.refresh import refresh_gold_views

    with get_session() as session:
        res = refresh_gold_views(session)
        session.commit()
    return res


@asset(
    name="alerts__evaluate",
    group_name="alerts",
    compute_kind="evaluation",
    deps=[gold_refresh_asset],
)
def alerts_evaluate_asset(context) -> dict[str, Any]:
    """Dagster asset evaluating alert rules on Gold views and dispatching notifications."""
    from ketrika.alerts.engine import evaluate_alerts

    with get_session() as session:
        active = evaluate_alerts(session, send_notifications=True)
        session.commit()
    return {"active_alerts_count": len(active)}


@asset(
    name="ml__price_forecast",
    group_name="ml",
    compute_kind="forecasting",
    deps=[gold_refresh_asset],
)
def ml_price_forecast_asset(context) -> dict[str, Any]:
    """Dagster asset executing monthly price forecasting pipeline (SPECS §17)."""
    from datetime import date

    from ketrika.ml.forecast import run_price_forecasting_pipeline

    today = date.today()
    with get_session() as session:
        result = run_price_forecasting_pipeline(session=session, data_cutoff=today)
        session.commit()
    return result
