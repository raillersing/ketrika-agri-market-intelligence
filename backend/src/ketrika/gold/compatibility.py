"""Automated pre-control and upgrade of historical Gold materialized view definitions (BL-019).

Enforces:
1. Detection of outdated Gold schemas on existing databases (e.g. price_monthly missing source_family).
2. Safe topological re-installation of required view definitions WITH NO DATA.
3. 100% preservation of Bronze objects, source_records, and observations.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

logger = logging.getLogger("ketrika.gold.compatibility")


def is_gold_definition_outdated(bind: Connection | Session) -> bool:
    """Check if existing Gold materialized views lack current schema columns (e.g. source_family)."""
    query = text(
        """
        SELECT 1 FROM pg_matviews m
        WHERE m.schemaname = 'gold' AND m.matviewname = 'price_monthly'
          AND NOT EXISTS (
              SELECT 1 FROM pg_attribute a
              JOIN pg_class c ON a.attrelid = c.oid
              JOIN pg_namespace n ON c.relnamespace = n.oid
              WHERE n.nspname = 'gold'
                AND c.relname = 'price_monthly'
                AND a.attname = 'source_family'
                AND NOT a.attisdropped
          );
        """
    )
    result = bind.execute(query).scalar()
    return bool(result)


def get_gold_sql_dir() -> Path:
    """Locate the Gold SQL definitions directory."""
    pkg_dir = Path(__file__).resolve().parent / "sql"
    if pkg_dir.exists():
        return pkg_dir
    alt_dir = Path("/app/src/ketrika/gold/sql")
    if alt_dir.exists():
        return alt_dir
    raise FileNotFoundError("Could not locate Gold SQL directory")


def check_and_upgrade_historical_gold_definitions(
    bind: Connection | Session,
    target_cutoff_index: int = 12,
) -> bool:
    """Pre-control and automatically align historical Gold definitions before migrations (BL-019).

    If outdated definitions (such as price_monthly without source_family) are detected,
    re-installs the current view definitions up to target_cutoff_index in topological order WITH NO DATA.
    Returns True if an automated upgrade was executed, False if the schema was already compliant.
    """
    if not is_gold_definition_outdated(bind):
        logger.debug("Gold view definitions are already compliant with current schema contracts.")
        return False

    logger.warning(
        "Outdated Gold definitions detected (BL-019: price_monthly missing source_family). "
        "Executing automated pre-control repair in topological order WITH NO DATA."
    )

    sql_dir = get_gold_sql_dir()
    sql_files = sorted(sql_dir.glob("*.sql"))

    for f in sql_files:
        try:
            index = int(f.name.split("_")[0])
        except (ValueError, IndexError):
            continue

        if index <= target_cutoff_index:
            sql_content = f.read_text(encoding="utf-8")
            if "WITH NO DATA;" not in sql_content:
                raise RuntimeError(f"Gold SQL definition {f.name} requires unpopulated WITH NO DATA")
            logger.info("Auto-upgrading historical Gold view definition: %s", f.name)
            bind.execute(text(sql_content))

    logger.info("Successfully aligned historical Gold definitions up to index %03d.", target_cutoff_index)
    return True
