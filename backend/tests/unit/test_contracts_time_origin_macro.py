"""Unit and contract tests for time, origin, and macroeconomic data (R2.1, ADR-069, SPECS §8, §19).

Validates:
1. MacroRecord natural key and model integrity.
2. Loader with append-only supersession and idempotent skipping.
3. Contract C2: first_available_at cannot be backdated and falls back conservative to fetched_at.
4. Non-regression of raw price observations and weather revisions without destructive overwrite.
5. REST API /v1/macro contract and JSON response structure.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from ketrika.api.main import app
from ketrika.connectors.records import MacroRecord, PriceRecord, WeatherRecord
from ketrika.connectors.runner import (
    load_macro_record_with_supersession,
    load_record_with_supersession,
)
from ketrika.core.db import get_db
from ketrika.core.models.db import (
    MacroObservation,
    SourceRecord,
)

pytestmark = pytest.mark.usefixtures("authenticated_unit_reader")


def test_macro_record_natural_key_determinism() -> None:
    """Criterion 1: MacroRecord generates a deterministic natural key including indicator, scope, and vintage."""
    rec1 = MacroRecord(
        indicator_code="GDP_NOMINAL_MGA",
        indicator_name="PIB Nominal de Madagascar",
        frequency="annual",
        unit="MGA",
        geo_scope="national",
        period_start=date(2023, 1, 1),
        period_end=date(2023, 12, 31),
        value=72500000000000.0,
        vintage="final",
    )
    rec2 = MacroRecord(
        indicator_code="GDP_NOMINAL_MGA",
        indicator_name="PIB Nominal de Madagascar",
        frequency="annual",
        unit="MGA",
        geo_scope="national",
        period_start=date(2023, 1, 1),
        period_end=date(2023, 12, 31),
        value=72500000000000.0,
        vintage="final",
    )
    rec_prov = MacroRecord(
        indicator_code="GDP_NOMINAL_MGA",
        indicator_name="PIB Nominal de Madagascar",
        frequency="annual",
        unit="MGA",
        geo_scope="national",
        period_start=date(2023, 1, 1),
        period_end=date(2023, 12, 31),
        value=71000000000000.0,
        vintage="provisional",
    )

    nk1 = rec1.compute_natural_key("instat_macro")
    nk2 = rec2.compute_natural_key("instat_macro")
    nk_prov = rec_prov.compute_natural_key("instat_macro")

    assert nk1 == nk2
    assert nk1 != nk_prov  # Distinct vintage yields distinct natural key


def test_macro_record_loader_insertion_and_idempotence() -> None:
    """Criterion 2: MacroRecord loading is inserted first, then skipped idempotently on identical replay."""
    session = MagicMock()
    session.scalar.return_value = False
    source_record_id = uuid.uuid4()
    source_id = "instat_macro"

    # Run 1: initial insertion
    session.execute.return_value.scalar_one_or_none.return_value = None

    rec = MacroRecord(
        indicator_code="FX_USD_MGA",
        indicator_name="Taux de change USD/MGA MID",
        frequency="daily",
        unit="MGA",
        geo_scope="national",
        period_start=date(2024, 6, 1),
        period_end=date(2024, 6, 1),
        value=4550.0,
        vintage="final",
    )

    status1, obs_id1 = load_record_with_supersession(session, rec, source_id, source_record_id)
    assert status1 == "inserted"
    assert isinstance(obs_id1, uuid.UUID)
    session.add.assert_called_once()
    added_obs = session.add.call_args[0][0]
    assert isinstance(added_obs, MacroObservation)
    assert added_obs.indicator_code == "FX_USD_MGA"
    assert added_obs.value == 4550.0

    # Run 2: identical replay
    existing_obs = added_obs
    session.execute.return_value.scalar_one_or_none.return_value = existing_obs

    status2, obs_id2 = load_record_with_supersession(session, rec, source_id, source_record_id)
    assert status2 == "idempotent_skipped"
    assert obs_id2 == existing_obs.observation_id


def test_contract_c2_time_availability_conservative_fallback() -> None:
    """Criterion 3 (Contract C2): first_available_at cannot be backdated; falls back conservative to fetched_at."""
    session = MagicMock()
    session.scalar.return_value = False
    source_record_id = uuid.uuid4()
    source_id = "bcm_macro"
    fetched_timestamp = datetime(2024, 10, 1, 12, 0, 0, tzinfo=UTC)

    mock_sr = MagicMock(spec=SourceRecord)
    mock_sr.fetched_at = fetched_timestamp
    session.get.return_value = mock_sr
    session.execute.return_value.scalar_one_or_none.return_value = None

    # Record has NO explicit first_available_at (cannot backdate from period_start)
    rec = MacroRecord(
        indicator_code="POLICY_RATE_PCT",
        indicator_name="Taux directeur BCM",
        frequency="adhoc",
        unit="pct",
        geo_scope="national",
        period_start=date(2023, 5, 1),  # Historical period
        period_end=date(2023, 5, 1),
        value=9.0,
        first_available_at=None,
    )

    status, _ = load_macro_record_with_supersession(session, rec, source_id, source_record_id)
    assert status == "inserted"
    added_obs = session.add.call_args[0][0]
    # first_available_at is conservative fetched_at, NOT 2023-05-01
    assert added_obs.first_available_at == fetched_timestamp


def test_macro_supersession_on_revised_value() -> None:
    """Criterion 4: Revision of macroeconomic estimate supersedes previous observation non-destructively."""
    session = MagicMock()
    session.scalar.return_value = False
    source_record_id = uuid.uuid4()
    source_id = "instat_macro"

    initial_obs = MacroObservation(
        observation_id=uuid.uuid4(),
        source_record_id=source_record_id,
        natural_key="test_nk",
        indicator_code="GDP_GROWTH_PCT",
        indicator_name="Croissance du PIB",
        frequency="annual",
        unit="pct",
        geo_scope="national",
        period_start=date(2023, 1, 1),
        period_end=date(2023, 12, 31),
        value=4.0,
        vintage="provisional",
        observed_or_imputed="observed",
        first_available_at=datetime(2024, 3, 1, tzinfo=UTC),
        extraction_method="deterministic",
        confidence=1.0,
        superseded_by=None,
    )
    session.execute.return_value.scalar_one_or_none.return_value = initial_obs

    revised_rec = MacroRecord(
        indicator_code="GDP_GROWTH_PCT",
        indicator_name="Croissance du PIB",
        frequency="annual",
        unit="pct",
        geo_scope="national",
        period_start=date(2023, 1, 1),
        period_end=date(2023, 12, 31),
        value=4.2,  # Revised value
        vintage="final",
    )

    status, new_id = load_macro_record_with_supersession(
        session, revised_rec, source_id, source_record_id
    )
    assert status == "superseded"
    assert new_id != initial_obs.observation_id
    session.execute.assert_called()  # update on initial_obs setting superseded_by
    session.add.assert_called()  # new row added


def test_non_regression_raw_price_and_weather_models() -> None:
    """Criterion 5: Raw fields on PriceObservation and WeatherObservation remain intact and unaffected."""
    # Ensure PriceRecord retains price_raw, unit_raw, currency_raw without alteration
    price_rec = PriceRecord(
        product_raw="Riz blanc Tsipala",
        variety="Tsipala",
        actor_level="retail",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 7),
        price_raw="2 800 Ar/kg",
        price_value=2800.0,
        unit_raw="kg",
        currency_raw="MGA",
        observed_or_imputed="observed",
    )
    assert price_rec.price_raw == "2 800 Ar/kg"
    assert price_rec.currency_raw == "MGA"

    # Ensure WeatherRecord retains value_raw and provenance without alteration
    weather_rec = WeatherRecord(
        location_raw="MDG1101",
        date=date(2024, 1, 1),
        variable="precip_mm",
        value=15.2,
        value_raw="15.20",
        provider="nasa_power",
    )
    assert weather_rec.value_raw == "15.20"
    assert weather_rec.period_start == date(2024, 1, 1)


def test_api_v1_macro_route_contract() -> None:
    """Criterion 6: GET /v1/macro returns typed JSON array matching MacroItem schema."""
    client = TestClient(app)

    mock_row = (
        uuid.uuid4(),
        "GDP_NOMINAL_MGA",
        "PIB Nominal de Madagascar",
        "national",
        "annual",
        "MGA",
        None,
        date(2023, 1, 1),
        date(2023, 12, 31),
        "final",
        72500000000000.0,
        "72 500 Mrd Ar",
        "observed",
        datetime(2024, 10, 1, 12, 0, 0, tzinfo=UTC),
        datetime(2024, 9, 30, 0, 0, 0, tzinfo=UTC),
        "instat_macro",
    )

    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = [mock_row]

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = client.get("/v1/macro?indicator=GDP_NOMINAL_MGA&vintage=final")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        item = data[0]
        assert item["indicator_code"] == "GDP_NOMINAL_MGA"
        assert item["geo_scope"] == "national"
        assert item["frequency"] == "annual"
        assert item["unit"] == "MGA"
        assert item["value"] == 72500000000000.0
        assert item["value_raw"] == "72 500 Mrd Ar"
        assert item["vintage"] == "final"
        assert item["observed_or_imputed"] == "observed"
        assert item["sources"] == ["instat_macro"]
    finally:
        app.dependency_overrides.clear()
