"""Synthetic source-backed normalization; never official market qualification."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from ketrika.connectors.records import PriceRecord
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import PriceObservation, Product, ProductAlias, Source, SourceRecord
from ketrika.core.provenance_audit import ObservationTarget, audit_observation_provenance
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.normalize.price_loader import load_normalized_price
from ketrika.normalize.products import normalize_product_string


def persist_artifact(session, store, source_id, alias, price, currency="FMG"):
    row = {
        "price": price,
        "product": alias,
        "market": "Antananarivo",
        "period_start": "2024-01-01",
        "unit": "kg",
        "currency": currency,
    }
    artifact = store.put(
        source_id=source_id,
        content=json.dumps([row]).encode(),
        mime_type="application/json",
        url="https://example.invalid/synthetic-normalization",
        retrieved_via="manual_upload",
        fetched_at=datetime(2026, 10, 11, tzinfo=UTC),
        http_status=0,
        http_headers={"x-ketrika-dataset": "synthetic; verified=false"},
    )
    identifier = uuid4()
    session.add(
        SourceRecord(
            source_record_id=identifier,
            source_id=source_id,
            source_url="https://example.invalid/synthetic-normalization",
            retrieved_via="manual_upload",
            object_key=artifact.object_key,
            content_sha256=artifact.content_sha256,
            mime_type="application/json",
            fetched_at=datetime.now(UTC),
            parser_version="1.0.0",
            extraction_status="parsed",
        )
    )
    session.flush()
    record = PriceRecord(
        product_raw=alias,
        location_raw="Antananarivo",
        actor_level="retail",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        price_raw=price,
        unit_raw="kg",
        currency_raw=currency,
        evidence={
            "provenance": {
                "version": 1,
                "format": "json",
                "scope_path": [0],
                "cells": [
                    {
                        "field": field,
                        "path": [0, column],
                        "role": "value" if field == "price_value" else "identity",
                        "kind": "number" if field == "price_value" else "text",
                        "expected": row[column],
                    }
                    for field, column in (
                        ("price_value", "price"),
                        ("product_raw", "product"),
                        ("location_raw", "market"),
                        ("period_start", "period_start"),
                        ("unit_raw", "unit"),
                        ("currency_raw", "currency"),
                    )
                ],
            }
        },
    )
    return identifier, record


@pytest.mark.integration
@pytest.mark.parametrize("currency", ["FMG", "USD"])
def test_source_alias_normalization_retry_revision_and_proof_across_sessions(request, currency):
    source_id = f"dummy_normalized_sql_{uuid4().hex}"
    alias = f"Synthetic scoped commodity {uuid4().hex}"
    with get_session() as session:
        url = session.get_bind().engine.url
        require_synthetic_test_database(url.host, url.database)
        store = BronzeStore()
        assert store.bucket == "ketrika-qa-bronze"
        rice = session.scalar(select(Product).where(Product.product_code == "RICE_WHITE_LOCAL"))
        maize = session.scalar(select(Product).where(Product.product_code == "MAIZE_GRAIN"))
        assert rice is not None and maize is not None
        session.add(
            Source(
                source_id=source_id,
                status="disabled",
                spec={"authenticity": "synthetic", "verified": False},
            )
        )
        session.flush()
        for scope, product in ((None, maize), (source_id, rice)):
            session.add(
                ProductAlias(
                    alias_id=uuid4(),
                    alias_norm=normalize_product_string(alias),
                    alias_display=alias,
                    lang="fr",
                    product_id=product.product_id,
                    source_id=scope,
                    confidence=Decimal(1),
                    origin="synthetic_test",
                    human_reviewed=False,
                )
            )
        session.flush()
        reference_id, record = persist_artifact(
            session, store, source_id, alias, "14250.1250", currency
        )
        first = load_normalized_price(session, record, source_id, reference_id)
        assert first.action == "inserted"
        assert first.review_items == (0 if currency == "FMG" else 1)
        first_id = first.observation_id
        rice_id = rice.product_id
    with get_session() as session:
        row = session.get(PriceObservation, first_id)
        assert row is not None and row.product_id == rice_id
        assert row.price_raw == "14250.1250" and row.price_value == Decimal("14250.1250")
        assert row.currency_raw == currency and row.unit_raw == "kg"
        assert row.base_unit == "kg"
        assert row.price_mga_per_base == (Decimal("2850.0250") if currency == "FMG" else None)
        assert row.conversion_status == ("confident" if currency == "FMG" else "uncertain")
        assert row.review_status == ("accepted" if currency == "FMG" else "pending")
        assert row.evidence["normalization"]["product_match"] == "exact_source_alias"
        replay = load_normalized_price(session, record, source_id, reference_id)
        assert replay.action == "idempotent_skipped" and replay.observation_id == first_id
        assert replay.review_items == 0
        new_reference_id, revision = persist_artifact(
            session, store, source_id, alias, "14255.1250", currency
        )
        revised = load_normalized_price(session, revision, source_id, new_reference_id)
        assert revised.action == "superseded"
        revised_id = revised.observation_id
    with get_session() as session:
        old = session.get(PriceObservation, first_id)
        new = session.get(PriceObservation, revised_id)
        assert old is not None and new is not None
        assert old.price_value == Decimal("14250.1250") and old.superseded_by == revised_id
        assert new.price_value == Decimal("14255.1250")
        assert new.price_mga_per_base == (Decimal("2851.0250") if currency == "FMG" else None)
        receipt = audit_observation_provenance(
            session,
            BronzeProofReader(store),
            mode="incremental",
            targets=[
                ObservationTarget("price_observation", first_id),
                ObservationTarget("price_observation", revised_id),
            ],
        )
        assert receipt.report.total == 2 and receipt.report.valid == 0
        assert not receipt.report.passed
        assert all(
            result.reason == "synthetic_source_record_forbidden"
            for result in receipt.report.results
        )
        request.node.user_properties.append(
            (
                "ketrika.normalization",
                json.dumps(
                    {
                        "source_id": source_id,
                        "currency": currency,
                        "old_id": str(first_id),
                        "new_id": str(revised_id),
                        "valid": 0,
                        "total": 2,
                        "objects_read": receipt.report.objects_read,
                        "retry_action": "idempotent_skipped",
                        "revision_action": "superseded",
                        "scope": "synthetic SQL + immutable QA Bronze; no official source or market qualification",
                    }
                ),
            )
        )
