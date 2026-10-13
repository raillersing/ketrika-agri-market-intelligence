"""Recorded document/version identity, never an inferred edition or forecast."""

import hashlib
import json
import re
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.connectors.base import RawArtifact
from ketrika.connectors.batch_ledger import batch_digest, read_bronze_batch
from ketrika.connectors.stages import BronzeBatch


def document_key(batch: BronzeBatch, artifact: RawArtifact) -> str:
    batch_digest(batch)
    if artifact not in batch.artifacts:
        raise ValueError("document_partition_outside_batch")
    return _frame_key(batch, artifact)


def _frame_key(batch: BronzeBatch, artifact: RawArtifact) -> str:
    frame = [
        "document_version_v1",
        batch.source_id,
        str(UUID(artifact.source_record_id)),
        artifact.content_sha256,
        batch.parser_version,
    ]
    return hashlib.sha256(
        json.dumps(frame, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def document_keys(batch: BronzeBatch) -> tuple[str, ...]:
    """Validate once, not once per member, when publishing a large batch."""
    batch_digest(batch)
    return tuple(_frame_key(batch, artifact) for artifact in batch.artifacts)


def register_document_partitions(session: Session, batch: BronzeBatch) -> tuple[str, ...]:
    """Caller already persisted the batch; no commit and no Bronze writes."""
    recorded = read_bronze_batch(session, batch.ingestion_run_id)
    if batch_digest(recorded) != batch_digest(batch):
        raise ValueError("document_partition_batch_mismatch")
    keys = []
    for artifact in batch.artifacts:
        key = _frame_key(batch, artifact)
        values = {
            "key": key,
            "run": batch.ingestion_run_id,
            "reference": UUID(artifact.source_record_id),
            "source": batch.source_id,
            "sha": artifact.content_sha256,
            "parser": batch.parser_version,
        }
        session.execute(
            text(
                "INSERT INTO meta.document_partition "
                "(partition_key,origin_run_id,source_record_id,source_id,content_sha256,parser_version) "
                "VALUES (:key,:run,:reference,:source,:sha,:parser) ON CONFLICT DO NOTHING"
            ),
            values,
        )
        row = session.execute(
            text(
                "SELECT source_record_id,source_id,content_sha256,parser_version "
                "FROM meta.document_partition WHERE partition_key=:key"
            ),
            {"key": key},
        ).one()
        if tuple(row) != (
            UUID(artifact.source_record_id),
            batch.source_id,
            artifact.content_sha256,
            batch.parser_version,
        ):
            raise ValueError("document_partition_identity_mismatch")
        keys.append(key)
    return tuple(keys)


def read_document_partition(
    session: Session, key: str, source_id: str
) -> tuple[BronzeBatch, RawArtifact]:
    if not isinstance(key, str) or re.fullmatch(r"[0-9a-f]{64}", key) is None:
        raise ValueError("document_partition_invalid_key")
    row = (
        session.execute(
            text("SELECT * FROM meta.document_partition WHERE partition_key=:key"), {"key": key}
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["source_id"] != source_id:
        raise ValueError("document_partition_source_mismatch")
    batch = read_bronze_batch(session, row["origin_run_id"])
    members = [
        member
        for member in batch.artifacts
        if member.source_record_id == str(row["source_record_id"])
    ]
    if (
        batch.source_id != source_id
        or batch.parser_version != row["parser_version"]
        or len(members) != 1
        or members[0].content_sha256 != row["content_sha256"]
        or document_key(batch, members[0]) != key
    ):
        raise ValueError("document_partition_identity_mismatch")
    return batch, members[0]
