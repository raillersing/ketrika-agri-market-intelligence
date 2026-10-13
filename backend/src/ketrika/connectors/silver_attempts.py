"""Native attempt ownership; an unfinished intention is unknown, never success."""

import hashlib
import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ketrika.connectors.batch_ledger import batch_digest, read_bronze_batch
from ketrika.connectors.document_partitions import document_keys, read_document_partition
from ketrika.connectors.stages import BronzeBatch
from ketrika.core.artifact_identity import ArtifactProcessingIdentity
from ketrika.core.db import get_engine, get_session
from ketrika.core.models.db import IngestionRun

COUNTERS = frozenset(
    {
        "n_fetched",
        "n_new_artifacts",
        "n_inserted",
        "n_superseded",
        "n_skipped",
        "n_rejected",
        "n_review",
    }
)


class SilverRunBusy(RuntimeError):
    """Native owner is active; do not mark its run as failed."""


def _run_id(run_id: UUID) -> UUID:
    if not isinstance(run_id, UUID) or run_id.int == 0:
        raise ValueError("silver_attempt_invalid_run")
    return run_id


def advisory_key(run_id: UUID) -> int:
    digest = hashlib.sha256(b"ketrika_silver_run_v1" + _run_id(run_id).bytes).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


@contextmanager
def exclusive_silver_run(run_id: UUID, source_id: str | None = None) -> Iterator[None]:
    """Pinned connection: commits cannot return the session lock to the pool."""
    keys = [advisory_key(run_id)]
    if source_id is not None:
        if not isinstance(source_id, str) or re.fullmatch(r"[a-z0-9_]{1,128}", source_id) is None:
            raise ValueError("silver_attempt_invalid_source")
        digest = hashlib.sha256(b"ketrika_silver_source_v1" + source_id.encode("ascii")).digest()
        keys.append(int.from_bytes(digest[:8], "big", signed=True))
    acquired_keys = []
    with get_engine().connect() as connection:
        try:
            for key in keys:
                acquired = connection.scalar(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
                )
                if acquired is True:
                    acquired_keys.append(key)
                connection.commit()
                if acquired is not True:
                    raise SilverRunBusy("silver_run_busy")
        except SilverRunBusy:
            if acquired_keys:
                connection.invalidate()
            raise
        except BaseException:
            connection.invalidate()
            raise
        try:
            yield
        finally:
            try:
                for key in reversed(acquired_keys):
                    released = connection.scalar(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": key}
                    )
                    connection.commit()
                    if released is not True:
                        connection.invalidate()
                        raise RuntimeError("silver_run_unlock_failed")
            except BaseException:
                connection.invalidate()
                raise


def validate_stats(value: Any) -> dict[str, int]:
    if not isinstance(value, dict) or not value or not set(value).issubset(COUNTERS):
        raise ValueError("silver_attempt_invalid_stats")
    if any(type(count) is not int or not 0 <= count <= 2**63 - 1 for count in value.values()):
        raise ValueError("silver_attempt_invalid_stats")
    return dict(value)


def validate_native_stats(value: Any) -> dict[str, int]:
    stats = validate_stats(value)
    if not {"n_fetched", "n_new_artifacts", "n_inserted", "n_superseded", "n_skipped"}.issubset(
        stats
    ):
        raise ValueError("silver_attempt_stats_incomplete")
    return stats


def read_success(batch: BronzeBatch) -> dict[str, int] | None:
    """Stored success only; caller holds the run lock and verifies the batch."""
    digest = batch_digest(batch)
    with get_session() as session:
        if batch_digest(read_bronze_batch(session, batch.ingestion_run_id)) != digest:
            raise ValueError("silver_recorded_batch_mismatch")
        row = (
            session.execute(
                text(
                    "SELECT a.attempt_id, a.batch_sha256, r.status, r.stats, i.status AS run_status, "
                    "i.n_fetched, i.n_new_artifacts, i.n_records, i.n_review "
                    "FROM meta.silver_attempt a JOIN meta.silver_attempt_result r USING (attempt_id) "
                    "JOIN meta.ingestion_run i ON i.run_id = a.run_id WHERE a.run_id = :run"
                ),
                {"run": batch.ingestion_run_id},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        if row["batch_sha256"] != digest:
            raise ValueError("silver_attempt_batch_mismatch")
        if row["status"] != "success":
            return None
        if row["run_status"] != "success":
            raise ValueError("silver_attempt_result_inconsistent")
        members = (
            session.execute(
                text(
                    "SELECT ordinal,source_record_id,document_key,processing_key,normalizer_version,reference_manifest_sha256 "
                    "FROM meta.silver_attempt_member WHERE attempt_id=:attempt ORDER BY ordinal LIMIT 100001"
                ),
                {"attempt": row["attempt_id"]},
            )
            .mappings()
            .all()
        )
        keys = document_keys(batch)
        if len(members) != len(batch.artifacts):
            raise ValueError("silver_attempt_members_incomplete")
        for ordinal, (member, artifact, key) in enumerate(
            zip(members, batch.artifacts, keys, strict=True)
        ):
            if (member["ordinal"], str(member["source_record_id"]), member["document_key"]) != (
                ordinal,
                artifact.source_record_id,
                key,
            ):
                raise ValueError("silver_attempt_member_mismatch")
            if member["processing_key"] is not None:
                identity = ArtifactProcessingIdentity(
                    batch.source_id,
                    UUID(artifact.source_record_id),
                    artifact.content_sha256,
                    batch.parser_version,
                    member["normalizer_version"],
                    member["reference_manifest_sha256"],
                )
                if identity.processing_key != member["processing_key"]:
                    raise ValueError("silver_attempt_processing_identity_mismatch")
            elif (
                member["normalizer_version"] is not None
                or member["reference_manifest_sha256"] is not None
            ):
                raise ValueError("silver_attempt_processing_identity_mismatch")
        stats = validate_native_stats(row["stats"])
        if (
            stats["n_fetched"],
            stats["n_new_artifacts"],
            stats["n_inserted"] + stats["n_superseded"],
            stats.get("n_review", 0),
        ) != (row["n_fetched"], row["n_new_artifacts"], row["n_records"], row["n_review"]):
            raise ValueError("silver_attempt_result_inconsistent")
        return stats


def begin_attempt(
    batch: BronzeBatch, resumed_from: UUID | None = None, document_key: str | None = None
) -> UUID:
    """Commit before the data session locks the run/FK parent."""
    digest = batch_digest(batch)
    if resumed_from is not None:
        _run_id(resumed_from)
        if resumed_from == batch.ingestion_run_id:
            raise ValueError("silver_attempt_self_resume")
    attempt_id = uuid4()
    with get_session() as session:
        recorded = read_bronze_batch(session, batch.ingestion_run_id)
        if batch_digest(recorded) != digest:
            raise ValueError("silver_recorded_batch_mismatch")
        run = session.scalar(
            select(IngestionRun)
            .where(IngestionRun.run_id == batch.ingestion_run_id)
            .with_for_update()
        )
        if run is None or run.status != "running" or run.finished_at is not None:
            raise ValueError("silver_attempt_run_not_running")
        if (
            session.scalar(
                text("SELECT attempt_id FROM meta.silver_attempt WHERE run_id = :run"),
                {"run": batch.ingestion_run_id},
            )
            is not None
        ):
            raise ValueError("silver_attempt_exists_resume_required")
        if resumed_from is not None:
            previous = read_bronze_batch(session, resumed_from)
            expected_artifacts = previous.artifacts
            if document_key is not None:
                origin, member = read_document_partition(session, document_key, batch.source_id)
                if origin.ingestion_run_id != resumed_from:
                    raise ValueError("silver_attempt_document_origin_mismatch")
                expected_artifacts = (member,)
            if (previous.source_id, previous.parser_version, expected_artifacts) != (
                batch.source_id,
                batch.parser_version,
                batch.artifacts,
            ):
                raise ValueError("silver_attempt_resume_batch_mismatch")
        elif document_key is not None:
            raise ValueError("silver_attempt_document_origin_required")
        session.execute(
            text(
                "INSERT INTO meta.silver_attempt "
                "(attempt_id,run_id,batch_sha256,started_at,resumed_from,document_key) "
                "VALUES (:attempt,:run,:sha,:started,:previous,:document)"
            ),
            {
                "attempt": attempt_id,
                "run": batch.ingestion_run_id,
                "sha": digest,
                "started": datetime.now(UTC),
                "previous": resumed_from,
                "document": document_key,
            },
        )
    return attempt_id


def finish_success(
    session: Session,
    attempt_id: UUID,
    stats: Any,
    *,
    batch: BronzeBatch,
    identities: list[ArtifactProcessingIdentity],
) -> None:
    """No commit: receipt and observations must succeed or roll back together."""
    values = validate_native_stats(stats)
    keys = document_keys(batch)
    artifacts_by_reference = {
        UUID(artifact.source_record_id): artifact for artifact in batch.artifacts
    }
    by_reference = {}
    for identity in identities:
        if (
            not isinstance(identity, ArtifactProcessingIdentity)
            or identity.source_record_id in by_reference
        ):
            raise ValueError("silver_attempt_processing_identity_invalid")
        matching = artifacts_by_reference.get(identity.source_record_id)
        if (
            matching is None
            or identity.source_id != batch.source_id
            or identity.parser_version != batch.parser_version
            or identity.content_sha256 != matching.content_sha256
        ):
            raise ValueError("silver_attempt_processing_identity_invalid")
        by_reference[identity.source_record_id] = identity
    session.execute(
        text(
            "INSERT INTO meta.silver_attempt_result "
            "(attempt_id,finished_at,status,stats) "
            "VALUES (:attempt,:finished,'success',CAST(:stats AS jsonb))"
        ),
        {
            "attempt": _run_id(attempt_id),
            "finished": datetime.now(UTC),
            "stats": json.dumps(values, sort_keys=True, separators=(",", ":")),
        },
    )
    for ordinal, (artifact, key) in enumerate(zip(batch.artifacts, keys, strict=True)):
        reference = UUID(artifact.source_record_id)
        member_identity = by_reference.get(reference)
        session.execute(
            text(
                "INSERT INTO meta.silver_attempt_member "
                "(attempt_id,ordinal,source_record_id,document_key,processing_key,normalizer_version,reference_manifest_sha256) "
                "VALUES (:attempt,:ordinal,:reference,:document,:processing,:normalizer,:manifest)"
            ),
            {
                "attempt": attempt_id,
                "ordinal": ordinal,
                "reference": reference,
                "document": key,
                "processing": member_identity.processing_key if member_identity else None,
                "normalizer": member_identity.normalizer_version if member_identity else None,
                "manifest": member_identity.reference_manifest_sha256 if member_identity else None,
            },
        )


def finish_failure(attempt_id: UUID, cause: type[BaseException]) -> None:
    if not isinstance(cause, type) or not issubclass(cause, BaseException):
        raise ValueError("silver_attempt_invalid_error_class")
    name = cause.__name__
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", name) is None:
        raise ValueError("silver_attempt_invalid_error_class")
    with get_session() as session:
        session.execute(
            text(
                "INSERT INTO meta.silver_attempt_result "
                "(attempt_id,finished_at,status,error_class) "
                "VALUES (:attempt,:finished,'failed',:error)"
            ),
            {"attempt": _run_id(attempt_id), "finished": datetime.now(UTC), "error": name},
        )
