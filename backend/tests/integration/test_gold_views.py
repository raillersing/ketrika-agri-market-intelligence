"""Integration tests for Gold materialized views and priority arbitration (SPECS §15, §16, T5.1)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from ketrika.core.db import check_db_connection
from ketrika.core.settings import get_settings
from ketrika.gold.refresh import refresh_gold_views
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.e2e_data.synthetic_gold_dataset import (
    PRODUCT_RICE_ID,
    seed_synthetic_gold_data,
)


@pytest.fixture
def db_session():
    """Create a database session connected to PostgreSQL."""
    if not check_db_connection():
        pytest.skip("Database is not reachable (skipping integration tests)")
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session = Session(engine)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.integration
def test_gold_views_sql_e2e_synthetic(db_session: Session):
    """Verify all 12 Gold materialized views compute hand-calculated analytical metrics on synthetic dataset."""
    # 1. Clean slate
    wipe_silver_gold_tables(db_session)
    db_session.commit()

    # 2. Seed clean deterministic synthetic dataset
    counts = seed_synthetic_gold_data(db_session)
    db_session.commit()
    assert counts["price"] >= 18
    assert counts["stock"] == 3
    assert counts["trade"] == 2
    assert counts["production"] == 1
    assert counts["weather"] == 8
    assert counts["cpi"] == 2
    assert counts["forecast"] == 2

    # 3. Refresh Gold materialized views in topological order
    refresh_result = refresh_gold_views(db_session)
    db_session.commit()
    assert refresh_result["count"] == 12
    assert len(refresh_result["errors"]) == 0

    # 4. Verify View 1: gold.price_obs_current
    v1_count = db_session.execute(text("SELECT count(*) FROM gold.price_obs_current;")).scalar()
    assert v1_count == counts["price"]

    # 5. Verify View 2: gold.price_monthly
    v2_rows = db_session.execute(
        text(
            """
            SELECT source_id, month, median_price, min_price, max_price, n_obs, imputed_share, has_observed
            FROM gold.price_monthly
            WHERE product_id = :pid AND month = '2024-01-01'
            """
        ),
        {"pid": PRODUCT_RICE_ID},
    ).fetchall()
    assert len(v2_rows) == 1
    assert v2_rows[0][0] == "miasa_odr"
    assert float(v2_rows[0][2]) == 3000.0  # median
    assert float(v2_rows[0][6]) == 0.0  # imputed_share
    assert v2_rows[0][7] is True  # has_observed

    # 6. Verify View 3: gold.price_monthly_best (verified further in dedicated priority test)
    v3_rows = db_session.execute(
        text("SELECT count(*) FROM gold.price_monthly_best WHERE product_id = :pid;"),
        {"pid": PRODUCT_RICE_ID},
    ).scalar()
    assert v3_rows == 15  # 13 historical months + 2024-02 + 2024-03

    # 7. Verify View 4: gold.price_changes (hand-calculated chg_1m, chg_3m, chg_12m)
    v4_row = db_session.execute(
        text(
            """
            SELECT median_price, chg_1m, chg_3m, chg_12m, vol_12, z_score_robust
            FROM gold.price_changes
            WHERE product_id = :pid AND month = '2024-01-01'
            """
        ),
        {"pid": PRODUCT_RICE_ID},
    ).fetchone()
    assert v4_row is not None
    assert float(v4_row[0]) == 3000.0
    # Month t (2024-01): 3000.0 vs Month t-1 (2023-12): 2950.0 -> (3000/2950) - 1 = +0.0169
    assert float(v4_row[1]) == pytest.approx(0.0169, abs=0.001)
    # Month t vs Month t-3 (2023-10): 2900.0 -> (3000/2900) - 1 = +0.0345
    assert float(v4_row[2]) == pytest.approx(0.0345, abs=0.001)
    # Month t vs Month t-12 (2023-01): 2500.0 -> (3000/2500) - 1 = +0.2000 (exact +20%)
    assert float(v4_row[3]) == pytest.approx(0.2000, abs=0.001)
    # Robust volatility over 12 months > 0
    assert float(v4_row[4]) > 0.0

    # 8. Verify View 5: gold.stock_latest
    v5_row = db_session.execute(
        text(
            """
            SELECT stock_status, coverage_days, trend
            FROM gold.stock_latest
            WHERE product_id = :pid;
            """
        ),
        {"pid": PRODUCT_RICE_ID},
    ).fetchone()
    assert v5_row is not None
    assert v5_row[0] == "sufficient"
    assert float(v5_row[1]) == 25.0
    assert v5_row[2] == "improving"

    # 9. Verify View 6: gold.trade_monthly
    v6_rows = db_session.execute(
        text(
            """
            SELECT flow, weight_tonnes, value_mga, value_usd
            FROM gold.trade_monthly
            WHERE product_id = :pid AND month = '2024-01-01'
            ORDER BY flow;
            """
        ),
        {"pid": PRODUCT_RICE_ID},
    ).fetchall()
    assert len(v6_rows) == 2
    # export: 1000.0 t, 3.5B MGA
    assert v6_rows[0][0] == "export"
    assert float(v6_rows[0][1]) == 1000.0
    assert float(v6_rows[0][2]) == 3500000000.0
    # import: 10000.0 t, 30.0B MGA
    assert v6_rows[1][0] == "import"
    assert float(v6_rows[1][1]) == 10000.0
    assert float(v6_rows[1][2]) == 30000000000.0

    # 10. Verify View 7: gold.import_dependency
    # Hand-calculated IDR:
    # Production = 50,000 t, Imports = 10,000 t, Exports = 1,000 t
    # Net availability = 50,000 + 10,000 - 1,000 = 59,000 t
    # IDR = 10,000 / 59,000 = 0.1695 (16.95%)
    v7_row = db_session.execute(
        text(
            """
            SELECT year, production_tonnes, import_tonnes, export_tonnes, net_availability_tonnes, import_dependency_ratio
            FROM gold.import_dependency
            WHERE product_id = :pid AND year = 2024;
            """
        ),
        {"pid": PRODUCT_RICE_ID},
    ).fetchone()
    assert v7_row is not None
    assert float(v7_row[1]) == 50000.0
    assert float(v7_row[2]) == 10000.0
    assert float(v7_row[3]) == 1000.0
    assert float(v7_row[4]) == 59000.0
    assert float(v7_row[5]) == pytest.approx(0.1695, abs=0.0005)

    # 11. Verify View 8: gold.weather_monthly
    v8_rows = db_session.execute(
        text(
            """
            SELECT month, precip_total_mm, t2m_max_avg_c, t2m_min_avg_c, rh2m_avg_pct
            FROM gold.weather_monthly
            ORDER BY month;
            """
        )
    ).fetchall()
    assert len(v8_rows) == 2
    assert float(v8_rows[0][1]) == 120.0  # precip jan
    assert float(v8_rows[0][2]) == 28.5  # max temp jan
    assert float(v8_rows[1][1]) == 150.0  # precip feb

    # 12. Verify View 9: gold.cpi_food
    v9_rows = db_session.execute(
        text(
            """
            SELECT month, index_value, chg_1m
            FROM gold.cpi_food
            ORDER BY month;
            """
        )
    ).fetchall()
    assert len(v9_rows) == 2
    assert float(v9_rows[0][1]) == 100.0
    assert v9_rows[0][2] is None  # first month no prev
    assert float(v9_rows[1][1]) == 105.0
    assert float(v9_rows[1][2]) == pytest.approx(0.0500, abs=0.0001)  # +5%

    # 13. Verify View 10: gold.market_health
    v10_row = db_session.execute(
        text(
            """
            SELECT score_stability, score_affordability, score_availability, score_climate, coverage, market_health_score
            FROM gold.market_health
            WHERE product_id = :pid AND month = '2024-01-01';
            """
        ),
        {"pid": PRODUCT_RICE_ID},
    ).fetchone()
    assert v10_row is not None
    # Availability from stocks, stability and affordability from prices, climate from weather
    assert float(v10_row[4]) >= 0.50  # coverage
    assert v10_row[5] is not None
    assert 0.0 <= float(v10_row[5]) <= 100.0  # composite score

    # 14. Verify View 11: gold.source_health
    v11_row = db_session.execute(
        text(
            """
            SELECT source_id, source_status, latest_run_status, open_review_items
            FROM gold.source_health
            WHERE source_id = 'miasa_odr';
            """
        )
    ).fetchone()
    assert v11_row is not None
    assert v11_row[0] == "miasa_odr"
    assert v11_row[1] == "active"
    assert v11_row[2] == "success"
    assert v11_row[3] == 1  # 1 open review item

    # 15. Verify View 12: gold.forecast_latest
    v12_rows = db_session.execute(
        text(
            """
            SELECT horizon, target_period, p10, p50, p90, model_name
            FROM gold.forecast_latest
            WHERE product_id = :pid
            ORDER BY horizon;
            """
        ),
        {"pid": PRODUCT_RICE_ID},
    ).fetchall()
    assert len(v12_rows) == 2
    assert v12_rows[0][0] == 1
    assert float(v12_rows[0][2]) == 3200.0  # p10
    assert float(v12_rows[0][3]) == 3350.0  # p50
    assert float(v12_rows[0][4]) == 3500.0  # p90
    assert v12_rows[0][5] == "AutoARIMA"


@pytest.mark.integration
def test_price_monthly_best_priority_order(db_session: Session):
    """Dedicated acceptance test: gold.price_monthly_best strictly respects source priority order.

    Rule: P0 observed > P1 observed > P1 imputed > P2... (SPECS §15, MVP_EXECUTION_PLAN T5.1).
    """
    # 1. Clean slate and seed
    wipe_silver_gold_tables(db_session)
    db_session.commit()
    seed_synthetic_gold_data(db_session)
    db_session.commit()
    refresh_gold_views(db_session)
    db_session.commit()

    # 2. Test Case A: Month 2024-02-01
    # Concurrent sources:
    # - ODR: Priority P0, observed, price = 3100.0
    # - WFP: Priority P1, observed, price = 3200.0
    # - WB RTFP: Priority P1, imputed, price = 3150.0
    # Must choose: ODR (P0 observed)!
    row_feb = db_session.execute(
        text(
            """
            SELECT chosen_source_id, priority, observed_or_imputed, median_price
            FROM gold.price_monthly_best
            WHERE product_id = :pid AND month = '2024-02-01';
            """
        ),
        {"pid": PRODUCT_RICE_ID},
    ).fetchone()
    assert row_feb is not None
    assert row_feb[0] == "miasa_odr", f"Expected miasa_odr (P0 observed), got {row_feb[0]}"
    assert row_feb[1] == "P0"
    assert row_feb[2] == "observed"
    assert float(row_feb[3]) == 3100.0

    # 3. Test Case B: Month 2024-03-01
    # Concurrent sources:
    # - WFP: Priority P1, observed, price = 3300.0
    # - WB RTFP: Priority P1, imputed, price = 3250.0
    # Must choose: WFP (P1 observed > P1 imputed)!
    row_mar = db_session.execute(
        text(
            """
            SELECT chosen_source_id, priority, observed_or_imputed, median_price
            FROM gold.price_monthly_best
            WHERE product_id = :pid AND month = '2024-03-01';
            """
        ),
        {"pid": PRODUCT_RICE_ID},
    ).fetchone()
    assert row_mar is not None
    assert row_mar[0] == "wfp_hdx_mdg", f"Expected wfp_hdx_mdg (P1 observed), got {row_mar[0]}"
    assert row_mar[1] == "P1"
    assert row_mar[2] == "observed"
    assert float(row_mar[3]) == 3300.0
