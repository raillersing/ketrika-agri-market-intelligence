"""SQL Guard: Strict AST validation and sanitization for Copilot queries (SPECS §21, R6.1, ADR-095).

Normative security requirements:
- Single SQL statement.
- Pure SELECT in the 'gold' analytical schema only.
- Strict prevention of data-modifying CTEs (WITH ... DELETE/UPDATE/INSERT).
- Strict prevention of system and network/exfiltration functions (pg_*, http_*, dblink*, etc.).
- Enforced LIMIT <= 500.
- Safe explanation on rejection without leakage of internal database or credentials metadata.
"""

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
    "market_coverage",
    "economic_dashboard",
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
    "http_",
    "net_",
    "query_to_",
    "table_to_",
    "schema_to_",
    "crosstab",
    "system",
    "sh",
    "exec",
    "cmd",
)

FORBIDDEN_SCHEMA_PATTERNS: tuple[str, ...] = (
    "auth",
    "obs",
    "bronze",
    "silver",
    "information_schema",
    "pg_catalog",
    "public",
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
    3. Common Table Expressions (CTEs) must be pure SELECT queries (no data-modifying CTEs).
    4. Every table referenced MUST belong exclusively to schema 'gold' and be a recognized Gold view.
    5. No dangerous or exfiltration functions (pg_*, http_*, dblink, lo_*, copy, etc.).
    6. No SELECT ... INTO statement.
    7. Injects or clamps LIMIT <= 500.

    Returns the sanitized, formatted SQL query string.
    Raises SqlGuardError on any violation.
    """
    cleaned_input = sql_query.strip()
    if not cleaned_input:
        raise SqlGuardError("Requête SQL vide.", "EMPTY_QUERY")

    # Reject obvious injection attempt keywords in comments or raw text
    lower_raw = cleaned_input.lower()
    for forbidden_sch in FORBIDDEN_SCHEMA_PATTERNS:
        if re.search(rf"\b{forbidden_sch}\.", lower_raw):
            raise SqlGuardError(
                f"Accès refusé au schéma '{forbidden_sch}'. Seul le schéma 'gold' est autorisé.",
                "FORBIDDEN_SCHEMA",
            )

    if re.search(r"\b(pg_read_file|pg_shadow|pg_authid|pg_ls_dir)\b", lower_raw):
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

    # Forbid SELECT INTO
    if stmt.args.get("into") is not None:
        raise SqlGuardError("La clause SELECT INTO est strictement interdite.", "INTO_NOT_ALLOWED")

    # Forbid any data-modifying AST nodes anywhere in the query (including within subqueries or CTEs)
    modifying_nodes = list(
        stmt.find_all(
            exp.Insert,
            exp.Update,
            exp.Delete,
            exp.Drop,
            exp.Create,
            exp.Alter,
            exp.Command,
        )
    )
    if modifying_nodes:
        raise SqlGuardError(
            "Instructions d'écriture ou de modification de données interdites dans la requête.",
            "MODIFICATION_NOT_ALLOWED",
        )

    # Verify CTEs: all CTE bodies must be pure Select
    for cte in stmt.find_all(exp.CTE):
        cte_query = cte.this
        if not isinstance(cte_query, exp.Select):
            raise SqlGuardError(
                "Toutes les expressions CTE (WITH) doivent obligatoirement être des SELECT en lecture seule.",
                "CTE_NOT_SELECT",
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

    ctes = {cte.alias_or_name.lower() for cte in stmt.find_all(exp.CTE) if cte.alias_or_name}

    for tbl in tables:
        schema = (tbl.db or "").lower().strip()
        table_name = (tbl.name or "").lower().strip()

        # Handle CTE references
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
