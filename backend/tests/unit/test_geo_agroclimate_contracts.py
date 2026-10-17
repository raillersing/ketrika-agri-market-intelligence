"""Unit tests for geospatial and agroclimatic contracts (ADR-080, SPECS §26, R4.1)."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ketrika.geo.contracts import (
    BBOX_MADAGASCAR,
    CRS_WGS84,
    MAX_RASTER_FILE_SIZE_BYTES,
    AggregationMethod,
    CropRegime,
    GeoBoundingBox,
    SpatialResolution,
    WeatherForecastRecord,
    WeatherVariable,
    load_crop_calendar,
)
from ketrika.geo.raster import (
    aggregate_zonal,
    clip_raster_bbox,
    compute_dry_spells,
    is_within_madagascar_bbox,
    validate_bbox,
)


def test_geospatial_constants_and_bbox():
    """Verify CRS and Madagascar official bounding box definitions."""
    assert CRS_WGS84 == "EPSG:4326"
    assert BBOX_MADAGASCAR == (43.0, -25.8, 50.8, -11.8)
    assert MAX_RASTER_FILE_SIZE_BYTES == 50 * 1024 * 1024

    # Points inside Madagascar
    assert is_within_madagascar_bbox(47.53, -18.91)  # Antananarivo
    assert is_within_madagascar_bbox(49.40, -18.15)  # Toamasina
    assert is_within_madagascar_bbox(43.67, -23.35)  # Toliara
    assert is_within_madagascar_bbox(49.29, -12.28)  # Antsiranana (Diego)
    assert is_within_madagascar_bbox(48.42, -17.83)  # Lac Alaotra

    # Points outside Madagascar
    assert not is_within_madagascar_bbox(2.35, 48.85)  # Paris
    assert not is_within_madagascar_bbox(36.82, -1.29)  # Nairobi
    assert not is_within_madagascar_bbox(55.45, -20.88)  # La Réunion
    assert not is_within_madagascar_bbox(40.0, -20.0)  # Mozambique Channel off-coast


def test_bounding_box_validation_and_clipping():
    """Verify validation of bounding boxes and clipping to Madagascar boundaries."""
    assert validate_bbox((43.0, -25.8, 50.8, -11.8))
    assert not validate_bbox((50.8, -25.8, 43.0, -11.8))  # min_lon > max_lon
    assert not validate_bbox((43.0, -11.8, 50.8, -25.8))  # min_lat > max_lat
    assert not validate_bbox((43.0, -25.8, 50.8))  # wrong tuple length

    # Global raster clipping to Madagascar bbox
    global_bbox = (-180.0, -90.0, 180.0, 90.0)
    clipped = clip_raster_bbox(global_bbox)
    assert clipped == BBOX_MADAGASCAR

    # Sub-region clipping
    sub_bbox = (45.0, -20.0, 55.0, -10.0)
    clipped_sub = clip_raster_bbox(sub_bbox)
    assert clipped_sub == (45.0, -20.0, 50.8, -11.8)

    # Disjoint bbox must raise ValueError
    europe_bbox = (-10.0, 35.0, 30.0, 60.0)
    with pytest.raises(ValueError, match="does not intersect"):
        clip_raster_bbox(europe_bbox)


def test_geo_bounding_box_pydantic():
    """Verify GeoBoundingBox pydantic schema validation."""
    box = GeoBoundingBox(min_lon=44.0, min_lat=-22.0, max_lon=49.0, max_lat=-15.0)
    assert box.intersects_madagascar()

    foreign_box = GeoBoundingBox(min_lon=10.0, min_lat=10.0, max_lon=20.0, max_lat=20.0)
    assert not foreign_box.intersects_madagascar()

    with pytest.raises(ValidationError):
        # max_lon <= min_lon
        GeoBoundingBox(min_lon=49.0, min_lat=-22.0, max_lon=44.0, max_lat=-15.0)


def test_zonal_aggregation_veracity_and_fallbacks():
    """Verify zonal aggregation and strict fallback when cropland_mask is unavailable."""
    # 1. Simple unweighted zonal mean with nodata filtering
    values = [10.0, 20.0, 30.0, -9999.0, float("nan")]
    res = aggregate_zonal(values, method=AggregationMethod.ZONAL_MEAN, nodata_value=-9999.0)
    assert res.value == 20.0  # (10+20+30)/3
    assert res.valid_cell_count == 3
    assert res.coverage_ratio == 0.6  # 3/5
    assert not res.is_fallback
    assert res.effective_method == AggregationMethod.ZONAL_MEAN

    # 2. Cropland weighted mean WITHOUT mask -> strict fallback to zonal_mean (ADR-080)
    res_fallback = aggregate_zonal(
        values=[10.0, 20.0, 30.0],
        weights=[0.8, 0.1, 0.1],
        method=AggregationMethod.CROPLAND_WEIGHTED_MEAN,
        cropland_mask_available=False,
    )
    assert res_fallback.is_fallback is True
    assert res_fallback.effective_method == AggregationMethod.ZONAL_MEAN
    assert res_fallback.value == 20.0  # Unweighted mean (10+20+30)/3 = 20.0
    assert "cropland_mask_unavailable" in (res_fallback.fallback_reason or "")

    # 3. Cropland weighted mean WITH verified mask -> genuine weighted mean
    res_weighted = aggregate_zonal(
        values=[10.0, 20.0, 30.0],
        weights=[0.8, 0.1, 0.1],
        method=AggregationMethod.CROPLAND_WEIGHTED_MEAN,
        cropland_mask_available=True,
    )
    assert not res_weighted.is_fallback
    assert res_weighted.effective_method == AggregationMethod.CROPLAND_WEIGHTED_MEAN
    # 10*0.8 + 20*0.1 + 30*0.1 = 8 + 2 + 3 = 13.0
    assert res_weighted.value == 13.0


def test_weather_forecast_record_contract():
    """Verify WeatherForecastRecord strictly enforces validity windows and quantile order."""
    now_utc = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
    future_start = datetime(2026, 10, 17, 0, 0, tzinfo=UTC)
    future_end = datetime(2026, 10, 17, 23, 59, tzinfo=UTC)

    rec = WeatherForecastRecord(
        source_record_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        issued_at=now_utc,
        valid_from=future_start,
        valid_to=future_end,
        horizon_hours=36,
        variable=WeatherVariable.PRECIP_MM,
        model_name="ecmwf_ifs",
        predicted_value=12.5,
        predicted_p10=5.0,
        predicted_p90=25.0,
        method=AggregationMethod.ZONAL_MEAN,
        spatial_resolution=SpatialResolution.ERA5_010,
        unit="mm",
    )
    assert rec.variable == WeatherVariable.PRECIP_MM
    assert rec.horizon_hours == 36
    assert rec.predicted_value == 12.5

    # Rejection if valid_to < valid_from
    with pytest.raises(ValidationError, match="valid_to"):
        WeatherForecastRecord(
            source_record_id=uuid.uuid4(),
            location_id=uuid.uuid4(),
            issued_at=now_utc,
            valid_from=future_end,
            valid_to=future_start,  # earlier!
            horizon_hours=36,
            variable=WeatherVariable.PRECIP_MM,
            model_name="ecmwf_ifs",
            predicted_value=12.5,
            method=AggregationMethod.ZONAL_MEAN,
            unit="mm",
        )

    # Rejection if predicted_p90 < predicted_p10
    with pytest.raises(ValidationError, match="predicted_p90"):
        WeatherForecastRecord(
            source_record_id=uuid.uuid4(),
            location_id=uuid.uuid4(),
            issued_at=now_utc,
            valid_from=future_start,
            valid_to=future_end,
            horizon_hours=36,
            variable=WeatherVariable.PRECIP_MM,
            model_name="ecmwf_ifs",
            predicted_value=12.5,
            predicted_p10=20.0,
            predicted_p90=10.0,  # inverted quantiles!
            method=AggregationMethod.ZONAL_MEAN,
            unit="mm",
        )


def test_crop_calendar_taxonomy():
    """Verify crop calendar taxonomy loading, validation and key commodity coverage."""
    records = load_crop_calendar()
    assert len(records) >= 8

    commodities = {r.product_code for r in records}
    assert "RICE_PADDY" in commodities
    assert "MAIZE_GRAIN" in commodities
    assert "CASSAVA_FRESH" in commodities

    # Check Lac Alaotra irrigated rice
    alaotra_cycles = [r for r in records if r.zone_code == "ZONE_ALAOTRA"]
    assert len(alaotra_cycles) >= 1
    assert alaotra_cycles[0].crop_regime == CropRegime.IRRIGATED
    assert alaotra_cycles[0].harvest_start_month == 5
    assert alaotra_cycles[0].harvest_end_month == 6

    # Check Grand Sud maize
    sud_maize = [r for r in records if r.zone_code == "ZONE_SUD" and r.crop == "MAIZE"]
    assert len(sud_maize) >= 1
    assert sud_maize[0].crop_regime == CropRegime.RAINFED
    assert sud_maize[0].planting_start_month == 11
    assert sud_maize[0].harvest_start_month == 3

    # All cycles must have valid month bounds [1, 12] and official source
    for rec in records:
        assert 1 <= rec.planting_start_month <= 12
        assert 1 <= rec.planting_end_month <= 12
        assert 1 <= rec.harvest_start_month <= 12
        if rec.eligible_for_alerts:
            assert rec.source_reference != ""
            assert rec.verified is True
        else:
            assert rec.verified is False


def test_dry_spells_computation():
    """Verify meteorological dry spells calculation (consecutive days below threshold)."""
    # 3 dry, 2 wet, 4 dry, 1 wet, 2 dry
    precip = [0.0, 0.5, 0.2, 15.0, 22.0, 0.0, 0.0, 0.1, 0.8, 5.0, 0.0, 0.4]
    spells = compute_dry_spells(precip, threshold_mm=1.0)
    assert spells == [3, 4, 2]

    # No rain at all for 10 days
    assert compute_dry_spells([0.0] * 10, threshold_mm=1.0) == [10]

    # Constant rain every day
    assert compute_dry_spells([5.0] * 10, threshold_mm=1.0) == []


def test_sqlalchemy_models_instantiation():
    """Verify ORM models instantiate all required columns matching Alembic schema."""
    from ketrika.core.models.db import CropCalendar, WeatherForecast, WeatherObservation

    now_utc = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
    loc_id = uuid.uuid4()
    prod_id = uuid.uuid4()
    sr_id = uuid.uuid4()

    obs = WeatherObservation(
        source_record_id=sr_id,
        location_id=loc_id,
        date=now_utc.date(),
        variable="precip_mm",
        value=15.2,
        method="zonal_mean",
        provider="chirps",
        stage="final",
        spatial_resolution="0.05_deg",
        coverage_ratio=0.985,
        raster_source_record_id=sr_id,
    )
    assert obs.stage == "final"
    assert obs.spatial_resolution == "0.05_deg"
    assert obs.coverage_ratio == 0.985

    forecast = WeatherForecast(
        source_record_id=sr_id,
        location_id=loc_id,
        issued_at=now_utc,
        valid_from=now_utc,
        valid_to=now_utc,
        horizon_hours=24,
        variable="precip_mm",
        model_name="ecmwf_ifs",
        predicted_value=10.5,
        method="zonal_mean",
        unit="mm",
    )
    assert forecast.variable == "precip_mm"
    assert forecast.horizon_hours == 24

    cal = CropCalendar(
        product_id=prod_id,
        location_id=loc_id,
        season_name="asara",
        crop_regime="rainfed",
        planting_start_month=11,
        planting_end_month=1,
        growing_start_month=1,
        growing_end_month=5,
        harvest_start_month=5,
        harvest_end_month=7,
        peak_harvest_month=6,
        source_reference="MinAE/FAO 2021",
        verified=True,
    )
    assert cal.season_name == "asara"
    assert cal.harvest_start_month == 5
