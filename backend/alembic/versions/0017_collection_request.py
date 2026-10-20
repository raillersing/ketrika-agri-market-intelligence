"""Durable receipts for explicit manual collection, never a volatile queue."""

from alembic import op

revision = "0017_collection_request"
down_revision = "0016_supply_arrival_and_stock_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE meta.collection_request (
            request_id UUID PRIMARY KEY,
            selection TEXT,
            status TEXT NOT NULL CHECK(status IN
                ('running','succeeded','partial','failed','interrupted')),
            stage TEXT NOT NULL,
            source_ids JSONB NOT NULL,
            outcomes JSONB NOT NULL DEFAULT '[]',
            publication TEXT NOT NULL DEFAULT 'not_started',
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE ON meta.collection_request TO ketrika_app")


def downgrade() -> None:
    raise RuntimeError("collection_receipts_are_audit_history")
