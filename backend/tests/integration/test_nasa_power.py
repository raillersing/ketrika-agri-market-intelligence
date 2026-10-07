"""Integration test for NASA POWER connector backfill, DQ and offline rebuild (CC3-CC6, T3.4)."""

import json
import uuid
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ketrika.connectors.base import RunContext
from ketrika.connectors.nasa_power import NasaPowerConnector
from ketrika.connectors.runner import execute_connector_pipeline
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import check_db_connection
from ketrika.core.http import PoliteHttpClient
from ketrika.core.models.db import Location, SourceRecord, WeatherObservation
from ketrika.core.policy import PolicyEngine
from ketrika.core.registry import find_repo_root
from ketrika.core.settings import get_settings
from ketrika.pipelines.rebuild import rebuild_database, wipe_silver_gold_tables

FIXTURE_PATH = (
    find_repo_root()
    / "backend"
    / "tests"
    / "fixtures"
    / "nasa_power"
    / "nasa_power_point_sample.json"
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


@pytest.fixture
def sample_payload() -> dict[str, Any]:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


@pytest.mark.integration
def test_nasa_power_backfill_dq_and_rebuild_lifecycle(httpserver, db_session, sample_payload: dict):
    """Verify CC3-CC6: backfill covering 100% of districts, DQ checks, and offline rebuild."""
    wipe_silver_gold_tables(db_session)
    db_session.commit()

    # Query all admin_level = 2 districts in database
    district_stmt = select(Location).where(Location.admin_level == 2).order_by(Location.pcode)
    db_districts = list(db_session.execute(district_stmt).scalars().all())
    assert len(db_districts) >= 3, "Expected at least 3 admin2 districts in ref.location"

    run_tag = uuid.uuid4().hex[:8]
    urls_info = []

    # Coordinate mapping for sample districts
    district_coords = {
        "MDG1101": [47.525, -18.924, 1280.0],
        "MDG1201": [47.025, -19.875, 1500.0],
        "MDG3101": [49.410, -18.150, 10.0],
    }

    for district in db_districts:
        pcode = district.pcode or "MDG1101"
        coords = district_coords.get(pcode, [47.5, -18.9, 1000.0])

        dist_payload = json.loads(json.dumps(sample_payload))
        dist_payload["geometry"]["coordinates"] = coords
        dist_payload["properties"]["district_pcode"] = pcode
        dist_payload["properties"]["district_name"] = district.name
        dist_payload["test_run_tag"] = run_tag

        path = f"/nasa_power_{run_tag}/{pcode}.json"
        httpserver.expect_request(path).respond_with_data(
            json.dumps(dist_payload), content_type="application/json"
        )
        url = httpserver.url_for(path)

        urls_info.append(
            {
                "url": url,
                "partition_key": f"{pcode}_daily",
                "hints": {
                    "district_pcode": pcode,
                    "district_name": district.name,
                    "longitude": str(coords[0]),
                    "latitude": str(coords[1]),
                },
            }
        )

    bronze_store = BronzeStore()
    policy = PolicyEngine()
    http_client = PoliteHttpClient(policy_engine=policy)
    connector = NasaPowerConnector()

    ctx = RunContext(
        source_id="nasa_power",
        bronze_store=bronze_store,
        http_client=http_client,
        policy_engine=policy,
        metadata={"urls": urls_info},
    )

    # 1. CC3: Backfill initial run
    stats1 = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()

    # 36 records per district * N districts (e.g. 3 districts = 108 records)
    expected_inserted = len(db_districts) * 36
    assert stats1["n_inserted"] == expected_inserted
    assert stats1["n_new_artifacts"] == len(db_districts)

    # 2. Check active weather observations in Silver
    obs_stmt = (
        select(WeatherObservation)
        .join(SourceRecord, WeatherObservation.source_record_id == SourceRecord.source_record_id)
        .where(SourceRecord.source_id == "nasa_power")
    )
    weather_obs = list(db_session.execute(obs_stmt).scalars().all())
    assert len(weather_obs) == expected_inserted

    # 3. CC4: Data Quality Checks
    # Check 1: 100% of districts have observations (T3.4 acceptance criterion)
    covered_location_ids = {o.location_id for o in weather_obs}
    expected_location_ids = {d.location_id for d in db_districts}
    assert covered_location_ids == expected_location_ids, "Not all districts are covered"

    # Check 2: 100% Bronze provenance
    assert all(o.source_record_id is not None for o in weather_obs)

    # Check 3: Physical ranges sanity
    for o in weather_obs:
        assert o.value is not None
        val = float(o.value)
        if o.variable == "precip_mm":
            assert val >= 0.0, f"Negative precipitation: {val}"
        elif o.variable == "rh2m_pct":
            assert 0.0 <= val <= 100.0, f"Humidity out of bounds: {val}"
        elif o.variable in ("t2m_max_c", "t2m_min_c"):
            assert -10.0 <= val <= 50.0, f"Temperature out of bounds: {val}"

    # 4. Idempotence: second run adds 0 rows
    stats2 = execute_connector_pipeline(connector=connector, ctx=ctx, session=db_session)
    db_session.commit()
    assert stats2["n_inserted"] == 0
    assert stats2["n_skipped"] == expected_inserted

    # 5. CC6: Offline rebuild stable verification
    rebuild_stats = rebuild_database(session=db_session, offline=True, source_id="nasa_power")
    assert rebuild_stats["source_records_replayed"] >= len(db_districts)

    obs_after = list(db_session.execute(obs_stmt).scalars().all())
    assert len(obs_after) == expected_inserted
    covered_after = {o.location_id for o in obs_after}
    assert covered_after == expected_location_ids
