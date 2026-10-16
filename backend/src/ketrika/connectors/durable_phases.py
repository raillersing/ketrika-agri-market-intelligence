"""Transactional phase owners; no historical caller commit or live qualification."""

from dataclasses import replace
from typing import Any, NoReturn
from uuid import UUID

from ketrika.connectors.base import Connector, RunContext
from ketrika.connectors.batch_ledger import batch_digest, persist_bronze_batch, read_bronze_batch
from ketrika.connectors.document_partitions import (
    read_document_partition,
    register_document_partitions,
)
from ketrika.connectors.durable_runs import (
    DurableRunReference,
    bind_running_run,
    create_durable_ingestion_run,
    persist_durable_run_failure,
    read_running_run_reference,
)
from ketrika.connectors.silver_attempts import (
    begin_attempt,
    exclusive_silver_run,
    finish_failure,
    finish_success,
    read_success,
)
from ketrika.connectors.stages import (
    BronzeBatch,
    authorize_collection,
    collect_connector_bronze,
    consume_connector_silver,
)
from ketrika.core.artifact_identity import ArtifactProcessingIdentity
from ketrika.core.db import get_session
from ketrika.core.models.db import IngestionRun


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
            register_document_partitions(session, batch)
            return batch
    except Exception as error:
        cause = type(error)
    _raise_failure(reference, "bronze", cause)


def execute_durable_silver(
    connector: Connector,
    ctx: RunContext,
    batch: BronzeBatch,
    *,
    resumed_from: UUID | None = None,
    document_key: str | None = None,
) -> dict[str, Any]:
    if (
        not isinstance(batch, BronzeBatch)
        or batch.source_id != connector.source_id
        or ctx.source_id != batch.source_id
    ):
        raise ValueError("silver_batch_source_mismatch")
    native_rtfp = batch.source_id == "wb_rtfp_mdg" and batch.parser_version == "2.0.0"
    if batch.parser_version != connector.parser_version and not native_rtfp:
        raise ValueError("silver_batch_parser_mismatch")
    with exclusive_silver_run(batch.ingestion_run_id, batch.source_id):
        previous = read_success(batch)
        if previous is not None:
            return previous
        reference = read_running_run_reference(batch.ingestion_run_id, batch.source_id)
        attempt = begin_attempt(batch, resumed_from, document_key)
        try:
            with get_session() as session:
                bind_running_run(session, reference)
                recorded = read_bronze_batch(session, batch.ingestion_run_id)
                if batch_digest(recorded) != batch_digest(batch):
                    raise ValueError("silver_recorded_batch_mismatch")
                identities: list[ArtifactProcessingIdentity] = []
                stats = consume_connector_silver(
                    connector, ctx, session, batch, processing_identities=identities
                )
                finish_success(session, attempt, stats, batch=batch, identities=identities)
                return stats
        except Exception as error:
            cause = type(error)
        receipt_failed = False
        try:
            finish_failure(attempt, cause)
        except Exception:
            receipt_failed = True
        if receipt_failed:
            raise DurablePhaseFailure("silver:attempt_receipt_unavailable") from None
        _raise_failure(reference, "silver", cause)


def resume_durable_silver(
    connector: Connector, ctx: RunContext, previous_run_id: UUID
) -> dict[str, Any]:
    """Explicit new owner, exact archived members; never discover or fetch."""
    if ctx.source_id != connector.source_id:
        raise ValueError("silver_batch_source_mismatch")
    with exclusive_silver_run(previous_run_id):
        with get_session() as session:
            previous = read_bronze_batch(session, previous_run_id)
            old_run = session.get(IngestionRun, previous_run_id)
            if (
                old_run is None
                or previous.source_id != connector.source_id
                or previous.parser_version != connector.parser_version
            ):
                raise ValueError("silver_resume_reference_mismatch")
            if old_run.status not in ("running", "failed"):
                raise ValueError("silver_resume_terminal_success")
        reference = create_durable_ingestion_run(
            connector.source_id, ctx.metadata.get("dagster_run_id")
        )
        batch = replace(previous, ingestion_run_id=reference.run_id)
        ctx.run_id = reference.run_id
        try:
            with get_session() as session:
                persist_bronze_batch(session, batch)
        except Exception as error:
            cause = type(error)
        else:
            return execute_durable_silver(connector, ctx, batch, resumed_from=previous_run_id)
        _raise_failure(reference, "silver_resume", cause)


def replay_document_silver(
    connector: Connector, ctx: RunContext, partition_key: str
) -> dict[str, Any]:
    """One explicit recorded document, including successful origins; no acquisition."""
    if ctx.source_id != connector.source_id:
        raise ValueError("silver_batch_source_mismatch")
    with get_session() as session:
        origin, member = read_document_partition(session, partition_key, connector.source_id)
    with exclusive_silver_run(origin.ingestion_run_id):
        with get_session() as session:
            origin, member = read_document_partition(session, partition_key, connector.source_id)
            if origin.parser_version != connector.parser_version:
                raise ValueError("silver_resume_reference_mismatch")
        reference = create_durable_ingestion_run(
            connector.source_id, ctx.metadata.get("dagster_run_id")
        )
        batch = replace(origin, ingestion_run_id=reference.run_id, artifacts=(member,))
        ctx.run_id = reference.run_id
        try:
            with get_session() as session:
                persist_bronze_batch(session, batch)
                run = session.get(IngestionRun, reference.run_id)
                if run is None:
                    raise ValueError("silver_resume_reference_mismatch")
                run.partition_key = partition_key
                session.flush()
        except Exception as error:
            cause = type(error)
        else:
            return execute_durable_silver(
                connector,
                ctx,
                batch,
                resumed_from=origin.ingestion_run_id,
                document_key=partition_key,
            )
        _raise_failure(reference, "silver_document_replay", cause)
