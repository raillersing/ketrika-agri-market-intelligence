"""Synthetic production SQL history; not agricultural source qualification."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from ketrika.connectors.records import ProductionRecord
from ketrika.connectors.runner import load_production_record_with_supersession
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import ProductionObservation, Source, SourceRecord
from ketrika.core.provenance_audit import ObservationTarget, audit_observation_provenance
from ketrika.core.qualification import require_synthetic_test_database


@pytest.mark.integration
def test_production_raw_revision_survives_session_reread(request: pytest.FixtureRequest) -> None:
    with get_session() as session:
        url = session.get_bind().engine.url
        require_synthetic_test_database(url.host, url.database)
        source_id, reference_id = "test-production-" + uuid4().hex, uuid4()
        session.add(
            Source(
                source_id=source_id,
                status="disabled",
                spec={"authenticity": "synthetic", "verified": False},
            )
        )
        session.flush()
        reader = BronzeStore()
        assert reader.bucket == "ketrika-qa-bronze"
        product = "synthetic-production-" + uuid4().hex
        fields = {
            "product_raw": product,
            "period_start": "2026-01-01",
            "element": "production_t",
            "unit_raw": "t",
            "value": "1.2500",
        }
        artifact = reader.put(
            source_id=source_id,
            content=json.dumps([fields]).encode(),
            mime_type="application/json",
            url="https://example.invalid/synthetic-production",
            retrieved_via="manual_upload",
            fetched_at=datetime(2026, 10, 10, tzinfo=UTC),
            http_status=0,
            http_headers={"x-ketrika-dataset": "synthetic; verified=false"},
        )
        session.add(
            SourceRecord(
                source_record_id=reference_id,
                source_id=source_id,
                object_key=artifact.object_key,
                content_sha256=artifact.content_sha256,
                mime_type="application/json",
                source_url="https://example.invalid/synthetic-production",
                retrieved_via="manual_upload",
                fetched_at=datetime.now(UTC),
                extraction_status="parsed",
                parser_version="synthetic-test",
            )
        )
        session.flush()
        evidence = {
            "version": 1,
            "format": "json",
            "scope_path": [0],
            "cells": [
                {
                    "role": "value" if field == "value" else "identity",
                    "field": field,
                    "path": [0, field],
                    "expected": raw,
                    "kind": "number" if field == "value" else "text",
                }
                for field, raw in fields.items()
            ],
        }
        candidate = ProductionRecord(
            product_raw=product,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
            element="production_t",
            value=1.25,
            value_raw="1.2500",
            unit_raw="t",
            evidence={"provenance": evidence},
        )
        status, old_id = load_production_record_with_supersession(
            session, candidate, source_id, reference_id
        )
        assert status == "inserted"
    with get_session() as session:
        old = session.get(ProductionObservation, old_id)
        assert old is not None and old.value_raw == "1.2500"
        assert old.value == Decimal("1.2500")
        assert load_production_record_with_supersession(
            session, candidate, source_id, reference_id
        ) == ("idempotent_skipped", old_id)
        revised = candidate.model_copy(update={"value_raw": "01.2500"})
        status, new_id = load_production_record_with_supersession(
            session, revised, source_id, reference_id
        )
        assert status == "superseded" and new_id != old_id
    with get_session() as session:
        old, new = (
            session.get(ProductionObservation, old_id),
            session.get(ProductionObservation, new_id),
        )
        assert old is not None and new is not None
        assert old.value_raw == "1.2500" and old.superseded_by == new_id
        assert new.value_raw == "01.2500" and new.superseded_by is None
        assert old.value == new.value == Decimal("1.2500")
        assert old.source_record_id == new.source_record_id == reference_id
        receipt = audit_observation_provenance(
            session,
            reader,
            mode="incremental",
            targets=[
                ObservationTarget("production_observation", old_id),
                ObservationTarget("production_observation", new_id),
            ],
        )
        assert receipt.report.total == 2 and receipt.report.valid == 1
        assert not receipt.report.passed
        request.node.user_properties.append(
            (
                "ketrika.production.raw_revision",
                "synthetic SQL only; history=2; current=1; cell_provenance=false",
            )
        )
