"""Fresh structure refusal before actual Gold SQL; isolated synthetic SQL/S3 only."""

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event, insert, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import (
    DqResult,
    Location,
    PriceObservation,
    Product,
    Source,
    SourceRecord,
)
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.core.schema_audit import CSVSchemaContract, audit_source_schema
from ketrika.core.schema_contracts import SchemaContractBinding, SchemaContractRegistry
from ketrika.gold.refresh import init_gold_views, refresh_gold_views
from ketrika.gold.schema_gate import GoldSchemaRejected
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.integration.test_gold_publication_provenance import signature
from tests.unit.test_provenance_audit import price_example

COLUMNS = ("price_value", "product_raw", "period_start", "unit_raw", "currency_raw")
CONTRACT = CSVSchemaContract("explicit-synthetic-flat-v1", COLUMNS)


@pytest.fixture
def publication_case():
    store = BronzeStore()
    with get_session() as session:
        target = session.get_bind().engine.url
        require_synthetic_test_database(target.host, target.database)
        assert store.bucket == "ketrika-qa-bronze"
        wipe_silver_gold_tables(session)
        source_id = "dummy_direct_schema_" + uuid4().hex
        product = Product(
            product_id=uuid4(),
            product_code="fixture_" + uuid4().hex,
            canonical_name_fr="Synthetic rice",
            category="cereal",
            base_unit="kg",
            verified=False,
        )
        location = Location(
            location_id=uuid4(),
            name="Synthetic place",
            admin_level=9,
            boundary_version="synthetic;verified=false",
        )
        session.add_all(
            [
                Source(
                    source_id=source_id,
                    status="disabled",
                    spec={"dataset": "synthetic", "verified": False},
                ),
                product,
                location,
            ]
        )
        session.flush()
        registry = SchemaContractRegistry(
            (SchemaContractBinding(source_id, "parser-v1", "text/csv", CONTRACT),)
        )

        def add_observation(*, drift=False, parser="parser-v1", pending=False, superseded_by=None):
            observation, original = price_example()
            values = json.loads(original)[0]
            output = io.StringIO(newline="")
            # Distinct synthetic editions obey the existing (source_id,SHA) uniqueness.
            terminator = "\r\n" if pending else "\r" if superseded_by is not None else "\n"
            writer = csv.writer(output, lineterminator=terminator)
            writer.writerow([*COLUMNS, *(["unexpected_tool"] if drift else [])])
            writer.writerow(
                [*[values[field] for field in COLUMNS], *(["RUN_TOOL_NOW"] if drift else [])]
            )
            content = output.getvalue().encode()
            artifact = store.put(
                source_id=source_id,
                content=content,
                mime_type="text/csv",
                url="https://example.invalid/synthetic-direct-schema",
                retrieved_via="manual_upload",
                fetched_at=datetime.now(UTC),
                http_status=0,
                http_headers={"x-ketrika-dataset": "synthetic;verified=false"},
            )
            record = SourceRecord(
                source_record_id=observation.source_record_id,
                source_id=source_id,
                source_url=artifact.url,
                object_key=artifact.object_key,
                content_sha256=artifact.content_sha256,
                mime_type="text/csv",
                retrieved_via="manual_upload",
                fetched_at=datetime.now(UTC),
                parser_version=parser,
                extraction_status="parsed",
            )
            session.add(record)
            session.flush()
            observation.product_id, observation.location_id = (
                product.product_id,
                location.location_id,
            )
            observation.price_mga_per_base = Decimal("3000.1250")
            observation.natural_key = uuid4().hex
            observation.review_status = "pending" if pending else "accepted"
            observation.superseded_by = superseded_by
            observation.evidence = {
                "provenance": {
                    "version": 1,
                    "format": "csv",
                    "row": 0,
                    "delimiter": ",",
                    "cells": [
                        {
                            "field": field,
                            "column": field,
                            "role": "value" if field == "price_value" else "identity",
                            "kind": "number" if field == "price_value" else "text",
                        }
                        for field in COLUMNS
                    ],
                }
            }
            session.add(observation)
            session.flush()
            return observation, record, content

        current, record, content = add_observation()
        init_gold_views(session)
        reader = BronzeProofReader(store)
        positive = refresh_gold_views(
            session, views=["price_obs_current"], reader=reader, schema_registry=registry
        )
        assert positive["structure_state"] == "structure_verified"
        assert positive["structure_artifacts_total"] == positive["structure_artifacts_valid"] == 1
        try:
            yield session, registry, reader, add_observation, current, record, content, positive
        finally:
            if not session.is_active:
                session.rollback()


@pytest.mark.integration
@pytest.mark.parametrize(
    "mode", ["absent", "wrong_parser", "other_source", "drift", "unreadable", "sha"]
)
def test_direct_refresh_refuses_structure_without_changing_published_cache(
    publication_case, mode, request
):
    session, registry, reader, add, current, record, content, positive = publication_case
    if mode == "drift":
        add(drift=True)
    if mode == "absent":
        registry = SchemaContractRegistry()
    elif mode == "wrong_parser":
        registry = SchemaContractRegistry(
            (SchemaContractBinding(record.source_id, "parser-v2", "text/csv", CONTRACT),)
        )
    elif mode == "other_source":
        registry = SchemaContractRegistry(
            (SchemaContractBinding("other_source", "parser-v1", "text/csv", CONTRACT),)
        )
    baseline = signature(session)
    silver_before = session.scalar(
        text(
            "SELECT md5(string_agg(to_jsonb(p)::text, ',' ORDER BY observation_id)) FROM obs.price_observation p"
        )
    )
    calls = []

    class FreshSecondRead:
        def get(self, key):
            calls.append(key)
            # The first read is provenance; the next must independently measure structure.
            if mode == "unreadable" and len(calls) == 2:
                raise RuntimeError("untrusted detail must not be emitted")
            result = reader.get(key)
            return result + b"damage" if mode == "sha" and len(calls) == 2 else result

    statements = []
    connection = session.connection()

    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("REFRESH MATERIALIZED VIEW"):
            statements.append(statement)

    event.listen(connection, "before_cursor_execute", capture)
    try:
        with pytest.raises(GoldSchemaRejected) as rejected:
            refresh_gold_views(
                session,
                views=["price_obs_current"],
                reader=FreshSecondRead(),
                schema_registry=registry,
            )
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert not statements and signature(session) == baseline
    assert (
        session.scalar(
            text(
                "SELECT md5(string_agg(to_jsonb(p)::text, ',' ORDER BY observation_id)) FROM obs.price_observation p"
            )
        )
        == silver_before
    )
    assert hashlib.sha256(reader.get(record.object_key)).hexdigest() == record.content_sha256
    assert rejected.value.receipts and all(not r.report.passed for r in rejected.value.receipts)
    for receipt in rejected.value.receipts:
        saved = session.get(DqResult, receipt.dq_id)
        assert saved is not None and not saved.passed
        assert saved.details["scope"] == "publication_candidate_artifacts"
        assert "RUN_TOOL_NOW" not in json.dumps(saved.details)
        assert "untrusted detail" not in json.dumps(saved.details)
    assert len(calls) >= 2
    # Caller explicitly commits the diagnostic; the helper never commits implicitly.
    ids = [r.dq_id for r in rejected.value.receipts]
    session.commit()
    with get_session() as reread:
        assert all(reread.get(DqResult, identifier) is not None for identifier in ids)
        assert signature(reread) == baseline
    request.node.user_properties.append(
        (
            "ketrika.structure.direct",
            json.dumps(
                {
                    "mode": mode,
                    "refresh_statements": len(statements),
                    "cache_unchanged": True,
                    "silver_unchanged": True,
                    "bronze_unchanged": True,
                    "dataset": "synthetic",
                }
            ),
        )
    )


@pytest.mark.integration
def test_pending_and_superseded_unknown_versions_do_not_enter_publication_scope(publication_case):
    session, registry, reader, add, current, record, content, positive = publication_case
    add(parser="unknown-parser", pending=True)
    add(parser="unknown-parser", superseded_by=current.observation_id)
    result = refresh_gold_views(
        session, views=["price_obs_current"], reader=reader, schema_registry=registry
    )
    assert result["source_observations_total"] == result["structure_artifacts_total"] == 1
    assert signature(session)[0] == 1
    history = audit_source_schema(session, reader, record.source_id, registry=registry)
    assert history.report.total_artifacts == 3 and history.report.valid_artifacts == 1
    assert not history.report.passed


@pytest.mark.integration
def test_metadata_only_does_not_claim_structure_certification(publication_case):
    session, registry, reader, add, current, record, content, positive = publication_case
    result = refresh_gold_views(
        session, views=["source_health"], reader=reader, schema_registry=SchemaContractRegistry()
    )
    assert result["structure_state"] == "metadata_only"
    assert result["structure_artifacts_total"] == result["structure_artifacts_valid"] == 0
    assert result["structure_dq_ids"] == []


@pytest.mark.integration
def test_empty_numeric_views_are_not_structure_verified(publication_case):
    session, registry, reader, add, current, record, content, positive = publication_case
    session.commit()  # Settle deferred observation triggers before the isolated fixture wipe.
    wipe_silver_gold_tables(session)
    result = refresh_gold_views(
        session,
        views=["price_obs_current"],
        reader=reader,
        schema_registry=SchemaContractRegistry(),
    )
    assert result["structure_state"] == "empty" and result["source_cell_rate"] is None
    assert result["structure_artifacts_total"] == 0 and result["structure_dq_ids"] == []
    assert signature(session)[0] == 0


@pytest.mark.integration
def test_candidate_locks_prevent_concurrent_observation_insert(publication_case):
    session, registry, reader, add, current, record, content, positive = publication_case
    values = {
        column.key: getattr(current, column.key) for column in PriceObservation.__table__.columns
    }
    values["observation_id"], values["natural_key"] = uuid4(), uuid4().hex
    baseline = signature(session)
    # Real independent PostgreSQL connection; no mocked lock or inferred timing proof.
    with Session(session.get_bind().engine) as writer:
        writer.execute(text("SET LOCAL lock_timeout = '250ms'"))
        with pytest.raises(DBAPIError) as rejected:
            writer.execute(insert(PriceObservation).values(**values))
        assert rejected.value.orig.sqlstate == "55P03"
        writer.rollback()
    assert signature(session) == baseline
