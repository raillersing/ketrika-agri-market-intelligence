"""Codec/guard tests; never stand in for SQL persistence or crash recovery."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from ketrika.connectors.base import RawArtifact
from ketrika.connectors.batch_ledger import batch_digest, persist_bronze_batch, read_bronze_batch
from ketrika.connectors.stages import BronzeBatch
from ketrika.core.models.db import IngestionRun, SourceRecord


def sample() -> BronzeBatch:
    artifact = RawArtifact(
        str(uuid4()),
        "dummy_batch/2026/10/" + "a" * 64 + ".json",
        "a" * 64,
        "application/json",
        "https://example.invalid/synthetic",
        True,
        datetime(2026, 10, 1, tzinfo=UTC),
    )
    return BronzeBatch("dummy_batch", uuid4(), "fixture-v1", (artifact,))


def test_digest_repeats_and_empty_is_explicit() -> None:
    batch = sample()
    assert batch_digest(batch) == batch_digest(batch)
    assert len(batch_digest(batch)) == 64
    assert batch_digest(batch) != batch_digest(replace(batch, artifacts=()))


def test_timestamp_timezone_is_canonical_not_an_inferred_date() -> None:
    batch = sample()
    artifact = batch.artifacts[0]
    assert artifact.published_at is not None
    same = replace(
        artifact, published_at=artifact.published_at.astimezone(timezone(timedelta(hours=3)))
    )
    assert batch_digest(batch) == batch_digest(replace(batch, artifacts=(same,)))


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", "UNKNOWN"),
        ("source_id", ""),
        ("source_id", "a" * 129),
        ("parser_version", ""),
        ("parser_version", " v1"),
        ("parser_version", "v\n1"),
        ("parser_version", "v" * 129),
        ("ingestion_run_id", UUID(int=0)),
        ("artifacts", []),
    ],
)
def test_invalid_batch(field: str, value: Any) -> None:
    with pytest.raises(ValueError):
        batch_digest(replace(sample(), **{field: value}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_record_id", "not-uuid"),
        ("source_record_id", str(UUID(int=0))),
        ("content_sha256", "A" * 64),
        ("content_sha256", "a" * 63),
        ("mime_type", ""),
        ("object_key", ""),
        ("object_key", "../\n"),
        ("is_new", 1),
        ("url", "x" * 8193),
        ("published_at", datetime(2026, 10, 1)),
    ],
)
def test_invalid_artifact(field: str, value: Any) -> None:
    batch = sample()
    with pytest.raises(ValueError):
        batch_digest(replace(batch, artifacts=(replace(batch.artifacts[0], **{field: value}),)))


def test_duplicate_reference_and_order() -> None:
    batch = sample()
    first = batch.artifacts[0]
    with pytest.raises(ValueError, match="duplicate_reference"):
        batch_digest(replace(batch, artifacts=(first, first)))
    second = replace(first, source_record_id=str(uuid4()))
    assert batch_digest(replace(batch, artifacts=(first, second))) != batch_digest(
        replace(batch, artifacts=(second, first))
    )


def test_size_bound_is_not_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ketrika.connectors.batch_ledger.MAX_BYTES", 16)
    with pytest.raises(ValueError, match="size_limit"):
        batch_digest(sample())


def test_member_bound_is_not_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ketrika.connectors.batch_ledger.MAX_MEMBERS", 0)
    with pytest.raises(ValueError, match="invalid_batch"):
        batch_digest(sample())


@pytest.mark.parametrize("kind", ["new", "dirty", "deleted"])
@pytest.mark.parametrize("model", [IngestionRun, SourceRecord])
def test_pending_parents_refused_before_refresh(kind: str, model: type) -> None:
    session = Mock(spec=Session)
    session.new, session.dirty, session.deleted = set(), set(), set()
    getattr(session, kind).add(model())
    batch = sample()
    with pytest.raises(ValueError, match="pending_parent_changes"):
        persist_bronze_batch(session, batch)
    with pytest.raises(ValueError, match="pending_parent_changes"):
        read_bronze_batch(session, batch.ingestion_run_id)
    session.get.assert_not_called()
    session.scalar.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
