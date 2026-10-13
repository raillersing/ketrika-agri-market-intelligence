"""Append-only native Silver intentions and transactional results."""

from alembic import op

revision: str = "0007_silver_attempt"
down_revision: str = "0006_ingestion_batch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE meta.silver_attempt (
      attempt_id UUID PRIMARY KEY,
      run_id UUID NOT NULL UNIQUE REFERENCES meta.ingestion_batch(run_id),
      batch_sha256 TEXT NOT NULL CHECK (batch_sha256 ~ '^[0-9a-f]{64}$'),
      started_at TIMESTAMPTZ NOT NULL,
      resumed_from UUID REFERENCES meta.ingestion_batch(run_id),
      CHECK (resumed_from IS NULL OR resumed_from <> run_id)
    );
    CREATE TABLE meta.silver_attempt_result (
      attempt_id UUID PRIMARY KEY REFERENCES meta.silver_attempt(attempt_id),
      finished_at TIMESTAMPTZ NOT NULL,
      status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
      stats JSONB,
      error_class TEXT,
      CHECK ((status = 'success' AND jsonb_typeof(stats) = 'object' AND stats IS NOT NULL
              AND error_class IS NULL)
          OR (status = 'failed' AND stats IS NULL AND error_class IS NOT NULL
              AND error_class ~ '^[A-Za-z_][A-Za-z0-9_]{0,127}$'))
    );
    CREATE TRIGGER silver_attempt_immutable BEFORE UPDATE OR DELETE
      ON meta.silver_attempt FOR EACH ROW EXECUTE FUNCTION meta.reject_ingestion_batch_mutation();
    CREATE TRIGGER silver_attempt_result_immutable BEFORE UPDATE OR DELETE
      ON meta.silver_attempt_result FOR EACH ROW EXECUTE FUNCTION meta.reject_ingestion_batch_mutation();
    GRANT SELECT, INSERT ON meta.silver_attempt, meta.silver_attempt_result TO ketrika_app;
    """)


def downgrade() -> None:
    raise RuntimeError("silver_attempt_history_downgrade_forbidden")
