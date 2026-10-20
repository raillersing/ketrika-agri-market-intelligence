"""Install post-schema Gold definitions and restore Gold-only copilot privileges."""

from pathlib import Path

from alembic import op

revision = "0018_gold_scope_permissions"
down_revision = "0017_collection_request"
branch_labels = None
depends_on = None


def upgrade() -> None:
    directory = Path(__file__).resolve().parents[2] / "src/ketrika/gold/sql"
    for name in ("013_market_coverage.sql", "014_economic_dashboard.sql"):
        definition = (directory / name).read_text(encoding="utf-8")
        if "WITH NO DATA;" not in definition:
            raise RuntimeError("gold_schema_requires_unpopulated_views")
        op.execute(definition)
    op.execute("REVOKE ALL PRIVILEGES ON obs.macro_observation FROM copilot_ro")
    op.execute(
        "GRANT SELECT ON gold.market_coverage, gold.economic_dashboard TO copilot_ro, ketrika_app"
    )


def downgrade() -> None:
    """Never restore excessive privileges or publish unqualified caches."""
