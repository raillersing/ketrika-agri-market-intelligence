"""Isolated weather loader checks; SQL/history qualification is separate."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from ketrika.connectors.records import WeatherRecord
from ketrika.connectors.runner import load_weather_record_with_supersession
from ketrika.core.models.db import Location, WeatherObservation
from ketrika.core.provenance import ProofError, verify_cells
from ketrika.core.provenance_audit import bind_observation


def record() -> WeatherRecord:
    return WeatherRecord(
        location_raw="TEST-LOCATION",
        date=date(2026, 10, 1),
        variable="precip_mm",
        value=1.25,
        value_raw="1.250",
        provider="synthetic",
        evidence={"test": "synthetic"},
    )


def session_for(current: WeatherObservation | None = None) -> MagicMock:
    session = MagicMock(spec=Session)
    session.scalar.return_value = False
    location = Location(location_id=uuid4(), name="TEST-LOCATION", admin_level=2)
    first = MagicMock()
    first.scalars.return_value.first.return_value = location
    second = MagicMock()
    second.scalar_one_or_none.return_value = current
    session.execute.side_effect = [first, second, MagicMock()]
    return session


def inserted(session: MagicMock) -> WeatherObservation:
    value = session.add.call_args.args[0]
    assert isinstance(value, WeatherObservation)
    return value


def test_weather_stores_proof_and_raw_without_mutating_the_record() -> None:
    candidate = record()
    source_record_id = uuid4()
    session = session_for()
    status, identifier = load_weather_record_with_supersession(
        session, candidate, "test", source_record_id
    )
    saved = inserted(session)
    assert status == "inserted" and identifier == saved.observation_id
    assert saved.source_record_id == source_record_id
    assert saved.value == Decimal("1.250") and saved.value_raw == "1.250"
    assert saved.location_raw == candidate.location_raw
    assert saved.evidence == candidate.evidence and saved.extraction_method == "deterministic"
    assert saved.evidence is not candidate.evidence
    candidate.evidence["test"] = "changed after load"
    assert saved.evidence == {"test": "synthetic"}


def test_weather_does_not_invent_a_missing_raw_value() -> None:
    candidate = record().model_copy(update={"value_raw": None})
    session = session_for()
    load_weather_record_with_supersession(session, candidate, "test", uuid4())
    assert inserted(session).value_raw is None


def existing(candidate: WeatherRecord, source_id: UUID) -> WeatherObservation:
    return WeatherObservation(
        observation_id=uuid4(),
        source_record_id=source_id,
        value=Decimal("1.250"),
        value_raw=candidate.value_raw,
        method=candidate.method,
        stage=candidate.stage,
        spatial_resolution=candidate.spatial_resolution,
        coverage_ratio=candidate.coverage_ratio,
        raster_source_record_id=candidate.raster_source_record_id,
        location_raw=candidate.location_raw,
        extraction_method=candidate.extraction_method,
        evidence=candidate.evidence,
        superseded_by=None,
    )


def test_identical_weather_proof_is_idempotent() -> None:
    candidate, source_id = record(), uuid4()
    old = existing(candidate, source_id)
    session = session_for(old)
    assert load_weather_record_with_supersession(session, candidate, "test", source_id) == (
        "idempotent_skipped",
        old.observation_id,
    )
    session.add.assert_not_called()
    assert session.execute.call_count == 2


@pytest.mark.parametrize(
    "change",
    [
        {"value": 2.5, "value_raw": "2.500"},
        {"value_raw": "01.250"},
        {"evidence": {"test": "new proof"}},
        {"method": "zonal_mean"},
        {"stage": "preliminary"},
        {"spatial_resolution": "0.05_deg"},
        {"coverage_ratio": 0.5},
        {"raster_source_record_id": uuid4()},
        {"extraction_method": "llm_verified"},
    ],
)
def test_weather_revisions_insert_instead_of_overwriting(change) -> None:
    candidate, source_id = record(), uuid4()
    old = existing(candidate, source_id)
    session = session_for(old)
    status, identifier = load_weather_record_with_supersession(
        session, candidate.model_copy(update=change), "test", source_id
    )
    assert status == "superseded" and identifier != old.observation_id
    assert inserted(session).observation_id == identifier
    assert old.value == Decimal("1.250") and old.source_record_id == source_id
    statement = session.execute.call_args_list[2].args[0]
    assert set(statement.compile().params) == {"superseded_by", "observation_id_1"}
    assert statement.compile().params["superseded_by"] == identifier


def test_source_revision_is_not_hidden_by_equal_weather_value() -> None:
    candidate, source_id = record(), uuid4()
    old = existing(candidate, source_id)
    session = session_for(old)
    new_source_id = uuid4()
    status, identifier = load_weather_record_with_supersession(
        session, candidate, "test", new_source_id
    )
    assert status == "superseded" and identifier != old.observation_id
    assert inserted(session).source_record_id == new_source_id
    assert old.source_record_id == source_id


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), float("-inf"), 10000000.0, -10000000.0]
)
def test_invalid_weather_value_fails_before_any_write(value: float) -> None:
    session = session_for()
    with pytest.raises(ValueError, match="weather_value_not_representable"):
        load_weather_record_with_supersession(
            session, record().model_copy(update={"value": value}), "test", uuid4()
        )
    session.add.assert_not_called()
    session.flush.assert_not_called()


def test_weather_is_not_silently_rounded_to_storage_precision() -> None:
    session = session_for()
    with pytest.raises(ValueError, match="weather_precision_not_supported"):
        load_weather_record_with_supersession(
            session, record().model_copy(update={"value": 1.2345}), "test", uuid4()
        )
    session.add.assert_not_called()
    session.flush.assert_not_called()


def test_weather_sql_fields_and_raw_are_bound_to_exact_source_cells() -> None:
    fields = {
        "value": "1.250",
        "date": "2026-10-01",
        "variable": "precip_mm",
        "provider": "synthetic",
        "location_raw": "TEST-LOCATION",
        "method": "point_centroid",
    }
    saved = WeatherObservation(
        observation_id=uuid4(),
        source_record_id=uuid4(),
        value=Decimal("1.250"),
        value_raw="1.250",
        date=date(2026, 10, 1),
        variable="precip_mm",
        provider="synthetic",
        location_raw="TEST-LOCATION",
        method="point_centroid",
        extraction_method="deterministic",
        evidence={
            "provenance": {
                "version": 1,
                "format": "json",
                "scope_path": [0],
                "cells": [
                    {
                        "field": field,
                        "path": [0, field],
                        "expected": "untrusted",
                        "role": "value" if field == "value" else "identity",
                        "kind": "number" if field == "value" else "text",
                    }
                    for field in fields
                ],
            }
        },
    )
    content = json.dumps([fields]).encode()
    claim = bind_observation("weather_observation", saved)
    assert verify_cells(content, "application/json", claim.proof) == 6
    saved.location_raw = "OTHER-LOCATION"
    with pytest.raises(ProofError, match="identity_mismatch"):
        verify_cells(
            content, "application/json", bind_observation("weather_observation", saved).proof
        )
