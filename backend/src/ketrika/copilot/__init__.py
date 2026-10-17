"""Ketrika Copilot Analyst module (SPECS §21, R6.1, ADR-095)."""

from ketrika.copilot.agent import CopilotAgent, generate_sql_from_question
from ketrika.copilot.executor import QueryResult, execute_copilot_query
from ketrika.copilot.schema import GOLD_VIEWS_CATALOG, generate_schema_catalog_markdown
from ketrika.copilot.sql_guard import (
    KNOWN_GOLD_VIEWS,
    MAX_ROW_LIMIT,
    SqlGuardError,
    validate_and_sanitize_sql,
)
from ketrika.copilot.tools import (
    AnalyticalToolCatalog,
    CropCalendarOutput,
    MarketCoverageOutput,
    MarketFactsOutput,
    ParameterValidationError,
    PriceSeriesOutput,
    QualifiedForecastOutput,
    SourceProvenanceOutput,
)
from ketrika.copilot.writer import (
    assemble_final_response,
    build_cell_placeholders,
    render_deterministic_fallback,
)

__all__ = [
    "GOLD_VIEWS_CATALOG",
    "KNOWN_GOLD_VIEWS",
    "MAX_ROW_LIMIT",
    "AnalyticalToolCatalog",
    "CopilotAgent",
    "CropCalendarOutput",
    "MarketCoverageOutput",
    "MarketFactsOutput",
    "ParameterValidationError",
    "PriceSeriesOutput",
    "QualifiedForecastOutput",
    "QueryResult",
    "SourceProvenanceOutput",
    "SqlGuardError",
    "assemble_final_response",
    "build_cell_placeholders",
    "execute_copilot_query",
    "generate_schema_catalog_markdown",
    "generate_sql_from_question",
    "render_deterministic_fallback",
    "validate_and_sanitize_sql",
]
