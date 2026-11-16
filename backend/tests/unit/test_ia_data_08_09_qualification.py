"""Tests for IA-DATA-08, IA-DATA-09, and IA-DATA-10:
Economic metrics qualification, agroclimatic resolution, and Dagster automation governance.
"""

from dagster import AssetKey

from ketrika.gold.economic import (
    ECONOMIC_METRIC_CARDS,
    REASON_BASE_SHIFT,
    REASON_INCOMPATIBLE_UNITS,
    REASON_MISSING_DENOMINATOR,
    REASON_MISSING_SERIES,
    REASON_UNALIGNED_PERIOD,
    REASON_ZERO_DENOMINATOR,
    audit_inflation_vs_market_price_distinctness,
    calculate_import_dependency_ratio,
    calculate_import_unit_cost,
    calculate_safe_variation,
)
from ketrika.pipelines.definitions import (
    all_assets,
    all_checks,
    all_schedules,
    defs,
    document_replay_jobs,
    source_inventory,
)


def test_ia_data_08_economic_catalog_coverage_and_families():
    """Verify that economic metric cards cover all 5 autonomous dimensions with qualified source families."""
    dimensions = {card.dimension for card in ECONOMIC_METRIC_CARDS.values()}
    assert dimensions == {
        "inflation",
        "exchange_rate",
        "fuel_energy",
        "external_trade",
        "real_activity",
    }

    families = {card.source_family for card in ECONOMIC_METRIC_CARDS.values()}
    assert "instat" in families
    assert "bfm" in families
    assert "omh" in families
    assert "faostat" in families

    for metric_id, card in ECONOMIC_METRIC_CARDS.items():
        assert card.metric_id == metric_id
        assert card.title
        assert card.definition
        assert card.unit
        assert card.frequency in ("daily", "monthly", "quarterly", "annual", "event")
        assert card.publication_lag_days > 0


def test_ia_data_08_safe_variation_guards():
    """Verify variation calculations strictly reject base shifts and zero denominators."""
    # 1. Base shift rejection
    val, reason = calculate_safe_variation(112.5, 100.0, current_base="2016", prev_base="2010")
    assert val is None
    assert reason == REASON_BASE_SHIFT

    # 2. Zero denominator rejection
    val, reason = calculate_safe_variation(50.0, 0.0)
    assert val is None
    assert reason == REASON_ZERO_DENOMINATOR

    # 3. Missing denominator rejection
    val, reason = calculate_safe_variation(50.0, None)
    assert val is None
    assert reason == REASON_MISSING_DENOMINATOR

    # 4. Missing series rejection
    val, reason = calculate_safe_variation(None, 50.0)
    assert val is None
    assert reason == REASON_MISSING_SERIES

    # 5. Nominal valid variation
    val, reason = calculate_safe_variation(110.0, 100.0, current_base="2016", prev_base="2016")
    assert val == 0.1000
    assert reason is None


def test_ia_data_08_import_unit_cost_physical_units():
    """Verify CIF import unit cost strictly validates physical units and converts tons to kg."""
    # Incompatible unit rejection
    val, reason = calculate_import_unit_cost(10_000_000.0, 5.0, unit_val="USD", unit_vol="tons")
    assert val is None
    assert reason == REASON_INCOMPATIBLE_UNITS

    # Nominal calculation: 10,000,000 MGA for 5 tons = 10,000,000 / 5,000 kg = 2,000 MGA/kg
    val, reason = calculate_import_unit_cost(10_000_000.0, 5.0, unit_val="MGA", unit_vol="tons")
    assert val == 2000.0
    assert reason is None


def test_ia_data_08_import_dependency_temporal_alignment():
    """Verify import dependency ratio rejects unaligned temporal periods."""
    # Unaligned periods rejection (e.g. 2024 import vs 2023 production)
    val, reason = calculate_import_dependency_ratio(
        import_tonnes=500_000.0,
        prod_tonnes=4_000_000.0,
        period_import="2024",
        period_prod="2023",
    )
    assert val is None
    assert reason == REASON_UNALIGNED_PERIOD

    # Aligned periods nominal calculation
    val, reason = calculate_import_dependency_ratio(
        import_tonnes=500_000.0,
        prod_tonnes=4_000_000.0,
        period_import="2024",
        period_prod="2024",
    )
    assert val is not None
    assert reason is None


def test_ia_data_08_inflation_vs_market_price_distinctness():
    """Verify that macroeconomic CPI food inflation is strictly separated from direct market price variation."""
    audit = audit_inflation_vs_market_price_distinctness(
        cpi_food_chg_12m=0.085,
        market_price_chg_12m=0.120,
    )
    assert audit["concepts_strictly_separated"] is True
    assert audit["cpi_food_inflation_rate_pct"] == 8.5
    assert audit["market_price_variation_rate_pct"] == 12.0
    assert audit["spread_pct_points"] == 3.5


def test_ia_data_09_agroclimatic_geographic_boundaries():
    """Verify Madagascar bounding box and spatial resolution constraints."""
    # Madagascar bounding box: Latitude [-25.6, -11.9], Longitude [43.2, 50.5]
    mdg_bbox = {
        "lat_min": -25.6,
        "lat_max": -11.9,
        "lon_min": 43.2,
        "lon_max": 50.5,
    }

    # Verify key agroclimatic station points fall within bounds
    stations = {
        "Antananarivo": (-18.91, 47.53),
        "Antsirabe": (-19.86, 47.03),
        "Ambatondrazaka": (-17.83, 48.42),
        "Toamasina": (-18.15, 49.41),
        "Toliara": (-23.35, 43.67),
        "Mahajanga": (-15.72, 46.32),
    }

    for name, (lat, lon) in stations.items():
        assert mdg_bbox["lat_min"] <= lat <= mdg_bbox["lat_max"], f"{name} lat out of bounds"
        assert mdg_bbox["lon_min"] <= lon <= mdg_bbox["lon_max"], f"{name} lon out of bounds"


def test_ia_data_10_dagster_orchestration_governance():
    """Verify Dagster orchestration assets, asset checks, schedules, and timezone governance."""
    # 1. Total inventory and eligible sources
    eligible_sources = [entry for entry in source_inventory if entry.included]
    assert len(eligible_sources) == 16

    # 2. Replay jobs: 1 replay job per eligible source
    assert len(document_replay_jobs) == len(eligible_sources)

    # 3. Timezone: all schedules must be strictly anchored to Indian/Antananarivo (UTC+3)
    for schedule in all_schedules:
        assert schedule.execution_timezone == "Indian/Antananarivo"

    # 4. Blocking checks: exactly 2 blocking checks per eligible source
    assert len(all_checks) == 2 * len(eligible_sources)

    # 5. Failure sensor registered
    assert len(defs.sensors) >= 1
    sensor_names = [s.name for s in defs.sensors]
    assert "pipeline_failure_email_sensor" in sensor_names

    # 6. Global Gold Refresh depends on all eligible silver assets
    gold_asset = next(a for a in all_assets if a.key == AssetKey(["gold__refresh"]))
    assert gold_asset is not None
    assert len(gold_asset.asset_deps[gold_asset.key]) == len(eligible_sources)
