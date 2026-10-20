"""0002_gold_views: Materialized views and indexes for Gold analytical layer.

Reproduces exact views from SPECS.md §15:
- gold.price_obs_current
- gold.price_monthly
- gold.price_monthly_best
- gold.price_changes
- gold.stock_latest
- gold.trade_monthly
- gold.import_dependency
- gold.weather_monthly
- gold.cpi_food
- gold.market_health
- gold.source_health
- gold.forecast_latest

Revision ID: 0002_gold_views
Revises: 0001_initial_schema
Create Date: 2026-10-07 05:15:00
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_gold_views"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Locate SQL scripts
    base_dir = Path(__file__).resolve().parent.parent.parent / "src" / "ketrika" / "gold" / "sql"
    if not base_dir.exists():
        base_dir = Path("/app/src/ketrika/gold/sql")

    views = (
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
    sql_files = [base_dir / f"{index:03d}_{view}.sql" for index, view in enumerate(views, 1)]
    sql_files[-1] = Path(__file__).resolve().parents[1] / "sql" / "012_forecast_latest_pre_0012.sql"
    if not all(file.is_file() for file in sql_files):
        raise RuntimeError(f"No Gold view SQL files found in {base_dir}")

    for sql_file in sql_files:
        sql = sql_file.read_text(encoding="utf-8")
        op.execute(sql)

    # Ensure permissions for ketrika_app and copilot_ro
    op.execute(
        """
        GRANT USAGE ON SCHEMA gold TO ketrika_app, copilot_ro;
        GRANT SELECT ON ALL TABLES IN SCHEMA gold TO ketrika_app, copilot_ro;
        ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO ketrika_app, copilot_ro;
        """
    )


def downgrade() -> None:
    views_reversed = [
        "forecast_latest",
        "source_health",
        "market_health",
        "cpi_food",
        "weather_monthly",
        "import_dependency",
        "trade_monthly",
        "stock_latest",
        "price_changes",
        "price_monthly_best",
        "price_monthly",
        "price_obs_current",
    ]
    for v in views_reversed:
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS gold.{v} CASCADE;")
