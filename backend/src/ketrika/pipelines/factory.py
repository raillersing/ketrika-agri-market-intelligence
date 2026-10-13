"""Dagster asset and pipeline factory for Ketrika connectors (SPECS §9)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetIn,
    AssetsDefinition,
    DynamicPartitionsDefinition,
    JobDefinition,
    ScheduleDefinition,
    SensorDefinition,
    asset,
    asset_check,
    job,
    op,
)

from ketrika.connectors.base import Connector, RunContext
from ketrika.connectors.document_partitions import document_keys
from ketrika.connectors.durable_phases import (
    execute_durable_bronze,
    execute_durable_silver,
    replay_document_silver,
)
from ketrika.connectors.stages import (
    BronzeBatch,
)
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.http import PoliteHttpClient
from ketrika.core.models.source import SourceDefinition
from ketrika.core.policy import PolicyEngine
from ketrika.core.provenance_audit import audit_source_provenance
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.registry import get_source
from ketrika.core.schema_audit import SchemaContract
from ketrika.pipelines.schema_check import build_source_schema_check


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


def build_source_assets(
    connector_cls: type[Connector], *, schema_contract: SchemaContract | None = None
) -> SourceAssets:
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
            batch = execute_durable_bronze(connector, ctx)
            context.instance.add_dynamic_partitions(
                f"{source_id}__document_versions",
                list(document_keys(batch)),
            )
            return batch

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
        return execute_durable_silver(connector, ctx, bronze_batch)

    # 3. DQ Asset Checks (SPECS §14)
    @asset_check(asset=silver_name, name=f"{source_id}__provenance_complete", blocking=True)
    def check_provenance(context) -> AssetCheckResult:
        with get_session() as session:
            receipt = audit_source_provenance(session, BronzeProofReader(BronzeStore()), source_id)
        report = receipt.report
        return AssetCheckResult(
            passed=report.passed,
            severity=AssetCheckSeverity.ERROR,
            metadata={
                "source_id": source_id,
                "check": "provenance_complete",
                "dq_id": str(receipt.dq_id),
                "total_records": report.total,
                "valid_provenance": report.valid,
                "rate": float(report.rate) if report.rate is not None else None,
                "objects_read": report.objects_read,
                "object_read_attempts": report.object_read_attempts,
                "state": "empty" if not report.total else "verified" if report.passed else "failed",
                "scope": "source_cells_not_authenticity_conversions_or_model",
            },
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
        checks=[check_provenance, build_source_schema_check(source_id, schema_contract)],
        schedule=schedule,
        sensor=None,
    )


def build_document_replay_job(connector_cls: type[Connector]) -> JobDefinition:
    """Explicit document/version job with no dependency that triggers Bronze."""
    source_id = connector_cls.source_id
    _source_for_assets(source_id)
    partitions = DynamicPartitionsDefinition(name=f"{source_id}__document_versions")

    @op(name=f"{source_id}__replay_recorded_document")
    def replay(context) -> dict[str, Any]:
        ctx = RunContext(
            source_id=source_id,
            bronze_store=BronzeStore(),
            policy_engine=PolicyEngine(),
            logger=context.log,
            metadata={"dagster_run_id": context.run_id},
        )
        return replay_document_silver(connector_cls(), ctx, context.partition_key)

    @job(name=f"{source_id}__document_replay", partitions_def=partitions)
    def document_replay():
        replay()

    return document_replay


def _refresh_gold() -> dict[str, Any]:
    """Shared real SQL refresh; no stand-in or alternate publication path."""
    from ketrika.gold.refresh import refresh_gold_views

    with get_session() as session:
        res = refresh_gold_views(session)
        session.commit()
    return res


@asset(name="gold__refresh", group_name="gold", compute_kind="refresh")
def gold_refresh_asset(context) -> dict[str, Any]:
    """Historical direct export; repository wiring is prepared separately."""
    return _refresh_gold()


def build_gold_refresh_asset(silver_assets: Sequence[AssetsDefinition]) -> AssetsDefinition:
    """Connect exact Silver definitions; a graph is not SQL qualification."""
    keys = set()
    for definition in silver_assets:
        if not isinstance(definition, AssetsDefinition) or len(definition.keys) != 1:
            raise ValueError("gold_invalid_silver_definition")
        key = next(iter(definition.keys))
        if len(key.path) != 1 or not key.path[0].endswith("__silver"):
            raise ValueError("gold_invalid_silver_key")
        if key in keys:
            raise ValueError("gold_duplicate_silver_key")
        keys.add(key)

    @asset(
        name="gold__refresh", group_name="gold", compute_kind="refresh", deps=list(silver_assets)
    )
    def connected_gold(context) -> dict[str, Any]:
        return _refresh_gold()

    return connected_gold


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
