"""Restore the complete quarantine-aware Gold graph without publishing caches (ADR134)."""

from pathlib import Path

from alembic import op

revision = "0021_gold_graph"
down_revision = "0020_quarantine_ledger_and_anti_self_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    definition = (Path(__file__).resolve().parents[1] / "sql/0021_gold_graph.sql").read_text(
        encoding="utf-8"
    )
    if definition.count("WITH NO DATA;") != 14:
        raise RuntimeError("gold_schema_requires_unpopulated_views")
    op.execute(definition)
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA gold TO ketrika_app, copilot_ro")


def downgrade() -> None:
    raise RuntimeError("Refusing to restore an incomplete Gold graph")
