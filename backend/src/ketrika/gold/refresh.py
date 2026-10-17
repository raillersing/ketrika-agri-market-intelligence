"""Gold materialized views creation and refresh engine (SPECS §15, MVP_EXECUTION_PLAN T5.1)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ketrika.core.bronze import BronzeStore
from ketrika.core.provenance import ArtifactReader
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.schema_contracts import SchemaContractRegistry
from ketrika.gold.dq import (
    GoldDqRejected,
    check_blocking_dq_gate,
    get_publication_denominators,
)
from ketrika.gold.provenance_gate import require_gold_provenance, tables_for_views
from ketrika.gold.schema_gate import require_gold_structure

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
    "market_coverage",
    "economic_dashboard",
]

GOLD_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "price_monthly": ("price_obs_current",),
    "price_monthly_best": ("price_monthly",),
    "price_changes": ("price_monthly_best",),
    "market_health": ("price_changes", "stock_latest", "weather_monthly"),
    "market_coverage": ("price_monthly",),
}


def publication_views(requested: list[str]) -> list[str]:
    """Include every consumed Gold cache; no stale dependency certification."""
    tables_for_views(requested)
    selected = set(requested)
    pending = list(requested)
    while pending:
        for dependency in GOLD_DEPENDENCIES.get(pending.pop(), ()):
            if dependency not in selected:
                selected.add(dependency)
                pending.append(dependency)
    return [view for view in ORDERED_GOLD_VIEWS if view in selected]


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
    """Create unpopulated views only; never implicitly publish source values."""
    sql_dir = get_sql_dir()
    sql_files = sorted(sql_dir.glob("*.sql"))
    expected_files = [f"{index:03d}_{view}.sql" for index, view in enumerate(ORDERED_GOLD_VIEWS, 1)]
    if [file.name for file in sql_files] != expected_files:
        raise ValueError("gold_schema_definition_missing")
    definitions = [file.read_text(encoding="utf-8") for file in sql_files]
    if any("WITH NO DATA;" not in definition for definition in definitions):
        raise ValueError("gold_schema_requires_unpopulated_views")
    logger.info("Initializing %d Gold materialized views from %s...", len(sql_files), sql_dir)

    executed = 0
    for f, sql_content in zip(sql_files, definitions, strict=True):
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
    logger.info("Created %d unpopulated Gold views; no source-cell certification.", executed)
    return {"views_initialized": executed, "views_populated": 0}


def refresh_gold_views(
    session: Session,
    concurrently: bool = False,
    views: list[str] | None = None,
    *,
    reader: ArtifactReader | None = None,
    schema_registry: SchemaContractRegistry | None = None,
) -> dict[str, Any]:
    """Fresh cell check and atomic publication; no model/conversion qualification."""
    requested = ORDERED_GOLD_VIEWS if views is None else views
    target_views = publication_views(requested)
    logger.info("Refreshing %d Gold materialized views...", len(target_views))

    refreshed: list[str] = []
    try:
        for view_name in target_views:
            exists = session.execute(
                text("SELECT 1 FROM pg_matviews WHERE schemaname = 'gold' AND matviewname = :mv"),
                {"mv": view_name},
            ).scalar()
            if not exists:
                raise ValueError("gold_view_missing")
        proof_reader = reader if reader is not None else BronzeProofReader(BronzeStore())
        check = require_gold_provenance(session, proof_reader, target_views)
        structure = require_gold_structure(session, proof_reader, check, schema_registry)
        if check.state != "empty":
            check_blocking_dq_gate(session)
        denominators = get_publication_denominators(session)
        with session.begin_nested():
            for view_name in target_views:
                if concurrently:
                    try:
                        with session.begin_nested():
                            session.execute(
                                text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY gold.{view_name};")
                            )
                    except SQLAlchemyError:
                        session.execute(text(f"REFRESH MATERIALIZED VIEW gold.{view_name};"))
                else:
                    session.execute(text(f"REFRESH MATERIALIZED VIEW gold.{view_name};"))
                refreshed.append(view_name)
    except (GoldDqRejected, ValueError):
        raise
    except SQLAlchemyError:
        raise ValueError("gold_publication_failed") from None

    session.flush()
    logger.info("Successfully refreshed %d Gold materialized views.", len(refreshed))
    return {
        "views_refreshed": refreshed,
        "errors": {},
        "count": len(refreshed),
        "provenance_state": check.state,
        "source_cell_dq_id": str(check.receipt.dq_id) if check.receipt else None,
        "provenance_scope": "source_cells_not_authenticity_conversions_or_model",
        "source_observations_total": check.receipt.report.total if check.receipt else 0,
        "source_observations_valid": check.receipt.report.valid if check.receipt else 0,
        "source_cell_rate": str(check.receipt.report.rate) if check.receipt else None,
        "structure_state": structure.state,
        "structure_dq_ids": [str(receipt.dq_id) for receipt in structure.receipts],
        "structure_artifacts_total": structure.total,
        "structure_artifacts_valid": structure.valid,
        "structure_scope": "publication_candidate_artifacts_not_authenticity_or_model",
        "denominators": {
            "candidate_files": denominators.candidate_files,
            "parsed_files": denominators.parsed_files,
            "failed_files": denominators.failed_files,
            "review_files": denominators.review_files,
            "pending_files": denominators.pending_files,
            "candidate_rows": denominators.candidate_rows,
            "accepted_rows": denominators.accepted_rows,
            "rejected_rows": denominators.rejected_rows,
            "review_rows": denominators.review_rows,
        },
    }
