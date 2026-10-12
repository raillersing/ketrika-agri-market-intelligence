"""Immutable Bronze membership; not Silver attempt or byte verification."""

from datetime import datetime
from uuid import UUID as UUIDType

from sqlalchemy import (
    BOOLEAN,
    INTEGER,
    TEXT,
    CheckConstraint,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ketrika.core.models.db import Base


class IngestionBatch(Base):
    __tablename__ = "ingestion_batch"
    __table_args__ = (
        CheckConstraint("n_artifacts BETWEEN 0 AND 100000", name="batch_count"),
        CheckConstraint("batch_sha256 ~ '^[0-9a-f]{64}$'", name="batch_sha"),
        {"schema": "meta"},
    )

    run_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta.ingestion_run.run_id"), primary_key=True
    )
    source_id: Mapped[str] = mapped_column(
        TEXT, ForeignKey("meta.source.source_id"), nullable=False
    )
    parser_version: Mapped[str] = mapped_column(TEXT, nullable=False)
    n_artifacts: Mapped[int] = mapped_column(INTEGER, nullable=False)
    batch_sha256: Mapped[str] = mapped_column(TEXT, nullable=False)


class IngestionBatchMember(Base):
    __tablename__ = "ingestion_batch_member"
    __table_args__ = (
        CheckConstraint("ordinal BETWEEN 0 AND 99999", name="batch_member_ordinal"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="batch_member_sha"),
        UniqueConstraint("run_id", "source_record_id", name="batch_member_reference"),
        {"schema": "meta"},
    )

    run_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta.ingestion_batch.run_id"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(INTEGER, primary_key=True)
    source_record_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta.source_record.source_record_id"), nullable=False
    )
    object_key: Mapped[str] = mapped_column(TEXT, nullable=False)
    content_sha256: Mapped[str] = mapped_column(TEXT, nullable=False)
    mime_type: Mapped[str] = mapped_column(TEXT, nullable=False)
    source_url: Mapped[str] = mapped_column(TEXT, nullable=False)
    is_new: Mapped[bool] = mapped_column(BOOLEAN, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
