"""Invalidate legacy unqualified Gold caches, preserving all underlying data."""

from pathlib import Path

from alembic import op

revision: str = "0005_gold_unpopulated"
down_revision: str = "0004_production_raw"
branch_labels = None
depends_on = None

VIEWS = (
    "price_obs_current",
    "price_monthly",
    "price_monthly_best",
    "price_changes",
    "stock_latest",
    "trade_monthly",
    "import_dependency",
    "weather_monthly",
    "cpi_food",
    "market_health",
    "source_health",
    "forecast_latest",
)


def upgrade() -> None:
    directory = Path(__file__).resolve().parents[2] / "src" / "ketrika" / "gold" / "sql"
    files = sorted(directory.glob("*.sql"))
    if [file.name for file in files] != [
        f"{index:03d}_{view}.sql" for index, view in enumerate(VIEWS, 1)
    ]:
        raise RuntimeError("gold_schema_definition_missing")
    definitions = [file.read_text(encoding="utf-8") for file in files]
    if any("WITH NO DATA;" not in definition for definition in definitions):
        raise RuntimeError("gold_schema_requires_unpopulated_views")
    for definition in definitions:
        op.execute(definition)
    op.execute(
        "GRANT USAGE ON SCHEMA gold TO ketrika_app, copilot_ro; GRANT SELECT ON ALL TABLES IN SCHEMA gold TO ketrika_app, copilot_ro; ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO ketrika_app, copilot_ro;"
    )


def downgrade() -> None:
    """Leave caches unpopulated/guarded; never restore unverified historical values."""
