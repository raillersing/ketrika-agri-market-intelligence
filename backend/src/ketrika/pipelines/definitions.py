from typing import Any

from dagster import Definitions, RunFailureSensorContext, run_failure_sensor

from ketrika.alerts.notifier import send_pipeline_failure_email
from ketrika.pipelines.factory import (
    alerts_evaluate_asset,
    gold_refresh_asset,
    ml_price_forecast_asset,
)
from ketrika.pipelines.source_definitions import build_registered_source_definitions

source_definitions = build_registered_source_definitions()
source_inventory = source_definitions.inventory
all_assets = [
    gold_refresh_asset,
    alerts_evaluate_asset,
    ml_price_forecast_asset,
    *source_definitions.assets,
]
all_checks = list(source_definitions.checks)
all_schedules = list(source_definitions.schedules)


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
