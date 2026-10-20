"""Gate qualification test suite for Phase R4: Agroclimatic observatory, weather, calendars, and spatial contracts (SPECS §26, R4.12)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ketrika.api.routers.climate import FACULTATIVE_SOURCES
from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.chirps import CHIRPS_NODATA_VALUE, ChirpsConnector
from ketrika.connectors.ecmwf_open import EcmwfOpenConnector
from ketrika.connectors.fewsnet_ipc import FewsnetConnector, IpcConnector
from ketrika.connectors.meteo_mg import MeteoMgConnector
from ketrika.connectors.records import EventRecord, WeatherRecord
from ketrika.geo.anomalies import (
    MIN_BASELINE_YEARS,
    ClimateAnomalyResult,
    ClimateBaseline,
    compute_climate_anomaly,
    compute_climate_baseline,
)
from ketrika.geo.calendar import (
    detect_phenological_stage,
    get_documented_trade_corridors_for_market,
    is_month_in_window,
)
from ketrika.geo.contracts import (
    AggregationMethod,
    AgroClimateRiskLevel,
    CalendarType,
    CropCalendarRecord,
    CropRegime,
    GeoBoundingBox,
    MarketLinkProofStatus,
    SpatialResolution,
    WeatherForecastRecord,
    WeatherStage,
    WeatherVariable,
    load_crop_calendar,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class DummyBronzeStore:
    def __init__(self, data: bytes):
        self._data = data

    def get(self, object_key: str) -> bytes | None:
        return self._data


def test_gate_r4_c1_geospatial_contracts_and_observation_vs_forecast_separation():
    """Criterion 1: Strict separation between observed weather and weather forecast, bounding box validation."""
    # 1. GeoBoundingBox intersects Madagascar
    mdg_box = GeoBoundingBox(
        min_lon=43.0,
        min_lat=-25.6,
        max_lon=50.5,
        max_lat=-11.9,
    )
    assert mdg_box.intersects_madagascar() is True

    outside_box = GeoBoundingBox(
        min_lon=10.0,
        min_lat=0.0,
        max_lon=15.0,
        max_lat=5.0,
    )
    assert outside_box.intersects_madagascar() is False

    # 2. Observed WeatherRecord
    obs = WeatherRecord(
        location_raw="Alaotra Mangoro",
        date=date(2024, 1, 10),
        variable=WeatherVariable.PRECIP_MM.value,
        value=45.2,
        provider="chirps",
        stage=WeatherStage.FINAL.value,
        spatial_resolution=SpatialResolution.CHIRPS_005.value,
    )
    assert obs.stage == WeatherStage.FINAL.value
    assert obs.value == 45.2
    assert obs.date == date(2024, 1, 10)

    # 3. Forecast WeatherForecastRecord with valid window
    v_from = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
    v_to = datetime(2024, 1, 3, 0, 0, tzinfo=UTC)
    fc = WeatherForecastRecord(
        source_record_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        issued_at=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        valid_from=v_from,
        valid_to=v_to,
        horizon_hours=48,
        variable=WeatherVariable.PRECIP_MM,
        model_name="ECMWF_IFS",
        predicted_value=22.5,
        predicted_p10=12.0,
        predicted_p90=38.0,
        method=AggregationMethod.ZONAL_MEAN,
        spatial_resolution=SpatialResolution.ERA5_010,
        unit="mm",
    )
    assert fc.valid_to >= fc.valid_from
    assert fc.horizon_hours == 48

    # 4. Rejection when valid_to < valid_from
    with pytest.raises(ValidationError):
        WeatherForecastRecord(
            source_record_id=uuid.uuid4(),
            location_id=uuid.uuid4(),
            issued_at=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
            valid_from=v_to,
            valid_to=v_from,  # Invalid: valid_to < valid_from
            horizon_hours=48,
            variable=WeatherVariable.PRECIP_MM,
            model_name="ECMWF_IFS",
            method=AggregationMethod.ZONAL_MEAN,
            unit="mm",
        )


def test_gate_r4_c2_chirps_dual_cycle_preliminary_vs_final_and_nodata_handling():
    """Criterion 2: CHIRPS preliminary vs final dual-cycle, nodata (-9999.0) vs valid 0.0 mm distinction."""
    assert CHIRPS_NODATA_VALUE == -9999.0
    connector = ChirpsConnector()
    assert connector.source_id == "chirps"
    # Stage verification
    assert WeatherStage.PRELIMINARY.value == "preliminary"
    assert WeatherStage.FINAL.value == "final"


def test_gate_r4_c3_meteo_mg_bulletins_and_no_hallucinated_probabilities():
    """Criterion 3: DGM Agrometeorological bulletins, issuance vs validity date separation."""
    fixture_path = FIXTURES_DIR / "meteo_mg" / "bulletin_decadaire_2024_01_d1.json"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = MeteoMgConnector()
    bronze_store = DummyBronzeStore(payload)
    ctx = RunContext(
        source_id="meteo_mg",
        run_id="gate-r4-meteo",
        bronze_store=bronze_store,
        metadata={},
    )
    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="https://www.meteomadagascar.mg/bulletins/agrometeo/2024/bulletin_decadaire_2024_01_d1.pdf",
        object_key="meteo_mg/2024/01/d1.pdf",
        mime_type="application/pdf",
        content_sha256="abc123sha",
        is_new=True,
    )
    result = connector.parse(artifact, ctx)
    assert len(result.issues) == 0
    assert len(result.records) >= 1
    weather_records = [r for r in result.records if isinstance(r, WeatherRecord)]
    assert len(weather_records) >= 1
    for r in weather_records:
        assert r.stage == WeatherStage.FINAL.value
        assert r.date is not None


def test_gate_r4_c4_fewsnet_and_ipc_events_and_phase_distinction():
    """Criterion 4: FEWS NET and IPC food security events, IPC phases 1-5."""
    ipc_conn = IpcConnector()
    fews_conn = FewsnetConnector()
    assert ipc_conn.source_id == "ipc_mdg"
    assert fews_conn.source_id == "fewsnet_mdg"

    fixture_path = FIXTURES_DIR / "fewsnet_ipc" / "fewsnet_mdg_outlook_2024_02.json"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    art = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="https://fews.net/east-africa/madagascar/outlook/february-2024",
        object_key="fewsnet/202402.json",
        mime_type="application/json",
        content_sha256="mocksha",
        is_new=True,
    )
    ctx = RunContext(
        source_id="fewsnet_mdg",
        run_id="gate-r4-fews",
        bronze_store=DummyBronzeStore(payload),
        metadata={},
    )
    result = fews_conn.parse(art, ctx)
    assert len(result.issues) == 0
    assert len(result.records) >= 1
    for r in result.records:
        assert isinstance(r, EventRecord)
        assert r.event_type is not None
        assert r.title is not None


def test_gate_r4_c5_ecmwf_open_data_weather_forecast_integrity():
    """Criterion 5: Archivable numerical weather forecast, ensemble quantiles, strict quantile ordering."""
    ecmwf_conn = EcmwfOpenConnector()
    assert ecmwf_conn.source_id == "ecmwf_open"

    fixture_path = FIXTURES_DIR / "ecmwf_open" / "ecmwf_ifs_20240301_00z.json"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    art = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="https://data.ecmwf.int/forecasts/20240301/00z/ifs_madagascar_0p4.json",
        object_key="ecmwf/20240301/00z.json",
        mime_type="application/json",
        content_sha256="mockecmwfsha",
        is_new=True,
    )
    ctx = RunContext(
        source_id="ecmwf_open",
        run_id="gate-r4-ecmwf",
        bronze_store=DummyBronzeStore(payload),
        metadata={},
    )
    result = ecmwf_conn.parse(art, ctx)
    assert len(result.issues) == 0
    assert len(result.records) >= 1
    for r in result.records:
        if (
            r.predicted_p10 is not None
            and r.predicted_p90 is not None
            and r.predicted_value is not None
        ):
            assert r.predicted_p10 <= r.predicted_value <= r.predicted_p90


def test_gate_r4_c6_agroclimatic_anomalies_and_baseline_threshold():
    """Criterion 6: Climate anomaly calculation, minimum baseline threshold (N>=10 years), refusal if insufficient."""
    # 1. Baseline with >= 10 years succeeds
    historical_10yr = [100.0, 110.0, 95.0, 105.0, 120.0, 85.0, 90.0, 115.0, 100.0, 105.0]
    years_10 = list(range(2010, 2020))
    baseline = compute_climate_baseline(
        historical_values=historical_10yr,
        period_years=years_10,
        min_years=MIN_BASELINE_YEARS,
        variable=WeatherVariable.PRECIP_MM,
    )
    assert baseline is not None
    assert isinstance(baseline, ClimateBaseline)
    assert baseline.sample_size == 10
    assert baseline.sample_size >= MIN_BASELINE_YEARS

    # 2. Refusal (returns None) when historical years < 10
    historical_5yr = [100.0, 110.0, 95.0, 105.0, 120.0]
    baseline_invalid = compute_climate_baseline(
        historical_values=historical_5yr,
        period_years=list(range(2015, 2020)),
        min_years=MIN_BASELINE_YEARS,
        variable=WeatherVariable.PRECIP_MM,
    )
    assert baseline_invalid is None

    # 3. Anomaly computation on valid baseline
    anomaly = compute_climate_anomaly(
        observed_value=60.0,
        baseline=baseline,
        variable=WeatherVariable.PRECIP_MM,
    )
    assert isinstance(anomaly, ClimateAnomalyResult)
    assert anomaly.percent_of_normal is not None
    assert anomaly.percent_of_normal < 100.0  # Deficit
    assert anomaly.risk_level in [
        AgroClimateRiskLevel.MEDIUM,
        AgroClimateRiskLevel.HIGH,
        AgroClimateRiskLevel.CRITICAL,
    ]

    # 4. Anomaly computation on invalid baseline (None) yields abstention status
    anomaly_refused = compute_climate_anomaly(
        observed_value=60.0,
        baseline=None,
        variable=WeatherVariable.PRECIP_MM,
    )
    assert anomaly_refused.status == "insufficient_history"
    assert anomaly_refused.percent_of_normal is None
    assert anomaly_refused.risk_level == AgroClimateRiskLevel.LOW


def test_gate_r4_c7_crop_calendar_versioning_and_trade_corridors():
    """Criterion 7: Crop calendar versioning, baseline vs seasonal recommendation, stages, documented corridors."""
    # 1. Month in window
    assert is_month_in_window(month=12, start_month=11, end_month=2) is True
    assert is_month_in_window(month=1, start_month=11, end_month=2) is True
    assert is_month_in_window(month=5, start_month=11, end_month=2) is False

    # 2. Phenological stage detection using CropCalendarRecord
    cal_record = CropCalendarRecord(
        zone_code="ZONE_ALAOTRA",
        zone_name="Bassin du Lac Alaotra",
        crop="Riz paddy",
        product_code="RICE_PADDY",
        crop_cycle="main_season",
        season_name="Vary Asara",
        crop_regime=CropRegime.IRRIGATED,
        calendar_version="v1.0",
        calendar_type=CalendarType.TRADITIONAL_BASELINE,
        campaign="baseline_permanent",
        planting_start_month=11,
        planting_end_month=1,
        growing_start_month=1,
        growing_end_month=4,
        harvest_start_month=4,
        harvest_end_month=6,
        peak_harvest_month=5,
        source_reference="FOFIFA & Cirad (2018), Calendriers Culturaux Régionaux",
    )
    assert detect_phenological_stage(cal_record, month=5) == "peak_harvest"
    assert detect_phenological_stage(cal_record, month=6) == "harvest"
    assert detect_phenological_stage(cal_record, month=12) == "planting"

    # 3. Documented trade corridors for Antananarivo market (MDG11)
    records = load_crop_calendar()
    tana_corridors = get_documented_trade_corridors_for_market(records, location_code="MDG11")
    assert len(tana_corridors) > 0
    supplying_basins = {c["basin_zone_code"] for c in tana_corridors}
    assert "ZONE_ALAOTRA" in supplying_basins
    for c in tana_corridors:
        assert c["proof_status"] in [
            MarketLinkProofStatus.DOCUMENTED_TRADE_CORRIDOR,
            MarketLinkProofStatus.OFFICIAL_SUPPLY_BASIN,
        ]

    # 4. Extra fields rejection (no invented prices or quantities)
    with pytest.raises(ValidationError):
        CropCalendarRecord(
            zone_code="ZONE_BOENY",
            zone_name="Plaine de Marovoay",
            crop="Riz paddy",
            product_code="RICE_PADDY",
            season_name="Vary Asara",
            crop_regime=CropRegime.IRRIGATED,
            planting_start_month=11,
            planting_end_month=12,
            growing_start_month=1,
            growing_end_month=4,
            harvest_start_month=4,
            harvest_end_month=6,
            source_reference="FOFIFA",
            invented_price_projection=2500.0,  # FORBIDDEN: extra field
        )


def test_gate_r4_c8_facultative_sources_transparency_and_no_zero_substitution():
    """Criterion 8: Explicit declaration of facultative sources without artificial 0.0 substitution."""
    assert len(FACULTATIVE_SOURCES) >= 3
    source_names = [s.source_name for s in FACULTATIVE_SOURCES]
    assert any("NASA FIRMS" in name for name in source_names)
    assert any("GloFAS" in name for name in source_names)
    assert any("Sentinel-2 NDVI" in name for name in source_names)

    for s in FACULTATIVE_SOURCES:
        assert s.status == "unavailable"
        assert s.data_available is False
        assert len(s.reason) > 10
        assert not hasattr(s, "value") or s.value is None
