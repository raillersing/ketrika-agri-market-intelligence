"""Transactional phase owners; no historical caller commit or live qualification."""

from typing import Any, NoReturn

from ketrika.connectors.base import Connector, RunContext
from ketrika.connectors.batch_ledger import persist_bronze_batch
from ketrika.connectors.durable_runs import (
    DurableRunReference,
    bind_running_run,
    create_durable_ingestion_run,
    persist_durable_run_failure,
    read_running_run_reference,
)
from ketrika.connectors.stages import (
    BronzeBatch,
    authorize_collection,
    collect_connector_bronze,
    consume_connector_silver,
)
from ketrika.core.db import get_session


class DurablePhaseFailure(RuntimeError):
    """Code-owned failure without collected exception text or displayed cause."""


def _raise_failure(
    reference: DurableRunReference, stage: str, cause: type[BaseException]
) -> NoReturn:
    receipt_failed = False
    try:
        persist_durable_run_failure(reference, cause)
    except Exception:
        receipt_failed = True
    if receipt_failed:
        raise DurablePhaseFailure(f"{stage}:failure_receipt_unavailable") from None
    raise DurablePhaseFailure(f"{stage}:{cause.__name__}") from None


def execute_durable_bronze(connector: Connector, ctx: RunContext) -> BronzeBatch:
    authorize_collection(connector, ctx)
    reference = create_durable_ingestion_run(
        connector.source_id, ctx.metadata.get("dagster_run_id")
    )
    try:
        with get_session() as session:
            batch = collect_connector_bronze(connector, ctx, session, durable_run=reference)
            persist_bronze_batch(session, batch)
            return batch
    except Exception as error:
        cause = type(error)
    _raise_failure(reference, "bronze", cause)


def execute_durable_silver(
    connector: Connector, ctx: RunContext, batch: BronzeBatch
) -> dict[str, Any]:
    if (
        not isinstance(batch, BronzeBatch)
        or batch.source_id != connector.source_id
        or ctx.source_id != batch.source_id
    ):
        raise ValueError("silver_batch_source_mismatch")
    reference = read_running_run_reference(batch.ingestion_run_id, batch.source_id)
    try:
        with get_session() as session:
            bind_running_run(session, reference)
            return consume_connector_silver(connector, ctx, session, batch)
    except Exception as error:
        cause = type(error)
    _raise_failure(reference, "silver", cause)
