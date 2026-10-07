"""Gold materialized views creation and refresh engine (SPECS §15, MVP_EXECUTION_PLAN T5.1)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("ketrika.gold")

# Strict topological order of materialized views
ORDERED_GOLD_VIEWS: list[str] = [
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
]


def get_sql_dir() -> Path:
    """Find directory containing Gold view SQL definitions."""
    pkg_dir = Path(__file__).resolve().parent / "sql"
    if pkg_dir.exists():
        return pkg_dir
    alt_dir = Path("/app/src/ketrika/gold/sql")
    if alt_dir.exists():
        return alt_dir
    raise FileNotFoundError("Could not locate Gold SQL directory")


def init_gold_views(session: Session) -> dict[str, int]:
    """Execute all SQL scripts in numerical order to create or replace Gold materialized views."""
    sql_dir = get_sql_dir()
    sql_files = sorted(sql_dir.glob("*.sql"))
    logger.info("Initializing %d Gold materialized views from %s...", len(sql_files), sql_dir)

    executed = 0
    for f in sql_files:
        sql_content = f.read_text(encoding="utf-8")
        logger.debug("Executing Gold SQL file: %s", f.name)
        session.execute(text(sql_content))
        executed += 1

    # Ensure permissions for ketrika_app and copilot_ro
    session.execute(
        text(
            """
            GRANT USAGE ON SCHEMA gold TO ketrika_app, copilot_ro;
            GRANT SELECT ON ALL TABLES IN SCHEMA gold TO ketrika_app, copilot_ro;
            ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO ketrika_app, copilot_ro;
            """
        )
    )
    session.flush()
    logger.info("Successfully initialized all Gold views.")
    return {"views_initialized": executed}


def refresh_gold_views(
    session: Session,
    concurrently: bool = False,
    views: list[str] | None = None,
) -> dict[str, Any]:
    """Refresh Gold materialized views in strict topological order."""
    target_views = views or ORDERED_GOLD_VIEWS
    logger.info("Refreshing %d Gold materialized views...", len(target_views))

    refreshed: list[str] = []
    errors: dict[str, str] = {}

    for view_name in target_views:
        # Check if materialized view exists
        exists = session.execute(
            text("SELECT 1 FROM pg_matviews WHERE schemaname = 'gold' AND matviewname = :mv"),
            {"mv": view_name},
        ).scalar()

        if not exists:
            logger.warning("Materialized view gold.%s does not exist. Skipping.", view_name)
            continue

        prefix = "CONCURRENTLY " if concurrently else ""
        try:
            session.execute(text(f"REFRESH MATERIALIZED VIEW {prefix}gold.{view_name};"))
            refreshed.append(view_name)
            logger.debug("Refreshed gold.%s", view_name)
        except Exception as e:
            logger.error("Failed to refresh gold.%s: %s", view_name, e)
            errors[view_name] = str(e)
            # If concurrent failed, retry without concurrently
            if concurrently:
                try:
                    session.execute(text(f"REFRESH MATERIALIZED VIEW gold.{view_name};"))
                    refreshed.append(view_name)
                    del errors[view_name]
                except Exception as retry_err:
                    errors[view_name] = str(retry_err)
                    raise

    session.flush()
    logger.info("Successfully refreshed %d Gold materialized views.", len(refreshed))
    return {
        "views_refreshed": refreshed,
        "errors": errors,
        "count": len(refreshed),
    }
