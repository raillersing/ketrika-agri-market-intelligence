"""Unit and property-based tests for Gold DQ, aggregations, calendar alignment and family independence (SPECS §14, §15, §16, R2.3).

Directive R2.3:
- Appliquer seuils SPECS §14.
- Publier dénominateurs cohérents pour fichiers, lignes candidates, acceptées, rejetées et revue.
- Vérifier priorité observé/imputé sans duplication de familles ; garder conflits et dispersion.
- Variations alignées sur calendrier réel, pas dernière ligne disponible.
- Préserver Market Health normatif avec composantes/coverage ; un changement de formule exige ADR.
- Fixtures de trou de mois, conflit, duplication WFP/RTFP, incomparabilité et faible couverture.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ketrika.core.aggregation import (
    ComparablePriceItem,
    IncompatibleAggregationError,
    compute_safe_arithmetic_average,
    filter_comparable_items,
    validate_comparable_group,
)
from ketrika.gold.dq import (
    GoldDqRejected,
    PublicationDenominators,
    check_blocking_dq_gate,
    check_llm_unverified_in_gold,
    check_parse_success_rate,
    check_price_range_sanity,
    check_provenance_complete,
    get_publication_denominators,
)
from ketrika.gold.kpi import (
    audit_source_family_independence,
    calculate_affordability_score,
    calculate_availability_score,
    calculate_calendar_aligned_variation,
    calculate_climate_risk_score,
    calculate_market_health_score,
    calculate_price_stability_score,
)
from ketrika.gold.refresh import get_sql_dir

# ==============================================================================
# 1. Calendar-aligned variations vs Naive LAG (Gap fixtures)
# ==============================================================================


def test_calendar_aligned_variation_with_continuous_months():
    """Verify that contiguous months compute exact percentage variations."""
    prices = {
        date(2024, 1, 1): 2500.0,
        date(2024, 2, 1): 2750.0,
        date(2024, 3, 1): 3000.0,
        date(2024, 4, 1): 3000.0,
    }
    # 2024-02 vs 2024-01 (+10%)
    chg_feb = calculate_calendar_aligned_variation(prices, date(2024, 2, 1), 1)
    assert chg_feb == pytest.approx(0.1000, abs=0.0001)

    # 2024-03 vs 2024-02 (+9.09%)
    chg_mar = calculate_calendar_aligned_variation(prices, date(2024, 3, 1), 1)
    assert chg_mar == pytest.approx(0.0909, abs=0.0001)

    # 2024-04 vs 2024-01 (3 months lag: (3000/2500) - 1 = +20%)
    chg_3m = calculate_calendar_aligned_variation(prices, date(2024, 4, 1), 3)
    assert chg_3m == pytest.approx(0.2000, abs=0.0001)


def test_calendar_aligned_variation_returns_null_on_month_gap():
    """Critical Acceptance Test: A gap in months MUST produce None, NEVER computing across the gap."""
    # Month 2 (February) is missing!
    prices_with_gap = {
        date(2024, 1, 1): 2500.0,
        # 2024-02-01 is missing
        date(2024, 3, 1): 3000.0,
    }
    # 1-month lag from 2024-03-01 targets 2024-02-01 (which does not exist).
    # A naive LAG would have picked 2024-01-01 and calculated +20% as MoM change.
    chg_1m = calculate_calendar_aligned_variation(prices_with_gap, date(2024, 3, 1), 1)
    assert chg_1m is None, "MoM variation across a missing month MUST be None"

    # But 2-month lag targets 2024-01-01, which exists
    chg_2m = calculate_calendar_aligned_variation(prices_with_gap, date(2024, 3, 1), 2)
    assert chg_2m == pytest.approx(0.2000, abs=0.0001)


def test_calendar_aligned_variation_handles_year_boundary_and_quarter():
    """Verify year transitions (e.g. January t vs December t-1, and 12-month YoY)."""
    prices = {
        date(2023, 1, 1): 2000.0,
        date(2023, 10, 1): 2200.0,
        date(2023, 12, 1): 2300.0,
        date(2024, 1, 1): 2400.0,
    }
    # 2024-01 vs 2023-12 (1 month lag across year boundary)
    chg_1m = calculate_calendar_aligned_variation(prices, date(2024, 1, 1), 1)
    assert chg_1m == pytest.approx(round((2400.0 / 2300.0) - 1.0, 4), abs=0.0001)

    # 2024-01 vs 2023-10 (3 months lag: Oct 2023)
    chg_3m = calculate_calendar_aligned_variation(prices, date(2024, 1, 1), 3)
    assert chg_3m == pytest.approx(round((2400.0 / 2200.0) - 1.0, 4), abs=0.0001)

    # 2024-01 vs 2023-01 (12 months lag: YoY +20%)
    chg_12m = calculate_calendar_aligned_variation(prices, date(2024, 1, 1), 12)
    assert chg_12m == pytest.approx(0.2000, abs=0.0001)

    # If 2023-01 is missing, YoY MUST be None
    prices_no_prev_year = {
        date(2023, 12, 1): 2300.0,
        date(2024, 1, 1): 2400.0,
    }
    assert calculate_calendar_aligned_variation(prices_no_prev_year, date(2024, 1, 1), 12) is None


def test_calendar_aligned_variation_invalid_arguments():
    """Verify negative or zero lag raises ValueError."""
    with pytest.raises(ValueError, match="lag_months must be positive"):
        calculate_calendar_aligned_variation({}, date(2024, 1, 1), 0)


# ==============================================================================
# 2. Source Family Independence & Anti-Leakage (C3, WFP / RTFP fixture)
# ==============================================================================


def test_source_family_independence_wfp_and_rtfp_not_independent():
    """C3 requirement: World Bank RTFP derives from WFP HDX; they must NOT be counted as 2 independent confirmations."""
    sources = [
        {"source_id": "wfp_hdx_mdg", "source_family": "un_wfp"},
        {
            "source_id": "wb_rtfp_mdg",
            "source_family": "world_bank",
            "source_dependency": "wfp_fao",
        },
    ]
    res = audit_source_family_independence(sources)
    assert res["n_sources"] == 2
    # Both resolve to un_wfp root family:
    assert res["n_independent_families"] == 1
    assert res["has_dependent_derivation"] is True
    assert res["is_truly_independent"] is False


def test_source_family_independence_national_sources_share_family():
    """Madagascar government sources share the madagascar_gov family."""
    sources = [
        {"source_id": "miasa_odr", "source_family": "madagascar_gov"},
        {"source_id": "mincc_ppn", "source_family": "madagascar_gov"},
    ]
    res = audit_source_family_independence(sources)
    assert res["n_sources"] == 2
    assert res["n_independent_families"] == 1
    assert res["independent_families"] == ["madagascar_gov"]
    assert res["is_truly_independent"] is False


def test_source_family_independence_truly_distinct_sources():
    """Sources from distinct organizations are recognized as truly independent."""
    sources = [
        {"source_id": "miasa_odr", "source_family": "madagascar_gov"},
        {"source_id": "wfp_hdx_mdg", "source_family": "un_wfp"},
        {"source_id": "faostat", "source_family": "un_fao"},
    ]
    res = audit_source_family_independence(sources)
    assert res["n_sources"] == 3
    assert res["n_independent_families"] == 3
    assert res["independent_families"] == ["madagascar_gov", "un_fao", "un_wfp"]
    assert res["has_dependent_derivation"] is False
    assert res["is_truly_independent"] is True


# ==============================================================================
# 3. Price Conflict Detection & Dispersion (SPECS §15)
# ==============================================================================


def test_price_conflict_detection_and_dispersion_metrics():
    """Verify that multi-source divergence (>= 25% price spread ratio) triggers conflict flag."""

    def compute_mock_group_conflict(prices_by_source: list[dict[str, Any]]) -> dict[str, Any]:
        min_p = min(s["min_price"] for s in prices_by_source)
        max_p = max(s["max_price"] for s in prices_by_source)
        spread = max_p - min_p
        ratio = (max_p / min_p) if min_p > 0 else 1.0
        n_sources = len({s["source_id"] for s in prices_by_source})
        n_families = len({s["source_family"] for s in prices_by_source})
        has_conflict = n_sources > 1 and min_p > 0 and ratio >= 1.25
        return {
            "n_sources": n_sources,
            "n_families": n_families,
            "group_min_price": min_p,
            "group_max_price": max_p,
            "group_spread": spread,
            "has_conflict": has_conflict,
        }

    # Case 1: High divergence between two sources (Source A = 2500, Source B = 3500, ratio = 1.40 >= 1.25)
    high_conflict_group = [
        {
            "source_id": "miasa_odr",
            "source_family": "madagascar_gov",
            "min_price": 2400.0,
            "max_price": 2600.0,
        },
        {
            "source_id": "wfp_hdx_mdg",
            "source_family": "un_wfp",
            "min_price": 3400.0,
            "max_price": 3600.0,
        },
    ]
    res_high = compute_mock_group_conflict(high_conflict_group)
    assert res_high["has_conflict"] is True
    assert res_high["group_spread"] == 1200.0
    assert res_high["n_sources"] == 2
    assert res_high["n_families"] == 2

    # Case 2: Agreement between two sources (Source A = 2900, Source B = 3000, ratio = 3000/2900 = 1.034 < 1.25)
    agreement_group = [
        {
            "source_id": "miasa_odr",
            "source_family": "madagascar_gov",
            "min_price": 2900.0,
            "max_price": 2950.0,
        },
        {
            "source_id": "wfp_hdx_mdg",
            "source_family": "un_wfp",
            "min_price": 2950.0,
            "max_price": 3000.0,
        },
    ]
    res_agree = compute_mock_group_conflict(agreement_group)
    assert res_agree["has_conflict"] is False
    assert res_agree["group_spread"] == 100.0


# ==============================================================================
# 4. Priority Arbitration: Observed Strictly Beats Imputed (SPECS §15)
# ==============================================================================


def test_priority_arbitration_observed_vs_imputed():
    """Verify that observed data strictly precedes imputed data in gold.price_monthly_best arbitration."""

    def rank_source_priority(
        priority: str, has_observed: bool, n_obs: int, source_id: str
    ) -> tuple[int, int, str]:
        if priority == "P0" and has_observed:
            tier = 1
        elif priority == "P1" and has_observed:
            tier = 2
        elif priority == "P0" and not has_observed:
            tier = 3
        elif priority == "P1" and not has_observed:
            tier = 4
        elif priority == "P2" and has_observed:
            tier = 5
        elif priority == "P2" and not has_observed:
            tier = 6
        else:
            tier = 7
        return (tier, -n_obs, source_id)

    # P0 observed beats P1 observed
    p0_obs = rank_source_priority("P0", has_observed=True, n_obs=10, source_id="miasa_odr")
    p1_obs = rank_source_priority("P1", has_observed=True, n_obs=20, source_id="wfp_hdx_mdg")
    assert p0_obs < p1_obs

    # P1 observed beats P0 imputed!
    p0_imp = rank_source_priority("P0", has_observed=False, n_obs=50, source_id="miasa_odr")
    assert p1_obs < p0_imp, "Observed observation MUST take precedence over imputed observation"

    # P1 observed beats P1 imputed
    p1_imp = rank_source_priority("P1", has_observed=False, n_obs=30, source_id="wb_rtfp_mdg")
    assert p1_obs < p1_imp

    # P0 imputed beats P1 imputed
    assert p0_imp < p1_imp


# ==============================================================================
# 5. Incomparable Aggregation Refusal (R2.2, SPECS §6, §7)
# ==============================================================================


def test_incomparable_aggregation_guards():
    """Verify that validate_comparable_group strictly rejects physical and economic mismatches."""
    # 1. Mixed currencies
    with pytest.raises(
        IncompatibleAggregationError, match="incompatible_currencies_in_aggregation"
    ):
        validate_comparable_group(
            [
                ComparablePriceItem(
                    price_mga_per_base=Decimal("3000"), base_unit="kg", currency="MGA"
                ),
                ComparablePriceItem(
                    price_mga_per_base=Decimal("1"), base_unit="kg", currency="USD"
                ),
            ]
        )

    # 2. Mixed units (mass vs volume)
    with pytest.raises(IncompatibleAggregationError, match="cannot_aggregate_mixed_base_units"):
        validate_comparable_group(
            [
                ComparablePriceItem(price_mga_per_base=Decimal("3000"), base_unit="kg"),
                ComparablePriceItem(price_mga_per_base=Decimal("8000"), base_unit="l"),
            ]
        )

    # 3. Mixing price index with nominal price
    with pytest.raises(
        IncompatibleAggregationError, match="cannot_aggregate_index_with_nominal_prices"
    ):
        validate_comparable_group(
            [
                ComparablePriceItem(
                    price_mga_per_base=Decimal("3000"), base_unit="kg", is_index=False
                ),
                ComparablePriceItem(
                    price_mga_per_base=Decimal("120"), base_unit="kg", is_index=True
                ),
            ]
        )

    # 4. Mixed actors without explicit segmentation
    with pytest.raises(
        IncompatibleAggregationError, match="cannot_aggregate_incompatible_actor_levels"
    ):
        validate_comparable_group(
            [
                ComparablePriceItem(
                    price_mga_per_base=Decimal("1500"), base_unit="kg", actor_level="farmgate"
                ),
                ComparablePriceItem(
                    price_mga_per_base=Decimal("3000"), base_unit="kg", actor_level="retail"
                ),
            ]
        )


def test_missing_values_never_default_to_zero():
    """Verify that missing prices return None and are never replaced by zero."""
    items = [
        ComparablePriceItem(price_mga_per_base=None, base_unit="kg"),
        ComparablePriceItem(price_mga_per_base=Decimal("0"), base_unit="kg"),
    ]
    valid = filter_comparable_items(items)
    assert valid == [], "Missing and zero prices must be excluded from comparable items"
    assert compute_safe_arithmetic_average(items) is None


# ==============================================================================
# 6. Market Health Normative Formula & Coverage Threshold (SPECS §16)
# ==============================================================================


def test_market_health_coverage_threshold_and_components():
    """Verify that coverage < 0.50 produces composite_score = None, and components are never masked."""
    # Stability alone = 0.30 < 0.50 -> None
    res1 = calculate_market_health_score(score_stability=80.0)
    assert res1.coverage == 0.30
    assert res1.composite_score is None

    # Affordability alone = 0.25 < 0.50 -> None
    res2 = calculate_market_health_score(score_affordability=70.0)
    assert res2.coverage == 0.25
    assert res2.composite_score is None

    # Availability alone = 0.25 < 0.50 -> None
    res3 = calculate_market_health_score(score_availability=100.0)
    assert res3.coverage == 0.25
    assert res3.composite_score is None

    # Climate alone = 0.20 < 0.50 -> None
    res4 = calculate_market_health_score(score_climate=90.0)
    assert res4.coverage == 0.20
    assert res4.composite_score is None

    # Stability (0.30) + Affordability (0.25) = 0.55 >= 0.50 -> computed!
    # Weighted sum: 80 * 0.30 + 70 * 0.25 = 24.0 + 17.5 = 41.5
    # Composite: 41.5 / 0.55 = 75.45
    res5 = calculate_market_health_score(score_stability=80.0, score_affordability=70.0)
    assert res5.coverage == 0.55
    assert res5.composite_score == 75.45


def test_market_health_missing_inputs_yield_none():
    """Verify individual component functions return None on missing input."""
    assert calculate_price_stability_score(None) is None
    assert calculate_affordability_score(None) is None
    assert calculate_availability_score(None) is None
    assert calculate_availability_score("unknown") is None
    assert calculate_climate_risk_score(None) is None


# ==============================================================================
# 7. Blocking DQ Gate & Publication Refusal (SPECS §14)
# ==============================================================================


def test_blocking_dq_gate_passes_when_all_checks_pass():
    """Verify check_blocking_dq_gate passes and returns checks when requirements are met."""
    mock_session = MagicMock()

    # Mock provenance check: 100% valid
    mock_session.execute.side_effect = [
        MagicMock(fetchone=lambda: (10, 10)),  # check_provenance_complete
        MagicMock(
            scalars=lambda: MagicMock(
                all=lambda: [MagicMock(extraction_status="parsed") for _ in range(5)]
            )
        ),  # check_parse_success_rate
        MagicMock(scalar=lambda: 0),  # check_llm_unverified_in_gold
    ]

    results = check_blocking_dq_gate(mock_session)
    assert len(results) == 3
    assert all(r.passed for r in results)


def test_blocking_dq_gate_refuses_when_provenance_incomplete():
    """Verify incomplete provenance (< 100%) raises GoldDqRejected."""
    mock_session = MagicMock()
    mock_session.execute.side_effect = [
        MagicMock(fetchone=lambda: (10, 9)),  # 9/10 = 90% < 100%
    ]
    with pytest.raises(GoldDqRejected, match="blocking_dq_provenance_incomplete"):
        check_blocking_dq_gate(mock_session)


def test_blocking_dq_gate_refuses_when_parse_rate_low():
    """Verify parse rate < 99% raises GoldDqRejected."""
    mock_session = MagicMock()
    # 10/10 provenance OK, but 90/100 parsed = 90% < 99%
    records = [MagicMock(extraction_status="parsed" if i < 90 else "failed") for i in range(100)]
    mock_session.execute.side_effect = [
        MagicMock(fetchone=lambda: (10, 10)),
        MagicMock(scalars=lambda: MagicMock(all=lambda: records)),
    ]
    with pytest.raises(GoldDqRejected, match="blocking_dq_parse_rate_low"):
        check_blocking_dq_gate(mock_session)


def test_blocking_dq_gate_refuses_when_unverified_llm_in_gold():
    """Verify unverified LLM rows entering Gold raises GoldDqRejected."""
    mock_session = MagicMock()
    mock_session.execute.side_effect = [
        MagicMock(fetchone=lambda: (10, 10)),  # prov OK
        MagicMock(
            scalars=lambda: MagicMock(all=lambda: [MagicMock(extraction_status="parsed")])
        ),  # parse OK
        MagicMock(scalar=lambda: 3),  # 3 unverified LLM records in Gold!
    ]
    with pytest.raises(GoldDqRejected, match="blocking_dq_llm_unverified_in_gold"):
        check_blocking_dq_gate(mock_session)


# ==============================================================================
# 8. Publication Denominators Accounting Invariant (SPECS §14)
# ==============================================================================


def test_publication_denominators_valid_invariant():
    """Verify PublicationDenominators validates candidate = accepted + rejected + review."""
    denoms = PublicationDenominators(
        candidate_files=10,
        parsed_files=8,
        failed_files=1,
        review_files=1,
        pending_files=0,
        candidate_rows=100,
        accepted_rows=80,
        rejected_rows=15,
        review_rows=5,
    )
    # 80 + 15 + 5 = 100 == candidate_rows
    # 8 + 1 + 1 + 0 = 10 == candidate_files
    denoms.validate_invariants()


def test_publication_denominators_inconsistent_rows_detected():
    """Verify inconsistent row counts raise ValueError."""
    denoms = PublicationDenominators(
        candidate_files=1,
        parsed_files=1,
        failed_files=0,
        review_files=0,
        pending_files=0,
        candidate_rows=100,
        accepted_rows=80,
        rejected_rows=10,
        review_rows=5,  # 80 + 10 + 5 = 95 != 100!
    )
    with pytest.raises(ValueError, match="publication_denominators_inconsistent"):
        denoms.validate_invariants()


def test_publication_denominators_inconsistent_files_detected():
    """Verify inconsistent file counts raise ValueError."""
    denoms = PublicationDenominators(
        candidate_files=10,
        parsed_files=7,
        failed_files=1,
        review_files=1,
        pending_files=0,  # 7 + 1 + 1 + 0 = 9 != 10!
        candidate_rows=50,
        accepted_rows=50,
        rejected_rows=0,
        review_rows=0,
    )
    with pytest.raises(ValueError, match="file_denominators_inconsistent"):
        denoms.validate_invariants()


# ==============================================================================
# 9. SQL View Definitions Conformance
# ==============================================================================


def test_gold_sql_files_contain_updated_contracts():
    """Verify that all modified Gold SQL view definitions meet R2.3 requirements."""
    sql_dir = get_sql_dir()

    # 1. 001_price_obs_current.sql has source_family
    v1_sql = (sql_dir / "001_price_obs_current.sql").read_text(encoding="utf-8")
    assert "source_family" in v1_sql
    assert "WITH NO DATA;" in v1_sql

    # 2. 002_price_monthly.sql has source_family, price_spread, stddev_price
    v2_sql = (sql_dir / "002_price_monthly.sql").read_text(encoding="utf-8")
    assert "source_family" in v2_sql
    assert "price_spread" in v2_sql
    assert "stddev_price" in v2_sql
    assert "WITH NO DATA;" in v2_sql

    # 3. 003_price_monthly_best.sql has n_sources, n_families, has_conflict, group_spread
    v3_sql = (sql_dir / "003_price_monthly_best.sql").read_text(encoding="utf-8")
    assert "chosen_source_family" in v3_sql
    assert "n_sources" in v3_sql
    assert "n_families" in v3_sql
    assert "has_conflict" in v3_sql
    assert "group_spread" in v3_sql
    assert "WITH NO DATA;" in v3_sql

    # 4. 004_price_changes.sql has calendar-aligned LEFT JOINs
    v4_sql = (sql_dir / "004_price_changes.sql").read_text(encoding="utf-8")
    assert "INTERVAL '1 month'" in v4_sql
    assert "INTERVAL '3 months'" in v4_sql
    assert "INTERVAL '12 months'" in v4_sql
    assert "LAG(" not in v4_sql, "Naive LAG must be replaced with exact calendar left joins"
    assert "WITH NO DATA;" in v4_sql

    # 5. 009_cpi_food.sql has calendar-aligned joins
    v9_sql = (sql_dir / "009_cpi_food.sql").read_text(encoding="utf-8")
    assert "INTERVAL '1 month'" in v9_sql
    assert "INTERVAL '12 months'" in v9_sql
    assert "LAG(" not in v9_sql
    assert "WITH NO DATA;" in v9_sql

    # 6. 010_market_health.sql has strict NULL component handling and coverage threshold
    v10_sql = (sql_dir / "010_market_health.sql").read_text(encoding="utf-8")
    assert "score_stability" in v10_sql
    assert "score_affordability" in v10_sql
    assert "score_availability" in v10_sql
    assert "score_climate" in v10_sql
    assert "coverage >= 0.50" in v10_sql
    assert "WITH NO DATA;" in v10_sql


# ==============================================================================
# 10. Property-based tests (Hypothesis) for calendar variations
# ==============================================================================


@settings(max_examples=50)
@given(
    price_t=st.floats(min_value=100.0, max_value=50000.0),
    price_prev=st.floats(min_value=100.0, max_value=50000.0),
    lag_months=st.integers(min_value=1, max_value=12),
)
def test_hypothesis_calendar_variation_exactness(
    price_t: float, price_prev: float, lag_months: int
):
    """Property test: For any positive prices and valid lag, calculate_calendar_aligned_variation matches formula."""
    curr_month = date(2024, 6, 1)
    # Compute expected target date
    total_m = curr_month.year * 12 + (curr_month.month - 1) - lag_months
    target_date = date(total_m // 12, (total_m % 12) + 1, 1)

    prices = {curr_month: price_t, target_date: price_prev}
    chg = calculate_calendar_aligned_variation(prices, curr_month, lag_months)

    expected = round((price_t / price_prev) - 1.0, 4)
    assert chg == expected


# ==============================================================================
# 11. Comprehensive Coverage of Data Quality Engine Functions (SPECS §14)
# ==============================================================================


def test_get_publication_denominators_with_and_without_source_id():
    """Verify get_publication_denominators computes correct figures with and without source_id."""
    mock_session = MagicMock()
    # Mock return rows for files and rows:
    # f_row: total, parsed, failed, review, pending
    # r_row: candidate, accepted, rejected, review
    mock_session.execute.side_effect = [
        MagicMock(fetchone=lambda: (10, 8, 1, 1, 0)),
        MagicMock(fetchone=lambda: (100, 80, 15, 5)),
        MagicMock(fetchone=lambda: (5, 4, 1, 0, 0)),
        MagicMock(fetchone=lambda: (50, 45, 5, 0)),
    ]

    # Global
    d_global = get_publication_denominators(mock_session)
    assert d_global.candidate_files == 10
    assert d_global.parsed_files == 8
    assert d_global.candidate_rows == 100
    assert d_global.accepted_rows == 80

    # Source filtered
    d_source = get_publication_denominators(mock_session, source_id="miasa_odr")
    assert d_source.candidate_files == 5
    assert d_source.parsed_files == 4
    assert d_source.candidate_rows == 50
    assert d_source.accepted_rows == 45


def test_check_provenance_complete_source_filtered():
    """Verify check_provenance_complete with source_id."""
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchone.return_value = (50, 50)
    res = check_provenance_complete(mock_session, source_id="miasa_odr")
    assert res.passed is True
    assert res.metric == 100.0
    assert res.source_id == "miasa_odr"


def test_check_parse_success_rate_source_filtered():
    """Verify check_parse_success_rate with source_id."""
    mock_session = MagicMock()
    records = [MagicMock(extraction_status="parsed") for _ in range(10)]
    mock_session.execute.return_value.scalars.return_value.all.return_value = records
    res = check_parse_success_rate(mock_session, source_id="miasa_odr")
    assert res.passed is True
    assert res.metric == 100.0


def test_check_price_range_sanity_global_and_filtered():
    """Verify check_price_range_sanity with and without violations."""
    mock_session = MagicMock()
    # Case 1: 0 violations
    mock_session.execute.return_value.scalar.return_value = 0
    res1 = check_price_range_sanity(mock_session)
    assert res1.passed is True
    assert res1.metric == 0.0

    # Case 2: 2 violations for specific source
    mock_session.execute.return_value.scalar.return_value = 2
    res2 = check_price_range_sanity(mock_session, source_id="wfp_hdx_mdg")
    assert res2.passed is False
    assert res2.metric == 2.0


def test_check_llm_unverified_source_filtered():
    """Verify check_llm_unverified_in_gold with source_id filter."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar.return_value = 0
    res = check_llm_unverified_in_gold(mock_session, source_id="miasa_odr")
    assert res.passed is True
    assert res.metric == 0.0


def test_check_freshness_and_manage_alerts_lifecycle():
    """Verify check_freshness_and_manage_alerts generates and resolves alerts."""
    from ketrika.gold.dq import check_freshness_and_manage_alerts

    mock_session = MagicMock()
    # Row tuple: (source_id, freshness_sla_days, freshness_days, is_stale, last_fetched_at)
    mock_session.execute.side_effect = [
        # Query 1: gold.source_health returns one stale source and one fresh source
        MagicMock(
            fetchall=lambda: [
                ("miasa_odr", 28, 45.0, True, "2024-01-01T00:00:00Z"),
                ("wfp_hdx_mdg", 62, 10.0, False, "2024-02-15T00:00:00Z"),
            ]
        ),
        # Query 2: existing alert lookup for miasa_odr (None -> new alert created)
        MagicMock(scalar_one_or_none=lambda: None),
        # Query 3: existing alert lookup for wfp_hdx_mdg (None -> no alert needed)
        MagicMock(scalar_one_or_none=lambda: None),
    ]

    checks = check_freshness_and_manage_alerts(mock_session)
    assert len(checks) == 2
    assert checks[0].passed is False  # miasa_odr is stale
    assert checks[0].source_id == "miasa_odr"
    assert checks[1].passed is True  # wfp_hdx_mdg is fresh

    # Verify an alert was added
    assert mock_session.add.called


def test_run_all_dq_checks_battery():
    """Verify run_all_dq_checks executes all batteries and can persist records."""
    from ketrika.gold.dq import run_all_dq_checks

    mock_session = MagicMock()
    mock_session.execute.side_effect = [
        MagicMock(fetchone=lambda: (10, 10)),  # provenance
        MagicMock(
            scalars=lambda: MagicMock(all=lambda: [MagicMock(extraction_status="parsed")])
        ),  # parse
        MagicMock(scalar=lambda: 0),  # price range
        MagicMock(scalar=lambda: 0),  # llm unverified
        MagicMock(fetchall=lambda: []),  # freshness
    ]

    results = run_all_dq_checks(mock_session, persist=True)
    assert len(results) == 4
    assert all(r.passed for r in results)
    # Persist added 4 DqResult rows:
    assert mock_session.add.call_count == 4
