"""Collection checkpoints for resumable, idempotent acquisition (IA-DATA-03).

Tracks collection progress across runs, allowing exact recovery from
transient interruptions (429, 503, timeouts, network disconnects) without
duplicate rows or skipped pages.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ketrika.core.db import get_engine


@dataclass
class CollectionCheckpoint:
    """Represents the progress state of a partitioned source collection."""

    source_id: str
    partition_key: str = ""
    cursor_value: str | None = None
    cursor_type: str = "offset"  # offset, page, cursor, timestamp
    etag: str | None = None
    last_modified: str | None = None
    items_collected: int = 0
    bytes_downloaded: int = 0
    status: str = "in_progress"  # in_progress, completed, failed, paused
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def advance(
        self,
        new_cursor: str | None,
        new_items: int = 0,
        new_bytes: int = 0,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> CollectionCheckpoint:
        """Advance cursor and accumulate collected metrics."""
        self.cursor_value = new_cursor
        self.items_collected += new_items
        self.bytes_downloaded += new_bytes
        if etag:
            self.etag = etag
        if last_modified:
            self.last_modified = last_modified
        self.updated_at = datetime.now(UTC)
        return self

    def mark_completed(self) -> CollectionCheckpoint:
        """Mark collection for this partition as completed."""
        self.status = "completed"
        self.updated_at = datetime.now(UTC)
        return self

    def mark_failed(self, error_message: str | None = None) -> CollectionCheckpoint:
        """Mark collection as failed while preserving resume cursor."""
        self.status = "failed"
        if error_message:
            self.metadata["last_error"] = str(error_message)[:500]
        self.updated_at = datetime.now(UTC)
        return self


class CheckpointStore(Protocol):
    """Protocol for checkpoint storage backends."""

    def get(self, source_id: str, partition_key: str = "") -> CollectionCheckpoint | None:
        """Retrieve existing checkpoint if any."""
        ...

    def save(self, checkpoint: CollectionCheckpoint) -> None:
        """Upsert checkpoint state."""
        ...

    def reset(self, source_id: str, partition_key: str = "") -> None:
        """Reset or clear checkpoint state for clean re-ingestion."""
        ...


class InMemoryCheckpointStore:
    """Thread-safe in-memory store for isolated unit tests."""

    def __init__(self) -> None:
        self._checkpoints: dict[tuple[str, str], CollectionCheckpoint] = {}

    def get(self, source_id: str, partition_key: str = "") -> CollectionCheckpoint | None:
        key = (source_id, partition_key)
        return self._checkpoints.get(key)

    def save(self, checkpoint: CollectionCheckpoint) -> None:
        key = (checkpoint.source_id, checkpoint.partition_key)
        self._checkpoints[key] = checkpoint

    def reset(self, source_id: str, partition_key: str = "") -> None:
        self._checkpoints.pop((source_id, partition_key), None)


class SqlCheckpointStore:
    """PostgreSQL durable checkpoint store backed by meta.collection_checkpoint."""

    def __init__(self, engine_or_session: Engine | Session | None = None) -> None:
        self._engine = engine_or_session if isinstance(engine_or_session, Engine) else None
        self._session = engine_or_session if isinstance(engine_or_session, Session) else None
        if self._engine is None and self._session is None:
            self._engine = get_engine()

    def get(self, source_id: str, partition_key: str = "") -> CollectionCheckpoint | None:
        sql = text(
            """
            SELECT
                source_id, partition_key, cursor_value, cursor_type,
                etag, last_modified, items_collected, bytes_downloaded,
                status, metadata, updated_at
            FROM meta.collection_checkpoint
            WHERE source_id = :sid AND partition_key = :pkey;
            """
        )
        params = {"sid": source_id, "pkey": partition_key}
        if self._session is not None:
            row = self._session.execute(sql, params).fetchone()
        else:
            with self._engine.connect() as conn:
                row = conn.execute(sql, params).fetchone()

        if not row:
            return None

        meta_val = row[9]
        if isinstance(meta_val, str):
            meta_dict = json.loads(meta_val)
        elif isinstance(meta_val, dict):
            meta_dict = meta_val
        else:
            meta_dict = {}

        return CollectionCheckpoint(
            source_id=row[0],
            partition_key=row[1],
            cursor_value=row[2],
            cursor_type=row[3],
            etag=row[4],
            last_modified=row[5],
            items_collected=int(row[6]),
            bytes_downloaded=int(row[7]),
            status=row[8],
            metadata=meta_dict,
            updated_at=row[10],
        )

    def save(self, checkpoint: CollectionCheckpoint) -> None:
        sql = text(
            """
            INSERT INTO meta.collection_checkpoint (
                source_id, partition_key, cursor_value, cursor_type,
                etag, last_modified, items_collected, bytes_downloaded,
                status, metadata, updated_at
            ) VALUES (
                :sid, :pkey, :cursor, :ctype,
                :etag, :last_mod, :items, :bytes,
                :status, CAST(:meta AS jsonb), :updated_at
            )
            ON CONFLICT (source_id, partition_key) DO UPDATE SET
                cursor_value = EXCLUDED.cursor_value,
                cursor_type = EXCLUDED.cursor_type,
                etag = EXCLUDED.etag,
                last_modified = EXCLUDED.last_modified,
                items_collected = EXCLUDED.items_collected,
                bytes_downloaded = EXCLUDED.bytes_downloaded,
                status = EXCLUDED.status,
                metadata = EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at;
            """
        )
        params = {
            "sid": checkpoint.source_id,
            "pkey": checkpoint.partition_key,
            "cursor": checkpoint.cursor_value,
            "ctype": checkpoint.cursor_type,
            "etag": checkpoint.etag,
            "last_mod": checkpoint.last_modified,
            "items": checkpoint.items_collected,
            "bytes": checkpoint.bytes_downloaded,
            "status": checkpoint.status,
            "meta": json.dumps(checkpoint.metadata),
            "updated_at": checkpoint.updated_at,
        }
        if self._session is not None:
            self._session.execute(sql, params)
        else:
            with self._engine.begin() as conn:
                conn.execute(sql, params)

    def reset(self, source_id: str, partition_key: str = "") -> None:
        sql = text(
            "DELETE FROM meta.collection_checkpoint WHERE source_id = :sid AND partition_key = :pkey;"
        )
        params = {"sid": source_id, "pkey": partition_key}
        if self._session is not None:
            self._session.execute(sql, params)
        else:
            with self._engine.begin() as conn:
                conn.execute(sql, params)
