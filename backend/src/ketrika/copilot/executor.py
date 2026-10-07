"""Secure database query executor using copilot_ro credentials (SPECS §8, §21, T10.1)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import create_engine, make_url, text
from sqlalchemy.engine import URL, Engine

from ketrika.copilot.sql_guard import validate_and_sanitize_sql
from ketrika.core.settings import Settings, get_settings

logger = logging.getLogger("ketrika.copilot.executor")


@dataclass
class QueryResult:
    """Execution output from a secured copilot query."""

    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    citations: list[dict[str, Any]] = field(default_factory=list)
    value_kinds: list[str] = field(default_factory=list)


_copilot_engine: Engine | None = None


def get_copilot_engine(settings: Settings | None = None) -> Engine:
    """Obtain or initialize the dedicated read-only engine for copilot_ro."""
    global _copilot_engine
    if _copilot_engine is not None:
        return _copilot_engine

    cfg = settings or get_settings()
    base_url = make_url(cfg.database_url)

    ro_url = URL.create(
        drivername=base_url.drivername,
        username="copilot_ro",
        password=cfg.copilot_db_password,
        host=base_url.host,
        port=base_url.port,
        database=base_url.database,
    )

    _copilot_engine = create_engine(
        ro_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"options": "-c statement_timeout=5000"},
    )
    return _copilot_engine


def execute_copilot_query(
    sql_query: str,
    settings: Settings | None = None,
) -> QueryResult:
    """Validate, sanitize and execute a query under copilot_ro read-only role.

    Guarantees:
    - Passes AST validation by SqlGuard (Gold schema only, SELECT only, LIMIT <= 500).
    - Statement timeout enforced to 5 seconds.
    - Automatic extraction of provenance citations and value kinds.
    """
    sanitized_sql = validate_and_sanitize_sql(sql_query)
    engine = get_copilot_engine(settings)

    with engine.connect() as conn:
        result = conn.execute(text(sanitized_sql))
        columns = list(result.keys()) if result.returns_rows else []
        raw_rows = result.fetchall() if result.returns_rows else []

        rows: list[dict[str, Any]] = []
        for r in raw_rows:
            row_dict: dict[str, Any] = {}
            for idx, col in enumerate(columns):
                val = r[idx]
                # Convert dates/decimals to JSON serializable objects if needed
                row_dict[col] = str(val) if hasattr(val, "isoformat") else val
            rows.append(row_dict)

    # Extract citations from results
    citations: list[dict[str, Any]] = []
    seen_citations: set[str] = set()

    # Extract value kinds (observed, imputed, forecast, composite)
    value_kinds: list[str] = []
    seen_kinds: set[str] = set()

    for row in rows:
        # Check source citations
        for src_key in ("chosen_source_id", "source_id"):
            if src_key in row and row[src_key]:
                s_id = str(row[src_key])
                if s_id not in seen_citations:
                    seen_citations.add(s_id)
                    citations.append({"source_id": s_id, "kind": "official_source"})

        # Check observation IDs
        if "observation_id" in row and row["observation_id"]:
            obs_id = str(row["observation_id"])
            if obs_id not in seen_citations:
                seen_citations.add(obs_id)
                citations.append({"observation_id": obs_id, "kind": "gold_observation"})

        # Check value kinds
        if "observed_or_imputed" in row and row["observed_or_imputed"]:
            kind = str(row["observed_or_imputed"]).lower()
            if kind not in seen_kinds:
                seen_kinds.add(kind)
                value_kinds.append(kind)

        if "model_name" in row and row["model_name"]:
            if "forecast" not in seen_kinds:
                seen_kinds.add("forecast")
                value_kinds.append("forecast")

        if "market_health_score" in row and row["market_health_score"]:
            if "composite" not in seen_kinds:
                seen_kinds.add("composite")
                value_kinds.append("composite")

    if not value_kinds:
        value_kinds.append("observed")

    return QueryResult(
        sql=sanitized_sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        citations=citations,
        value_kinds=value_kinds,
    )
