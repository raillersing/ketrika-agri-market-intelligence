"""SQL Guard: Strict AST validation and sanitization for Copilot queries (SPECS §21, T10.1)."""

from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

KNOWN_GOLD_VIEWS: set[str] = {
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
}

FORBIDDEN_FUNCTION_PREFIXES: tuple[str, ...] = (
    "pg_",
    "dblink",
    "lo_",
    "copy",
    "current_setting",
    "set_config",
    "inet_",
    "version",
)

MAX_ROW_LIMIT: int = 500


class SqlGuardError(ValueError):
    """Exception raised when an SQL query violates the Copilot security policy."""

    def __init__(self, message: str, violation_code: str = "FORBIDDEN_QUERY") -> None:
        super().__init__(message)
        self.violation_code = violation_code


def validate_and_sanitize_sql(sql_query: str) -> str:
    """Validate that an SQL query strictly conforms to the read-only Gold security policy.

    Rules enforced via sqlglot AST:
    1. Exactly one SQL statement.
    2. Must be a pure SELECT query (no INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, etc.).
    3. Every table referenced MUST belong exclusively to schema 'gold' and be a recognized Gold view.
    4. No dangerous functions (pg_*, dblink, lo_*, copy, etc.).
    5. Injects or clamps LIMIT <= 500.

    Returns the sanitized, formatted SQL query string.
    Raises SqlGuardError on any violation.
    """
    cleaned_input = sql_query.strip()
    if not cleaned_input:
        raise SqlGuardError("Requête SQL vide.", "EMPTY_QUERY")

    # Reject obvious injection attempt keywords in comments or raw text
    lower_raw = cleaned_input.lower()
    if re.search(r"\b(auth\.user_account|auth\.api_key|pg_read_file|pg_shadow)\b", lower_raw):
        raise SqlGuardError(
            "Accès aux schémas système ou sensibles strictement interdit.", "ACCESS_DENIED"
        )

    try:
        parsed_statements = sqlglot.parse(cleaned_input, read="postgres")
    except Exception as exc:
        raise SqlGuardError(f"Syntaxe SQL invalide : {exc}", "SYNTAX_ERROR") from exc

    if not parsed_statements:
        raise SqlGuardError("Aucune instruction SQL détectée.", "EMPTY_QUERY")

    if len(parsed_statements) > 1:
        raise SqlGuardError(
            f"Les requêtes multiples sont interdites ({len(parsed_statements)} instructions détectées).",
            "MULTIPLE_STATEMENTS",
        )

    stmt = parsed_statements[0]
    if stmt is None or not isinstance(stmt, exp.Select):
        raise SqlGuardError(
            "Seules les instructions SELECT en lecture seule sont autorisées.",
            "STATEMENT_NOT_SELECT",
        )

    # Check for forbidden functions
    for func in stmt.find_all(exp.Func, exp.Anonymous):
        func_name = (func.name or func.sql()).lower().strip()
        for prefix in FORBIDDEN_FUNCTION_PREFIXES:
            if func_name.startswith(prefix) or f".{prefix}" in func_name:
                raise SqlGuardError(
                    f"Appel à la fonction système interdite '{func_name}'.",
                    "FORBIDDEN_FUNCTION",
                )

    # Validate tables and schemas
    tables = list(stmt.find_all(exp.Table))
    if not tables:
        raise SqlGuardError(
            "La requête doit interroger au moins une vue du schéma gold.", "NO_TABLES"
        )

    for tbl in tables:
        schema = (tbl.db or "").lower().strip()
        table_name = (tbl.name or "").lower().strip()

        # Handle CTE (Common Table Expressions) references: CTEs don't have a db schema
        ctes = {cte.alias_or_name.lower() for cte in stmt.find_all(exp.CTE) if cte.alias_or_name}
        if table_name in ctes and not schema:
            continue

        if schema and schema != "gold":
            raise SqlGuardError(
                f"Accès refusé au schéma '{schema}'. Seul le schéma 'gold' est autorisé.",
                "FORBIDDEN_SCHEMA",
            )

        if table_name not in KNOWN_GOLD_VIEWS:
            raise SqlGuardError(
                f"La vue ou table '{table_name}' n'appartient pas au catalogue Gold autorisé.",
                "UNKNOWN_VIEW",
            )

        # Enforce explicit 'gold' schema qualification on AST
        if not tbl.db:
            tbl.set("db", exp.to_identifier("gold"))

    # Limit check: enforce LIMIT <= 500
    limit_node = stmt.args.get("limit")
    if limit_node is None:
        stmt = stmt.limit(MAX_ROW_LIMIT)
    else:
        expr = limit_node.expression
        try:
            val = int(expr.this) if hasattr(expr, "this") else int(expr.sql())
            if val > MAX_ROW_LIMIT:
                stmt.args["limit"] = exp.Limit(expression=exp.Literal.number(MAX_ROW_LIMIT))
        except Exception:
            stmt.args["limit"] = exp.Limit(expression=exp.Literal.number(MAX_ROW_LIMIT))

    sanitized_sql = stmt.sql(dialect="postgres")
    return sanitized_sql
