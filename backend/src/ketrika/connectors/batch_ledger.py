"""Exact Bronze batches in SQL; caller owns commit, Silver owns byte checks."""

import hashlib
import json
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.connectors.base import RawArtifact
from ketrika.connectors.stages import BronzeBatch
from ketrika.core.models.db import IngestionRun, SourceRecord
from ketrika.core.models.ingestion_batch import IngestionBatch, IngestionBatchMember

MAX_MEMBERS = 100_000
MAX_BYTES = 32 * 1024 * 1024


def _token(value: str, limit: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > limit
        or value != value.strip()
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise ValueError("batch_ledger_invalid_token")
    return value


def _uuid(value: str | UUID) -> UUID:
    try:
        parsed = value if isinstance(value, UUID) else UUID(value)
        if parsed.int == 0:
            raise ValueError
        return parsed
    except (ValueError, TypeError, AttributeError):
        raise ValueError("batch_ledger_invalid_uuid") from None


def _date(value: datetime | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("batch_ledger_invalid_timestamp")
    return value.astimezone(UTC).isoformat()


def batch_digest(batch: BronzeBatch) -> str:
    if (
        not isinstance(batch, BronzeBatch)
        or not isinstance(batch.ingestion_run_id, UUID)
        or not isinstance(batch.artifacts, tuple)
        or len(batch.artifacts) > MAX_MEMBERS
        or not isinstance(batch.source_id, str)
        or re.fullmatch(r"[a-z0-9_]{1,128}", batch.source_id) is None
    ):
        raise ValueError("batch_ledger_invalid_batch")
    _uuid(batch.ingestion_run_id)
    _token(batch.parser_version, 128)
    members: list[list[str | bool | None]] = []
    seen: set[UUID] = set()
    size = 0
    for artifact in batch.artifacts:
        if not isinstance(artifact, RawArtifact) or type(artifact.is_new) is not bool:
            raise ValueError("batch_ledger_invalid_artifact")
        reference_id = _uuid(artifact.source_record_id)
        if reference_id in seen:
            raise ValueError("batch_ledger_duplicate_reference")
        seen.add(reference_id)
        _token(artifact.object_key, 2048)
        _token(artifact.mime_type, 256)
        # URL is source data, not an instruction or a URL to fetch here.
        if not isinstance(artifact.url, str) or len(artifact.url) > 8192:
            raise ValueError("batch_ledger_invalid_url")
        if (
            not isinstance(artifact.content_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", artifact.content_sha256) is None
        ):
            raise ValueError("batch_ledger_invalid_sha")
        member: list[str | bool | None] = [
            str(reference_id),
            artifact.object_key,
            artifact.content_sha256,
            artifact.mime_type,
            artifact.url,
            artifact.is_new,
            _date(artifact.published_at),
        ]
        encoded = json.dumps(member, ensure_ascii=True, separators=(",", ":"))
        size += len(encoded)
        if size > MAX_BYTES:
            raise ValueError("batch_ledger_size_limit")
        members.append(member)
    frame = json.dumps(
        [
            "ingestion_batch_v1",
            batch.source_id,
            str(batch.ingestion_run_id),
            batch.parser_version,
            members,
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    if len(frame) > MAX_BYTES:
        raise ValueError("batch_ledger_size_limit")
    return hashlib.sha256(frame).hexdigest()


def _validate_parents(session: Session, batch: BronzeBatch) -> None:
    run = session.get(IngestionRun, batch.ingestion_run_id, populate_existing=True)
    if run is None or run.source_id != batch.source_id:
        raise ValueError("batch_ledger_run_mismatch")
    for artifact in batch.artifacts:
        parent = session.get(SourceRecord, _uuid(artifact.source_record_id), populate_existing=True)
        if parent is None or (
            parent.source_id,
            parent.object_key,
            parent.content_sha256,
            parent.mime_type,
            parent.source_url,
            _date(parent.published_at),
        ) != (
            batch.source_id,
            artifact.object_key,
            artifact.content_sha256,
            artifact.mime_type,
            artifact.url,
            _date(artifact.published_at),
        ):
            raise ValueError("batch_ledger_reference_mismatch")


def _require_clean(session: Session) -> None:
    tracked = (IngestionRun, SourceRecord, IngestionBatch, IngestionBatchMember)
    if any(
        isinstance(row, tracked)
        for group in (session.new, session.dirty, session.deleted)
        for row in group
    ):
        raise ValueError("batch_ledger_pending_parent_changes")


def read_bronze_batch(session: Session, run_id: UUID) -> BronzeBatch:
    _require_clean(session)
    if not isinstance(run_id, UUID):
        raise ValueError("batch_ledger_invalid_uuid")
    _uuid(run_id)
    header = session.get(IngestionBatch, run_id, populate_existing=True)
    if header is None:
        raise ValueError("batch_ledger_missing")
    rows = session.scalars(
        select(IngestionBatchMember)
        .where(IngestionBatchMember.run_id == run_id)
        .order_by(IngestionBatchMember.ordinal)
        .limit(MAX_MEMBERS + 1)
        .execution_options(populate_existing=True)
    ).all()
    if len(rows) != header.n_artifacts or any(
        row.ordinal != index for index, row in enumerate(rows)
    ):
        raise ValueError("batch_ledger_members_mismatch")
    batch = BronzeBatch(
        header.source_id,
        run_id,
        header.parser_version,
        tuple(
            RawArtifact(
                str(row.source_record_id),
                row.object_key,
                row.content_sha256,
                row.mime_type,
                row.source_url,
                row.is_new,
                row.published_at,
            )
            for row in rows
        ),
    )
    if batch_digest(batch) != header.batch_sha256:
        raise ValueError("batch_ledger_digest_mismatch")
    _validate_parents(session, batch)
    return batch


def persist_bronze_batch(session: Session, batch: BronzeBatch) -> str:
    _require_clean(session)
    digest = batch_digest(batch)
    # Same caller transaction: no independent FK insert behind its own run lock.
    run = session.scalar(
        select(IngestionRun)
        .where(IngestionRun.run_id == batch.ingestion_run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if run is None or run.source_id != batch.source_id or run.status != "running":
        raise ValueError("batch_ledger_run_not_running")
    _validate_parents(session, batch)
    if session.get(IngestionBatch, batch.ingestion_run_id, populate_existing=True) is not None:
        if batch_digest(read_bronze_batch(session, batch.ingestion_run_id)) != digest:
            raise ValueError("batch_ledger_existing_mismatch")
        return digest
    session.add(
        IngestionBatch(
            run_id=batch.ingestion_run_id,
            source_id=batch.source_id,
            parser_version=batch.parser_version,
            n_artifacts=len(batch.artifacts),
            batch_sha256=digest,
        )
    )
    session.flush()
    for index, artifact in enumerate(batch.artifacts):
        session.add(
            IngestionBatchMember(
                run_id=batch.ingestion_run_id,
                ordinal=index,
                source_record_id=_uuid(artifact.source_record_id),
                object_key=artifact.object_key,
                content_sha256=artifact.content_sha256,
                mime_type=artifact.mime_type,
                source_url=artifact.url,
                is_new=artifact.is_new,
                published_at=artifact.published_at,
            )
        )
    session.flush()
    if batch_digest(read_bronze_batch(session, batch.ingestion_run_id)) != digest:
        raise ValueError("batch_ledger_write_mismatch")
    return digest
