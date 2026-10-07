from typing import Any

from dagster import Definitions, RunFailureSensorContext, run_failure_sensor

from ketrika.alerts.notifier import send_pipeline_failure_email
from ketrika.connectors.registry import list_registered_connectors
from ketrika.pipelines.factory import (
    alerts_evaluate_asset,
    build_source_assets,
    gold_refresh_asset,
    ml_price_forecast_asset,
)

all_assets = [gold_refresh_asset, alerts_evaluate_asset, ml_price_forecast_asset]
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


def handle_pipeline_failure(context: Any) -> None:
    """Handle pipeline failure and dispatch alert email to Mailpit."""
    run_id = context.dagster_run.run_id
    job_name = context.dagster_run.job_name or "dagster_job"
    error_msg = (
        context.failure_event.message if context.failure_event else "Pipeline run failed in Dagster"
    )
    send_pipeline_failure_email(job_name=job_name, run_id=run_id, error_message=error_msg)


@run_failure_sensor(name="pipeline_failure_email_sensor")
def pipeline_failure_email_sensor(context: RunFailureSensorContext) -> None:
    """Dagster sensor dispatching alert email to Mailpit upon run failure (SPECS §19, T11.1)."""
    handle_pipeline_failure(context)


defs = Definitions(
    assets=all_assets,
    asset_checks=all_checks,
    schedules=all_schedules,
    sensors=[pipeline_failure_email_sensor],
)
