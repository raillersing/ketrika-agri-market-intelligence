"""Independent metadata sessions; not collection permission or crash recovery."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.core.db import get_session
from ketrika.core.models.db import IngestionRun, Source


@dataclass(frozen=True)
class DurableRunReference:
    run_id: UUID
    source_id: str
    started_at: datetime
    dagster_run_id: str | None


def _validate_source(source_id: str) -> None:
    if not isinstance(source_id, str) or re.fullmatch(r"[a-z0-9_]{1,128}", source_id) is None:
        raise ValueError("durable_run_invalid_source")


def create_durable_ingestion_run(
    source_id: str, dagster_run_id: str | None = None
) -> DurableRunReference:
    """Only metadata: caller must enforce policy before any acquisition."""
    _validate_source(source_id)
    if dagster_run_id is not None:
        try:
            identifier = UUID(dagster_run_id)
        except (ValueError, TypeError, AttributeError):
            raise ValueError("durable_run_invalid_dagster_id") from None
        if identifier.int == 0 or str(identifier) != dagster_run_id:
            raise ValueError("durable_run_invalid_dagster_id")
    reference = DurableRunReference(uuid4(), source_id, datetime.now(UTC), dagster_run_id)
    with get_session() as session:
        if session.get(Source, source_id) is None:
            raise ValueError("durable_run_source_not_persisted")
        session.add(
            IngestionRun(
                run_id=reference.run_id,
                source_id=reference.source_id,
                dagster_run_id=reference.dagster_run_id,
                started_at=reference.started_at,
                status="running",
                n_fetched=0,
                n_new_artifacts=0,
                n_records=0,
                n_rejected=0,
                n_review=0,
            )
        )
        session.flush()
    return reference


def persist_durable_run_failure(reference: DurableRunReference, cause: type[BaseException]) -> UUID:
    """Do not change a caller transaction or store exception messages."""
    if not isinstance(reference, DurableRunReference):
        raise ValueError("durable_run_invalid_reference")
    _validate_source(reference.source_id)
    if (
        not isinstance(reference.run_id, UUID)
        or reference.run_id.int == 0
        or not isinstance(reference.started_at, datetime)
        or reference.started_at.utcoffset() is None
    ):
        raise ValueError("durable_run_invalid_reference")
    if not isinstance(cause, type) or not issubclass(cause, BaseException):
        raise ValueError("durable_run_invalid_error_class")
    error_class = cause.__name__
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", error_class) is None:
        raise ValueError("durable_run_invalid_error_class")
    with get_session() as session:
        run = session.scalar(
            select(IngestionRun).where(IngestionRun.run_id == reference.run_id).with_for_update()
        )
        if run is None or (
            run.source_id,
            run.started_at,
            run.dagster_run_id,
        ) != (reference.source_id, reference.started_at, reference.dagster_run_id):
            raise ValueError("durable_run_reference_mismatch")
        if run.status == "failed" and run.error == error_class and run.finished_at is not None:
            return run.run_id
        if run.status != "running" or run.finished_at is not None:
            raise ValueError("durable_run_already_terminal")
        run.status, run.finished_at, run.error = "failed", datetime.now(UTC), error_class
        session.flush()
    return reference.run_id


def bind_running_run(session: Session, reference: DurableRunReference) -> IngestionRun:
    """Lock the explicit owner's metadata row in the data transaction."""
    if (
        not isinstance(reference, DurableRunReference)
        or not isinstance(reference.run_id, UUID)
        or reference.run_id.int == 0
        or not isinstance(reference.started_at, datetime)
        or reference.started_at.utcoffset() is None
    ):
        raise ValueError("durable_run_invalid_reference")
    _validate_source(reference.source_id)
    run = session.scalar(
        select(IngestionRun).where(IngestionRun.run_id == reference.run_id).with_for_update()
    )
    if run is None or (run.source_id, run.started_at, run.dagster_run_id) != (
        reference.source_id,
        reference.started_at,
        reference.dagster_run_id,
    ):
        raise ValueError("durable_run_reference_mismatch")
    if run.status != "running" or run.finished_at is not None:
        raise ValueError("durable_run_not_running")
    return run


def read_running_run_reference(run_id: UUID, source_id: str) -> DurableRunReference:
    """Read an existing phase owner; this does not create or reactivate a run."""
    _validate_source(source_id)
    if not isinstance(run_id, UUID) or run_id.int == 0:
        raise ValueError("durable_run_invalid_reference")
    with get_session() as session:
        run = session.get(IngestionRun, run_id)
        if run is None or run.source_id != source_id:
            raise ValueError("durable_run_reference_mismatch")
        if run.status != "running" or run.finished_at is not None:
            raise ValueError("durable_run_not_running")
        return DurableRunReference(run.run_id, run.source_id, run.started_at, run.dagster_run_id)
