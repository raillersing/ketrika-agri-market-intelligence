"""Immutable document-version partitions; no historical inference/backfill."""

from alembic import op

revision: str = "0008_document_partition"
down_revision: str = "0007_silver_attempt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE meta.document_partition (
      partition_key TEXT PRIMARY KEY CHECK (partition_key ~ '^[0-9a-f]{64}$'),
      origin_run_id UUID NOT NULL REFERENCES meta.ingestion_batch(run_id),
      source_record_id UUID NOT NULL REFERENCES meta.source_record(source_record_id),
      source_id TEXT NOT NULL REFERENCES meta.source(source_id),
      content_sha256 TEXT NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
      parser_version TEXT NOT NULL
    );
    CREATE TRIGGER document_partition_immutable BEFORE UPDATE OR DELETE
      ON meta.document_partition FOR EACH ROW EXECUTE FUNCTION meta.reject_ingestion_batch_mutation();
    ALTER TABLE meta.silver_attempt ADD COLUMN document_key TEXT
      REFERENCES meta.document_partition(partition_key);
    GRANT SELECT, INSERT ON meta.document_partition TO ketrika_app;
    """)


def downgrade() -> None:
    raise RuntimeError("document_partition_history_downgrade_forbidden")
