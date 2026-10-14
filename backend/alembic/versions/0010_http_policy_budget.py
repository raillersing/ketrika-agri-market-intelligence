"""Durable HTTP reservations and policy stops; no active data backfill."""

from alembic import op

revision: str = "0010_http_policy_budget"
down_revision: str = "0009_silver_attempt_member"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE meta.http_daily_budget (
      scope TEXT NOT NULL CHECK (scope IN ('source', 'domain')),
      scope_key TEXT NOT NULL CHECK (length(scope_key) BETWEEN 1 AND 512),
      day_utc DATE NOT NULL,
      request_count INTEGER NOT NULL DEFAULT 0 CHECK (request_count >= 0),
      budget_limit INTEGER NOT NULL CHECK (budget_limit >= 0),
      PRIMARY KEY (scope, scope_key, day_utc)
    );
    CREATE TABLE meta.http_domain_pacing (
      domain TEXT PRIMARY KEY,
      next_allowed_at TIMESTAMPTZ NOT NULL,
      max_rps DOUBLE PRECISION NOT NULL CHECK (max_rps > 0 AND max_rps <= 1000)
    );
    CREATE TABLE meta.http_policy_stop (
      scope TEXT NOT NULL CHECK (scope IN ('source', 'origin')),
      scope_key TEXT NOT NULL CHECK (length(scope_key) BETWEEN 1 AND 512),
      reason_code TEXT NOT NULL CHECK (reason_code = 'challenge'),
      status_code INTEGER NOT NULL CHECK (status_code BETWEEN 100 AND 599),
      stopped_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (scope, scope_key)
    );
    CREATE TRIGGER http_policy_stop_immutable BEFORE UPDATE OR DELETE
      ON meta.http_policy_stop FOR EACH ROW EXECUTE FUNCTION meta.reject_ingestion_batch_mutation();
    GRANT SELECT, INSERT, UPDATE ON meta.http_daily_budget, meta.http_domain_pacing TO ketrika_app;
    GRANT SELECT, INSERT ON meta.http_policy_stop TO ketrika_app;
    """)


def downgrade() -> None:
    raise RuntimeError("http_policy_history_downgrade_forbidden")
