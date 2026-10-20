"""Unit tests for agro-climatic anomalies and zonal aggregations (R4.6, ADR-085, SPECS §26)."""

from ketrika.geo.anomalies import (
    ClimateBaseline,
    compute_climate_anomaly,
    compute_climate_baseline,
)
from ketrika.geo.contracts import (
    AggregationMethod,
    AgroClimateRiskLevel,
    WeatherVariable,
)
from ketrika.geo.raster import aggregate_zonal


def test_compute_climate_baseline_success():
    """Test computation of climatological baseline with N >= 10 years."""
    # 10 known values: mean = 100.0
    history = [100.0, 110.0, 90.0, 105.0, 95.0, 120.0, 80.0, 100.0, 105.0, 95.0]
    years = list(range(2010, 2020))

    baseline = compute_climate_baseline(
        history, years, min_years=10, variable=WeatherVariable.PRECIP_MM
    )
    assert baseline is not None
    assert baseline.sample_size == 10
    assert baseline.mean == 100.0
    assert baseline.period_start_year == 2010
    assert baseline.period_end_year == 2019
    assert baseline.std > 0.0


def test_compute_climate_baseline_abstention_insufficient_history():
    """Criterion: Formal abstention if historical data < 10 years (ADR-085)."""
    # Only 7 valid years
    short_history = [100.0, 110.0, 90.0, 105.0, 95.0, -9999.0, 80.0, 100.0]
    baseline = compute_climate_baseline(short_history, min_years=10)
    assert baseline is None


def test_compute_climate_anomaly_abstention_status():
    """Test anomaly computation returns status='insufficient_history' when baseline is None."""
    res = compute_climate_anomaly(
        observed_value=85.0,
        baseline=None,
        variable=WeatherVariable.PRECIP_MM,
    )
    assert res.status == "insufficient_history"
    assert res.baseline_mean is None
    assert res.absolute_anomaly is None
    assert res.percent_of_normal is None
    assert res.standardized_anomaly is None
    assert res.risk_level == AgroClimateRiskLevel.LOW


def test_compute_climate_anomaly_rainfall_deficit_and_surplus():
    """Test rainfall anomaly calculations (absolute, percent of normal, z-score, risk level)."""
    baseline = ClimateBaseline(
        variable=WeatherVariable.PRECIP_MM,
        sample_size=20,
        mean=100.0,
        std=20.0,
        period_start_year=2000,
        period_end_year=2019,
    )

    # Case 1: Severe drought (40 mm observed vs 100 mm baseline)
    drought_res = compute_climate_anomaly(40.0, baseline, WeatherVariable.PRECIP_MM)
    assert drought_res.status == "calculated"
    assert drought_res.absolute_anomaly == -60.0
    assert drought_res.percent_of_normal == 40.0
    assert drought_res.standardized_anomaly == -3.0
    assert drought_res.risk_level == AgroClimateRiskLevel.CRITICAL

    # Case 2: Normal rainfall (105 mm observed)
    normal_res = compute_climate_anomaly(105.0, baseline, WeatherVariable.PRECIP_MM)
    assert normal_res.status == "calculated"
    assert normal_res.absolute_anomaly == 5.0
    assert normal_res.percent_of_normal == 105.0
    assert normal_res.standardized_anomaly == 0.25
    assert normal_res.risk_level == AgroClimateRiskLevel.LOW

    # Case 3: Flood / excess rainfall (175 mm observed)
    flood_res = compute_climate_anomaly(175.0, baseline, WeatherVariable.PRECIP_MM)
    assert flood_res.status == "calculated"
    assert flood_res.absolute_anomaly == 75.0
    assert flood_res.percent_of_normal == 175.0
    assert flood_res.standardized_anomaly == 3.75
    assert flood_res.risk_level == AgroClimateRiskLevel.HIGH


def test_compute_climate_anomaly_temperature():
    """Test temperature anomaly calculation (degrees C delta, no percent of normal)."""
    baseline = ClimateBaseline(
        variable=WeatherVariable.T2M_MAX_C,
        sample_size=15,
        mean=28.0,
        std=1.5,
        period_start_year=2005,
        period_end_year=2019,
    )

    heatwave_res = compute_climate_anomaly(32.5, baseline, WeatherVariable.T2M_MAX_C)
    assert heatwave_res.status == "calculated"
    assert heatwave_res.absolute_anomaly == 4.5
    assert heatwave_res.percent_of_normal is None  # Not meaningful for Celsius degrees
    assert heatwave_res.standardized_anomaly == 3.0
    assert heatwave_res.risk_level == AgroClimateRiskLevel.HIGH


def test_zonal_aggregation_hand_calculated_grid():
    """Criterion: Small 3x3 test raster with hand-calculated aggregate, nodata and coastal mask."""
    # 3x3 grid: 7 valid cells, 2 nodata cells (-9999.0)
    grid_values = [
        10.0,
        20.0,
        30.0,
        -9999.0,
        40.0,
        50.0,
        60.0,
        70.0,
        -9999.0,
    ]
    # Sum of valid cells = 10 + 20 + 30 + 40 + 50 + 60 + 70 = 280.0
    # Valid count = 7, simple mean = 280.0 / 7 = 40.0
    res = aggregate_zonal(
        values=grid_values,
        method=AggregationMethod.ZONAL_MEAN,
        nodata_value=-9999.0,
    )
    assert res.valid_cell_count == 7
    assert res.coverage_ratio == round(7 / 9, 4)
    assert res.value == 40.0
    assert res.effective_method == AggregationMethod.ZONAL_MEAN
    assert res.is_fallback is False


def test_zonal_aggregation_cropland_weighted_strict_fallback():
    """Criterion: Fallback to zonal_mean if cropland_mask is unavailable (ADR-080 veracity)."""
    grid_values = [10.0, 20.0, 30.0, 40.0]
    weights = [0.1, 0.5, 0.2, 0.2]

    # Without verified cropland mask: MUST fallback to zonal_mean
    res_no_mask = aggregate_zonal(
        values=grid_values,
        weights=weights,
        method=AggregationMethod.CROPLAND_WEIGHTED_MEAN,
        cropland_mask_available=False,
    )
    assert res_no_mask.effective_method == AggregationMethod.ZONAL_MEAN
    assert res_no_mask.is_fallback is True
    assert "cropland_mask_unavailable" in (res_no_mask.fallback_reason or "")
    assert res_no_mask.value == 25.0  # (10 + 20 + 30 + 40) / 4 = 25.0

    # With verified cropland mask: executes weighted mean
    # (10*0.1 + 20*0.5 + 30*0.2 + 40*0.2) = 1.0 + 10.0 + 6.0 + 8.0 = 25.0
    weights_skewed = [1.0, 0.0, 0.0, 0.0]
    res_with_mask = aggregate_zonal(
        values=grid_values,
        weights=weights_skewed,
        method=AggregationMethod.CROPLAND_WEIGHTED_MEAN,
        cropland_mask_available=True,
    )
    assert res_with_mask.effective_method == AggregationMethod.CROPLAND_WEIGHTED_MEAN
    assert res_with_mask.is_fallback is False
    assert res_with_mask.value == 10.0  # 100% weight on cell 0
