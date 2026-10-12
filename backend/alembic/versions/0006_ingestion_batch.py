"""Add immutable persisted Bronze batches; never mutate existing data."""

from alembic import op

revision: str = "0006_ingestion_batch"
down_revision: str = "0005_gold_unpopulated"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE meta.ingestion_batch (
      run_id UUID PRIMARY KEY REFERENCES meta.ingestion_run(run_id),
      source_id TEXT NOT NULL REFERENCES meta.source(source_id),
      parser_version TEXT NOT NULL,
      n_artifacts INTEGER NOT NULL CONSTRAINT batch_count CHECK (n_artifacts BETWEEN 0 AND 100000),
      batch_sha256 TEXT NOT NULL CONSTRAINT batch_sha CHECK (batch_sha256 ~ '^[0-9a-f]{64}$')
    );
    CREATE TABLE meta.ingestion_batch_member (
      run_id UUID NOT NULL REFERENCES meta.ingestion_batch(run_id),
      ordinal INTEGER NOT NULL CONSTRAINT batch_member_ordinal CHECK (ordinal BETWEEN 0 AND 99999),
      source_record_id UUID NOT NULL REFERENCES meta.source_record(source_record_id),
      object_key TEXT NOT NULL,
      content_sha256 TEXT NOT NULL CONSTRAINT batch_member_sha CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
      mime_type TEXT NOT NULL,
      source_url TEXT NOT NULL,
      is_new BOOLEAN NOT NULL,
      published_at TIMESTAMPTZ,
      PRIMARY KEY (run_id, ordinal),
      CONSTRAINT batch_member_reference UNIQUE (run_id, source_record_id)
    );
    CREATE FUNCTION meta.reject_ingestion_batch_mutation() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      RAISE EXCEPTION 'ingestion_batch_immutable' USING ERRCODE = '55000';
    END;
    $$;
    CREATE TRIGGER ingestion_batch_immutable BEFORE UPDATE OR DELETE
      ON meta.ingestion_batch FOR EACH ROW EXECUTE FUNCTION meta.reject_ingestion_batch_mutation();
    CREATE TRIGGER ingestion_batch_member_immutable BEFORE UPDATE OR DELETE
      ON meta.ingestion_batch_member FOR EACH ROW EXECUTE FUNCTION meta.reject_ingestion_batch_mutation();
    GRANT SELECT, INSERT ON meta.ingestion_batch, meta.ingestion_batch_member TO ketrika_app;
    """)


def downgrade() -> None:
    raise RuntimeError("ingestion_batch_history_downgrade_forbidden")
