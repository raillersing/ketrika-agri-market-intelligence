"""Add collection_checkpoint table for resumable, bounded ingestion (IA-DATA-03)."""

from alembic import op

revision = "0029_collection_checkpoint"
down_revision = "0028_ambiguous_milled_rice_alias"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS meta.collection_checkpoint (
            source_id text NOT NULL,
            partition_key text NOT NULL DEFAULT '',
            cursor_value text,
            cursor_type text NOT NULL DEFAULT 'offset',
            etag text,
            last_modified text,
            items_collected integer NOT NULL DEFAULT 0,
            bytes_downloaded bigint NOT NULL DEFAULT 0,
            status text NOT NULL DEFAULT 'in_progress',
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamp with time zone NOT NULL DEFAULT now(),
            updated_at timestamp with time zone NOT NULL DEFAULT now(),
            CONSTRAINT collection_checkpoint_pkey PRIMARY KEY (source_id, partition_key),
            CONSTRAINT collection_checkpoint_source_id_fkey FOREIGN KEY (source_id) REFERENCES meta.source(source_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_collection_checkpoint_status ON meta.collection_checkpoint (status);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS meta.collection_checkpoint;")
