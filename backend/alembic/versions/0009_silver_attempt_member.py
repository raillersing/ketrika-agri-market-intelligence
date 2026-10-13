"""Append-only verified processing members, no historical inference."""

from alembic import op

revision: str = "0009_silver_attempt_member"
down_revision: str = "0008_document_partition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE meta.silver_attempt_member (
      attempt_id UUID NOT NULL REFERENCES meta.silver_attempt_result(attempt_id),
      ordinal INTEGER NOT NULL CHECK (ordinal BETWEEN 0 AND 99999),
      source_record_id UUID NOT NULL REFERENCES meta.source_record(source_record_id),
      document_key TEXT NOT NULL REFERENCES meta.document_partition(partition_key),
      processing_key TEXT,
      normalizer_version TEXT,
      reference_manifest_sha256 TEXT,
      PRIMARY KEY (attempt_id, ordinal),
      UNIQUE (attempt_id, source_record_id),
      CHECK ((processing_key IS NULL AND normalizer_version IS NULL AND reference_manifest_sha256 IS NULL)
          OR (processing_key IS NOT NULL AND processing_key ~ '^[0-9a-f]{64}$'
              AND normalizer_version IS NOT NULL AND length(normalizer_version) BETWEEN 1 AND 128
              AND reference_manifest_sha256 IS NOT NULL AND reference_manifest_sha256 ~ '^[0-9a-f]{64}$'))
    );
    CREATE TRIGGER silver_attempt_member_immutable BEFORE UPDATE OR DELETE
      ON meta.silver_attempt_member FOR EACH ROW EXECUTE FUNCTION meta.reject_ingestion_batch_mutation();
    GRANT SELECT, INSERT ON meta.silver_attempt_member TO ketrika_app;
    """)


def downgrade() -> None:
    raise RuntimeError("silver_attempt_member_history_downgrade_forbidden")
