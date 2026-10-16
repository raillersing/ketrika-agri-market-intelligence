"""Unit and integration tests for market coverage matrix, independent gaps, and pilot selection (R2.4)."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ketrika.api.routers.coverage import (
    get_market_coverage,
    get_pilot_configuration,
    get_series_gaps,
)
from ketrika.api.schemas import MarketCoverageItem, PilotConfigResponse, SeriesCoverageSummaryItem
from ketrika.core.pilot import (
    PilotNoAuthenticDataError,
    check_pilot_authenticity,
    load_pilot_config,
)
from ketrika.gold.coverage import (
    add_calendar_month,
    audit_pilot_market_coverage,
    calculate_missing_months,
    compute_series_gaps_independent_sql,
    query_market_coverage_matrix,
)

# ============================================================================
# 1. Pilot Configuration Tests
# ============================================================================


def test_load_pilot_config_structure():
    """Verify pilot configuration is loaded and complies with all R2.4 rules."""
    config = load_pilot_config()

    assert config.pilot_id == "pilot_rice_2026"
    assert config.version == "1.0.0"

    # Prescribed products: local rice and imported rice
    product_codes = [p.product_code for p in config.products]
    assert "RICE_WHITE_LOCAL" in product_codes
    assert "RICE_WHITE_IMPORTED" in product_codes
    assert len(config.products) == 2

    for p in config.products:
        assert p.category == "cereal"
        assert p.base_unit == "kg"
        assert len(p.justification) > 10

    # Prescribed locations: at most 3 regional zones + national
    location_pcodes = [loc.pcode for loc in config.locations]
    regional_locations = [loc for loc in config.locations if loc.admin_level == 1]
    assert len(regional_locations) <= 3

    assert "MDG11" in location_pcodes  # Analamanga (consumption)
    assert "MDG31" in location_pcodes  # Alaotra-Mangoro (production)
    assert "MDG33" in location_pcodes  # Atsinanana (import port)
    assert "MDG0" in location_pcodes  # National reference

    # Economic roles verified
    roles = {loc.pcode: loc.economic_role for loc in config.locations}
    assert roles["MDG11"] == "bassin_consommation_urbain"
    assert roles["MDG31"] == "bassin_production_agricole"
    assert roles["MDG33"] == "port_entree_importations"
    assert roles["MDG0"] == "synthese_macroeconomique"

    # Complementarity rationale must be substantive
    assert len(config.complementarity_rationale) > 50
    assert "Alaotra-Mangoro" in config.complementarity_rationale
    assert "Analamanga" in config.complementarity_rationale
    assert "Atsinanana" in config.complementarity_rationale

    # Impossible capabilities explicitly documented
    caps = {c.capability: c for c in config.impossible_capabilities}
    assert "granularite_infra_regionale_continue" in caps
    assert caps["granularite_infra_regionale_continue"].status == "impossible"
    assert "admin2_district" in caps["granularite_infra_regionale_continue"].scope

    assert "acteurs_intermediaires_informels" in caps
    assert caps["acteurs_intermediaires_informels"].status == "impossible"

    assert "frequence_journaliere_continue" in caps
    assert caps["frequence_journaliere_continue"].status == "impossible"

    # Authenticity requirements
    auth_req = config.authenticity_requirements
    assert auth_req.minimum_authentic_sources >= 1
    assert "miasa_odr" in auth_req.allowed_authentic_sources
    assert "wb_rtfp_mdg" in auth_req.allowed_authentic_sources
    assert auth_req.disallow_synthetic_seed_substitution is True


# ============================================================================
# 2. Independent Calendar Gap Calculation Tests
# ============================================================================


def test_add_calendar_month():
    """Verify exact monthly calendar stepping."""
    assert add_calendar_month(datetime.date(2023, 1, 1)) == datetime.date(2023, 2, 1)
    assert add_calendar_month(datetime.date(2023, 12, 1)) == datetime.date(2024, 1, 1)


def test_calculate_missing_months_continuous_series():
    """Continuous 12 months must have 0 missing months and 1.0 coverage ratio."""
    months = [datetime.date(2023, m, 1) for m in range(1, 13)]
    missing_cnt, missing_list, ratio = calculate_missing_months(months)

    assert missing_cnt == 0
    assert len(missing_list) == 0
    assert ratio == 1.0


def test_calculate_missing_months_with_gaps():
    """Series with missing months must independently detect all absent months."""
    # Jan, Feb, Apr, Jun, Jul (Mar and May missing in 7-month range)
    months = [
        datetime.date(2023, 1, 1),
        datetime.date(2023, 2, 1),
        datetime.date(2023, 4, 1),
        datetime.date(2023, 6, 1),
        datetime.date(2023, 7, 1),
    ]
    missing_cnt, missing_list, ratio = calculate_missing_months(months)

    assert missing_cnt == 2
    assert missing_list == [datetime.date(2023, 3, 1), datetime.date(2023, 5, 1)]
    assert ratio == round(5 / 7, 4)


def test_calculate_missing_months_sparse_series():
    """Sparse series across 24 months."""
    months = [
        datetime.date(2022, 1, 1),
        datetime.date(2022, 6, 1),
        datetime.date(2023, 12, 1),
    ]
    missing_cnt, missing_list, ratio = calculate_missing_months(months)

    assert missing_cnt == 21
    assert len(missing_list) == 21
    assert ratio == round(3 / 24, 4)


def test_calculate_missing_months_empty():
    """Empty series handling."""
    missing_cnt, missing_list, ratio = calculate_missing_months([])
    assert missing_cnt == 0
    assert missing_list == []
    assert ratio == 0.0

    # With explicit range
    missing_cnt2, missing_list2, ratio2 = calculate_missing_months(
        [], start_month="2023-01-01", end_month="2023-03-01"
    )
    assert missing_cnt2 == 3
    assert len(missing_list2) == 3
    assert ratio2 == 0.0


@given(
    st.lists(
        st.integers(min_value=1, max_value=24),
        min_size=1,
        max_size=24,
        unique=True,
    )
)
def test_hypothesis_missing_months_invariant(month_indices: list[int]):
    """Hypothesis property: missing_count + distinct_observed_in_range == expected_total."""

    def offset_month(idx: int) -> datetime.date:
        year = 2022 + (idx - 1) // 12
        month = ((idx - 1) % 12) + 1
        return datetime.date(year, month, 1)

    observed = sorted([offset_month(i) for i in month_indices])
    start = min(observed)
    end = max(observed)

    # Compute expected total months directly
    expected_total = (end.year - start.year) * 12 + (end.month - start.month) + 1

    missing_cnt, missing_list, ratio = calculate_missing_months(observed, start, end)

    assert missing_cnt + len(set(observed)) == expected_total
    assert len(missing_list) == missing_cnt
    assert ratio == round(len(set(observed)) / expected_total, 4)


# ============================================================================
# 3. Pilot Authenticity Guard Tests
# ============================================================================


def test_check_pilot_authenticity_synthetic_rejection():
    """Synthetic observations must be strictly refused as proof of coverage."""
    mock_session = MagicMock()
    # Mock return rows where natural_key starts with "synthetic_"
    mock_session.execute.return_value.fetchall.return_value = [
        ("miasa_odr", "synthetic_rice_001", 10),
        ("miasa_odr", "test_fixture_002", 5),
    ]

    result = check_pilot_authenticity(session=mock_session, raise_on_error=False)

    assert result.is_authentic is False
    assert result.status == "BLOCKED_NO_AUTHENTIC_DATA"
    assert result.authentic_observations_count == 0
    assert result.synthetic_observations_count == 15
    assert "synthetic seeds cannot substitute authentic data" in result.summary_message

    with pytest.raises(PilotNoAuthenticDataError):
        check_pilot_authenticity(session=mock_session, raise_on_error=True)


def test_check_pilot_authenticity_empty_database():
    """Empty database must produce BLOCKED_NO_AUTHENTIC_DATA."""
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = []

    result = check_pilot_authenticity(session=mock_session, raise_on_error=False)

    assert result.is_authentic is False
    assert result.status == "BLOCKED_NO_AUTHENTIC_DATA"
    assert result.authentic_observations_count == 0


def test_check_pilot_authenticity_authentic_qualification():
    """Authentic observations from qualified sources qualify the pilot."""
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = [
        ("miasa_odr", "ODR_2024_01_ANOSIBE_LOCAL", 42),
        ("wb_rtfp_mdg", "WB_RTFP_MDG11_2023_10", 120),
    ]

    result = check_pilot_authenticity(session=mock_session, raise_on_error=True)

    assert result.is_authentic is True
    assert result.status == "QUALIFIED_AUTHENTIC"
    assert result.authentic_observations_count == 162
    assert result.synthetic_observations_count == 0
    assert "miasa_odr" in result.authentic_sources_found
    assert "wb_rtfp_mdg" in result.authentic_sources_found


# ============================================================================
# 4. SQL Recomputability & Gap Query Tests (in-memory SQLite simulation)
# ============================================================================


def test_query_market_coverage_matrix_mapping():
    """Verify query_market_coverage_matrix correctly transforms SQL tuples to MarketCoverageRow."""
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = [
        (
            None,
            "RICE_WHITE_LOCAL",
            "Riz blanc local",
            None,
            "MDG11",
            "Analamanga",
            1,
            "retail",
            "2024-03-01",
            2,
            1,
            "miasa_odr, wb_rtfp_mdg",
            "odr, un_wfp",
            15,
            0.0,
            True,
            "observed",
            2800.0,
            3200.0,
            3000.0,
            30,
        )
    ]

    rows = query_market_coverage_matrix(session=mock_session, product_code="RICE_WHITE_LOCAL")
    assert len(rows) == 1
    r = rows[0]
    assert r.product_code == "RICE_WHITE_LOCAL"
    assert r.location_pcode == "MDG11"
    assert r.actor_level == "retail"
    assert r.month == "2024-03-01"
    assert r.n_sources == 2
    assert r.n_obs == 15
    assert r.has_observed is True
    assert r.observed_or_imputed == "observed"
    assert r.median_price == 3000.0


def test_compute_series_gaps_independent_sql_mock():
    """Verify compute_series_gaps_independent_sql handles result row mapping."""
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchone.return_value = (
        "2023-01-01",
        "2023-12-01",
        12,  # total expected
        10,  # total observed
        2,  # missing count
        0.8333,  # coverage ratio
        ["2023-04-01", "2023-08-01"],  # missing list
        "odr, un_wfp",  # families
        "Riz blanc local",
        "Analamanga",
        1,
    )

    summary = compute_series_gaps_independent_sql(
        session=mock_session,
        product_code="RICE_WHITE_LOCAL",
        location_pcode="MDG11",
        actor_level="retail",
    )

    assert summary.expected_months == 12
    assert summary.observed_months == 10
    assert summary.missing_months == 2
    assert summary.coverage_ratio == 0.8333
    assert summary.missing_months_list == ["2023-04-01", "2023-08-01"]
    assert summary.is_pilot_candidate is True
    assert "odr" in summary.source_families


def test_audit_pilot_market_coverage():
    """Verify audit_pilot_market_coverage runs across all pilot combinations."""
    mock_session = MagicMock()
    # Mock fetchone to return 12 expected, 12 observed (full coverage)
    mock_session.execute.return_value.fetchone.return_value = (
        "2023-01-01",
        "2023-12-01",
        12,
        12,
        0,
        1.0,
        [],
        "odr",
        "Riz",
        "Zone",
        1,
    )

    audit = audit_pilot_market_coverage(session=mock_session)

    assert audit["pilot_id"] == "pilot_rice_2026"
    assert audit["total_series_evaluated"] == 8  # 2 products * 4 locations
    assert audit["total_expected_cell_months"] == 8 * 12
    assert audit["total_observed_cell_months"] == 8 * 12
    assert audit["total_missing_cell_months"] == 0
    assert audit["overall_coverage_ratio"] == 1.0
    assert len(audit["impossible_capabilities"]) == 3


# ============================================================================
# 5. API Endpoints Tests
# ============================================================================


def test_api_get_market_coverage():
    """Test GET /v1/market/coverage endpoint."""
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = [
        (
            None,
            "RICE_WHITE_LOCAL",
            "Riz blanc local",
            None,
            "MDG11",
            "Analamanga",
            1,
            "retail",
            "2024-01-01",
            1,
            1,
            "miasa_odr",
            "odr",
            10,
            0.0,
            True,
            "observed",
            2900.0,
            3100.0,
            3000.0,
            60,
        )
    ]

    items = get_market_coverage(
        product="RICE_WHITE_LOCAL",
        location="MDG11",
        actor_level="retail",
        from_date=None,
        to_date=None,
        session=mock_session,
    )

    assert len(items) == 1
    assert isinstance(items[0], MarketCoverageItem)
    assert items[0].product_code == "RICE_WHITE_LOCAL"
    assert items[0].median_price == 3000.0


def test_api_get_series_gaps():
    """Test GET /v1/market/coverage/gaps endpoint."""
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchone.return_value = (
        "2023-01-01",
        "2023-06-01",
        6,
        5,
        1,
        0.8333,
        ["2023-03-01"],
        "odr",
        "Riz blanc local",
        "Analamanga",
        1,
    )

    item = get_series_gaps(
        product="RICE_WHITE_LOCAL",
        location="MDG11",
        actor_level="retail",
        session=mock_session,
    )

    assert isinstance(item, SeriesCoverageSummaryItem)
    assert item.missing_months == 1
    assert item.missing_months_list == ["2023-03-01"]
    assert item.is_pilot_candidate is True


def test_api_get_pilot_configuration():
    """Test GET /v1/market/pilot endpoint."""
    mock_session = MagicMock()
    # Mock check_pilot_authenticity query
    mock_session.execute.return_value.fetchall.return_value = [
        ("miasa_odr", "ODR_2024_01_ANOSIBE_LOCAL", 50),
    ]

    resp = get_pilot_configuration(session=mock_session)

    assert isinstance(resp, PilotConfigResponse)
    assert resp.pilot_id == "pilot_rice_2026"
    assert len(resp.products) == 2
    assert len(resp.locations) == 4
    assert resp.authenticity_status == "QUALIFIED_AUTHENTIC"
    assert resp.authentic_observations_count == 50
    assert "miasa_odr" in resp.authentic_sources_found
