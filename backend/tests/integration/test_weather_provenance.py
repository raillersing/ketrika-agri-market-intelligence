"""Synthetic SQL/MinIO revisions; never live meteorological qualification."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from ketrika.connectors.records import WeatherRecord
from ketrika.connectors.runner import load_weather_record_with_supersession
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import DqResult, Location, Source, SourceRecord, WeatherObservation
from ketrika.core.provenance_audit import ObservationTarget, audit_observation_provenance
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.core.schema_json import JSONSchemaContract, JSONShape
from ketrika.gold.refresh import refresh_gold_views
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.e2e_data.schema_declarations import declare_synthetic_contract
from tests.unit.test_weather_migration import migration

WEATHER_CONTRACT = JSONSchemaContract(
    "synthetic-weather-structure-v1",
    JSONShape(
        "array",
        items=JSONShape(
            "object",
            properties=tuple(
                (name, JSONShape("string"), True)
                for name in ("value", "date", "location_raw", "variable", "provider", "method")
            ),
        ),
    ),
)


@pytest.mark.integration
def test_weather_history_proof_and_gold_current_rows(request: pytest.FixtureRequest) -> None:
    source_id = "test_weather_" + uuid4().hex
    declare_synthetic_contract(source_id, "synthetic-test", "application/json", WEATHER_CONTRACT)
    source_records = [uuid4(), uuid4()]
    with get_session() as session:
        url = session.get_bind().engine.url
        require_synthetic_test_database(url.host, url.database)
        reader = BronzeStore()
        assert reader.bucket == "ketrika-qa-bronze"
        wipe_silver_gold_tables(session)
        location = session.scalars(
            select(Location)
            .where(Location.admin_level == 2, Location.pcode.is_not(None))
            .order_by(Location.pcode)
        ).first()
        assert location is not None and location.pcode is not None
        location_id, location_raw = location.location_id, location.pcode
        session.add(
            Source(
                source_id=source_id,
                status="disabled",
                spec={"authenticity": "synthetic", "verified": False},
            )
        )
        session.flush()
        records = []
        artifacts = []
        for identifier, raw in zip(source_records, ["1.250", "2.500"], strict=True):
            fields = {
                "value": raw,
                "date": "2026-10-01",
                "location_raw": location_raw,
                "variable": "precip_mm",
                "provider": source_id,
                "method": "point_centroid",
            }
            content = json.dumps([fields]).encode()
            artifact = reader.put(
                source_id=source_id,
                content=content,
                mime_type="application/json",
                url="https://example.invalid/synthetic-weather",
                retrieved_via="manual_upload",
                fetched_at=datetime(2026, 10, 10, tzinfo=UTC),
                http_status=0,
                http_headers={"x-ketrika-dataset": "synthetic; verified=false"},
            )
            artifacts.append(artifact)
            session.add(
                SourceRecord(
                    source_record_id=identifier,
                    source_id=source_id,
                    object_key=artifact.object_key,
                    content_sha256=artifact.content_sha256,
                    mime_type="application/json",
                    source_url="https://example.invalid/synthetic-weather",
                    retrieved_via="manual_upload",
                    fetched_at=datetime.now(UTC),
                    extraction_status="parsed",
                    parser_version="synthetic-test",
                )
            )
            proof = {
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
            records.append(
                WeatherRecord(
                    location_raw=location_raw,
                    date=date(2026, 10, 1),
                    variable="precip_mm",
                    value=float(raw),
                    value_raw=raw,
                    provider=source_id,
                    evidence={"provenance": proof},
                )
            )
        session.flush()
        status, old_id = load_weather_record_with_supersession(
            session, records[0], source_id, source_records[0]
        )
        assert status == "inserted"
    with get_session() as session:
        old = session.get(WeatherObservation, old_id)
        assert old is not None and old.value == Decimal("1.250") and old.value_raw == "1.250"
        assert old.evidence == records[0].evidence and old.location_raw == location_raw
        status, new_id = load_weather_record_with_supersession(
            session, records[1], source_id, source_records[1]
        )
        assert status == "superseded" and old_id != new_id
    with get_session() as session:
        old, new = session.get(WeatherObservation, old_id), session.get(WeatherObservation, new_id)
        assert old is not None and new is not None
        assert old.superseded_by == new_id and new.superseded_by is None
        assert old.value == Decimal("1.250") and old.source_record_id == source_records[0]
        assert old.value_raw == "1.250" and old.evidence == records[0].evidence
        assert new.value == Decimal("2.500") and new.source_record_id == source_records[1]
        assert load_weather_record_with_supersession(
            session, records[1], source_id, source_records[1]
        ) == ("idempotent_skipped", new_id)
        counts = session.scalar(
            select(func.count())
            .select_from(WeatherObservation)
            .where(WeatherObservation.provider == source_id)
        )
        assert counts == 2
        receipt = audit_observation_provenance(
            session,
            reader,
            mode="incremental",
            targets=[
                ObservationTarget("weather_observation", old_id),
                ObservationTarget("weather_observation", new_id),
            ],
        )
        assert receipt.report.valid == receipt.report.total == 2 and receipt.report.passed
        assert receipt.report.objects_read == 2
        dq_id = receipt.dq_id
        for statement in (
            "UPDATE obs.weather_observation SET value=99 WHERE observation_id=:id",
            "DELETE FROM obs.weather_observation WHERE observation_id=:id",
        ):
            with pytest.raises(DBAPIError), session.begin_nested():
                session.execute(text(statement), {"id": new_id})
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                WeatherObservation(
                    source_record_id=source_records[1],
                    location_id=location_id,
                    date=date(2026, 10, 1),
                    variable="precip_mm",
                    value=Decimal("2.500"),
                    method="point_centroid",
                    provider=source_id,
                )
            )
            session.flush()
        refresh_gold_views(session, views=["weather_monthly", "market_health"])
        total = session.scalar(
            text(
                "SELECT precip_total_mm FROM gold.weather_monthly WHERE location_id=:id AND month='2026-10-01'"
            ),
            {"id": location_id},
        )
        assert total == Decimal("2.50")  # Old 1.25 must not be counted a second time.
    with get_session() as session:
        dq = session.get(DqResult, dq_id)
        assert dq is not None and dq.passed and dq.metric == 100
        assert dq.details is not None and dq.details["valid_provenance"] == 2
        assert session.get(WeatherObservation, old_id) is not None
        assert session.get(WeatherObservation, new_id) is not None
    with get_session() as session:
        url = session.get_bind().engine.url
        require_synthetic_test_database(url.host, url.database)
        session.execute(text("SET TRANSACTION READ ONLY"))
        module = migration()
        operations = Operations(MigrationContext.configure(session.connection()))
        with (
            patch.object(module, "op", operations),
            pytest.raises(RuntimeError, match="discard evidence/history"),
        ):
            module.downgrade()
        assert (
            session.scalar(
                text(
                    "SELECT count(*) FROM information_schema.columns WHERE table_schema='obs' AND table_name='weather_observation' AND column_name IN ('location_raw','value_raw','evidence','extraction_method','superseded_by')"
                )
            )
            == 5
        )
        assert session.get(WeatherObservation, old_id) is not None
        assert session.get(WeatherObservation, new_id) is not None
        for artifact in artifacts:
            assert reader.get(artifact.object_key)
        request.node.user_properties.append(
            (
                "ketrika.weather.revisions",
                json.dumps(
                    {
                        "history_rows": 2,
                        "current_rows": 1,
                        "valid": 2,
                        "total": 2,
                        "objects_read": 2,
                        "dq_id": str(dq_id),
                        "negative_update_delete_refused": True,
                        "downgrade_with_evidence_refused_readonly": True,
                        "dataset": "synthetic; no live source or market qualification",
                    }
                ),
            )
        )
