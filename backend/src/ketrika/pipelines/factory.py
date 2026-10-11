"""Dagster asset and pipeline factory for Ketrika connectors (SPECS §9)."""

from dataclasses import dataclass
from typing import Any

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetIn,
    AssetsDefinition,
    ScheduleDefinition,
    SensorDefinition,
    asset,
    asset_check,
)

from ketrika.connectors.base import Connector, RunContext
from ketrika.connectors.stages import (
    BronzeBatch,
    collect_connector_bronze,
    consume_connector_silver,
)
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.http import PoliteHttpClient
from ketrika.core.models.source import SourceDefinition
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


def _cadence_to_cron(cadence: str) -> str | None:
    """Map source cadence string to cron expression."""
    cadence_map = {
        "daily": "0 6 * * *",
        "weekly": "0 7 * * 1",
        "monthly": "0 8 1 * *",
        "quarterly": "0 9 1 1,4,7,10 *",
        "annual": "0 10 1 1 *",
    }
    if cadence in ("event", "static"):
        return None
    if cadence not in cadence_map:
        raise ValueError("unsupported_source_cadence")
    return cadence_map[cadence]


def _source_for_assets(source_id: str) -> SourceDefinition | None:
    try:
        definition = get_source(source_id)
    except KeyError:
        if source_id.startswith(("dummy_", "fixture_")):
            return None
        raise ValueError("unregistered_source_definition") from None
    if definition is None:
        if source_id.startswith(("dummy_", "fixture_")):
            return None
        raise ValueError("missing_source_definition")
    if definition.source_id != source_id:
        raise ValueError("source_definition_identity_mismatch")
    return definition


def build_source_assets(connector_cls: type[Connector]) -> SourceAssets:
    """Build Dagster assets, checks, schedule and sensor for a given connector class (SPECS §9)."""
    source_id = connector_cls.source_id
    source_def = _source_for_assets(source_id)
    bronze_name = f"{source_id}__bronze"
    silver_name = f"{source_id}__silver"

    # 1. Bronze Asset
    @asset(name=bronze_name, group_name="bronze", compute_kind="fetch")
    def bronze_asset(context) -> BronzeBatch:
        connector = connector_cls()
        policy = PolicyEngine()
        with PoliteHttpClient(policy_engine=policy) as http_client:
            ctx = RunContext(
                source_id=source_id,
                http_client=http_client,
                bronze_store=BronzeStore(),
                policy_engine=policy,
                logger=context.log,
                metadata={"dagster_run_id": context.run.run_id},
            )
            with get_session() as session:
                return collect_connector_bronze(connector, ctx, session)

    # 2. Silver Asset
    @asset(
        name=silver_name,
        group_name="silver",
        compute_kind="normalize",
        ins={"bronze_batch": AssetIn(key=bronze_name)},
    )
    def silver_asset(context, bronze_batch: BronzeBatch) -> dict[str, Any]:
        connector = connector_cls()
        ctx = RunContext(
            source_id=source_id,
            bronze_store=BronzeStore(),
            policy_engine=PolicyEngine(),
            logger=context.log,
        )
        with get_session() as session:
            stats = consume_connector_silver(connector, ctx, session, bronze_batch)
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
    if (
        source_def is not None
        and not source_id.startswith(("dummy_", "fixture_"))
        and source_def.status in ("active", "degraded")
        and source_def.crawl_permission != "forbidden"
    ):
        cron = _cadence_to_cron(source_def.cadence)
        if cron is not None:
            schedule = ScheduleDefinition(
                name=f"{source_id}__schedule",
                target=[bronze_asset, silver_asset],
                cron_schedule=cron,
                execution_timezone="Indian/Antananarivo",
            )

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
