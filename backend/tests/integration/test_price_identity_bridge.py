"""Real isolated SQL/immutable QA Bronze; no real source/market qualification."""

from dataclasses import replace
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ketrika.connectors.base import RecordBase
from ketrika.connectors.durable_phases import execute_durable_silver
from ketrika.connectors.runner import load_price_record_with_supersession
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import IngestionRun, PriceObservation, ReviewItem, Source
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.normalize.loader import normalize_and_load_price_records
from ketrika.normalize.price_loader import load_normalized_price
from tests.integration.test_normalized_price_load import persist_artifact
from tests.integration.test_silver_recovery import recovery_case as _recovery_case

recovery_case = _recovery_case


@pytest.fixture
def case():
    with get_session() as session:
        url = session.get_bind().engine.url
        require_synthetic_test_database(url.host, url.database)
        source = "dummy_identity_" + uuid4().hex
        session.add(Source(source_id=source, status="disabled", spec={"verified": False}))
        session.flush()
        store = BronzeStore()
        assert store.bucket == "ketrika-qa-bronze"
        reference, record = persist_artifact(
            session, store, source, "Riz blanc local", "2850", "MGA"
        )
        yield session, source, reference, record


def load(session, record, source, reference, path):
    if path == "normalized":
        result = load_normalized_price(session, record, source, reference)
        return result.action, result.observation_id
    return load_price_record_with_supersession(session, record, source, reference)


def legacy(session, source, reference, record, kind="point", *, key=None, contradictory=False):
    row = PriceObservation(
        observation_id=uuid4(),
        source_record_id=reference,
        natural_key=key or RecordBase.compute_natural_key(record, source),
        product_raw=record.product_raw,
        variety=record.variety,
        location_raw=record.location_raw,
        actor_level=record.actor_level,
        period_start=record.period_start,
        period_end=record.period_end,
        price_raw=record.price_raw,
        price_value=Decimal(record.price_raw),
        unit_raw=record.unit_raw,
        currency_raw=record.currency_raw,
        observed_or_imputed=record.observed_or_imputed,
        conversion_status="uncertain",
        extraction_method="deterministic",
        confidence=Decimal(1),
        review_status="pending",
        evidence={"provenance": record.evidence["provenance"]}
        | ({"normalization": {"value_kind": kind}} if kind is not None else {})
        | ({"price_identity": {"statistical_kind": "min"}} if contradictory else {}),
    )
    session.add(row)
    session.flush()
    return row


@pytest.mark.integration
@pytest.mark.parametrize("path", ["normalized", "historical"])
def test_grains_coexist_retry_revision_and_raw_evidence(case, path):
    session, source, reference, record = case
    variants = [record] + [
        record.model_copy(update=change)
        for change in (
            {"variety": "blanc"},
            {"value_kind": "min"},
            {"value_kind": "max"},
            {"value_kind": "avg"},
            {"unit_raw": "sac"},
            {"currency_raw": "USD"},
            {"observed_or_imputed": "imputed"},
            {"location_raw": None},
            {"location_raw": "None"},
        )
    ]
    ids = []
    for variant in variants:
        action, identifier = load(session, variant, source, reference, path)
        assert action == "inserted"
        ids.append(identifier)
        assert load(session, variant, source, reference, path) == ("idempotent_skipped", identifier)
    assert len(set(ids)) == len(variants)
    action, revised_id = load(
        session,
        record.model_copy(update={"price_raw": "2855", "price_value": 2855}),
        source,
        reference,
        path,
    )
    assert action == "superseded"
    old = session.get(PriceObservation, ids[0])
    new = session.get(PriceObservation, revised_id)
    assert old is not None and new is not None
    session.refresh(old)
    assert old.price_raw == "2850" and old.superseded_by == revised_id
    assert new.evidence["provenance"] == record.evidence["provenance"]
    assert new.evidence["price_identity"]["version"] == "price_identity_v2"
    assert all(
        session.get(PriceObservation, identifier).superseded_by is None for identifier in ids[1:]
    )


@pytest.mark.integration
@pytest.mark.parametrize("path", ["normalized", "historical"])
def test_explicit_legacy_bridge_preserves_old_key_and_value(case, path):
    session, source, reference, record = case
    old = legacy(session, source, reference, record)
    old_id, old_key = old.observation_id, old.natural_key
    action, new_id = load(
        session,
        record.model_copy(update={"price_raw": "2855", "price_value": 2855}),
        source,
        reference,
        path,
    )
    assert action == "superseded"
    session.refresh(old)
    new = session.get(PriceObservation, new_id)
    assert old.natural_key == old_key and old.price_value == Decimal("2850")
    assert old.superseded_by == new_id and new.observation_id != old_id
    assert new.natural_key == record.compute_natural_key(source) != old_key


@pytest.mark.integration
@pytest.mark.parametrize("path", ["normalized", "historical", "batch"])
@pytest.mark.parametrize("ambiguity", ["unknown", "multiple", "contradictory"])
def test_unknown_or_multiple_legacy_refuses_without_duplicate_reviews(case, path, ambiguity):
    session, source, reference, record = case
    old = legacy(
        session,
        source,
        reference,
        record,
        None if ambiguity == "unknown" else "point",
        contradictory=ambiguity == "contradictory",
    )
    if ambiguity == "multiple":
        legacy(session, source, reference, record, key=uuid4().hex)
    before = session.scalar(select(func.count()).select_from(PriceObservation))
    for _ in range(2):
        if path == "batch":
            result = normalize_and_load_price_records(session, [record], source, reference)
            assert result["rejected"] == 1 and result["inserted"] == result["superseded"] == 0
        else:
            action, _ = load(session, record, source, reference, path)
            assert action == "review_required"
    assert session.scalar(select(func.count()).select_from(PriceObservation)) == before
    session.refresh(old)
    assert old.superseded_by is None and old.price_raw == "2850"
    reviews = list(
        session.scalars(select(ReviewItem).where(ReviewItem.source_record_id == reference))
    )
    assert len(reviews) == 1 and reviews[0].payload["human_reviewed"] is False
    assert str(old.observation_id) in reviews[0].payload["candidate_ids"]


@pytest.mark.integration
def test_legacy_other_statistic_and_delimiter_collision_do_not_bridge(case):
    session, source, reference, record = case
    old = legacy(session, source, reference, record, "min")
    action, new_id = load(session, record, source, reference, "historical")
    assert action == "inserted" and new_id != old.observation_id
    assert old.superseded_by is None
    first = record.model_copy(update={"product_raw": "riz|local", "location_raw": "marché"})
    second = record.model_copy(update={"product_raw": "riz", "location_raw": "local|marché"})
    collision = legacy(session, source, reference, first)
    assert RecordBase.compute_natural_key(first, source) == RecordBase.compute_natural_key(
        second, source
    )
    assert load(session, second, source, reference, "historical")[0] == "inserted"
    assert collision.superseded_by is None


@pytest.mark.integration
def test_transaction_rollback_and_independent_connection_source_lock(case):
    session, source, reference, record = case
    _, old_id = load(session, record, source, reference, "historical")
    session.commit()
    old = session.get(PriceObservation, old_id)
    _, new_id = load(
        session,
        record.model_copy(update={"price_raw": "2855", "price_value": 2855}),
        source,
        reference,
        "historical",
    )
    with Session(session.get_bind()) as other:
        other.execute(text("SET LOCAL lock_timeout = '100ms'"))
        with pytest.raises(DBAPIError) as failure:
            load(other, record, source, reference, "historical")
        assert failure.value.orig.sqlstate == "55P03"
        other.rollback()
    session.rollback()
    session.refresh(old)
    assert old.superseded_by is None and old.price_raw == "2850"
    assert session.get(PriceObservation, new_id) is None
    assert load(session, record, source, reference, "historical") == ("idempotent_skipped", old_id)


@pytest.mark.integration
def test_native_rejection_counters_receipt_v2_and_cached_retry(recovery_case):
    connector, context, batch, calls = recovery_case
    record = connector.parse(batch.artifacts[0], replace(context, offline=True)).records[0]
    reference = UUID(batch.artifacts[0].source_record_id)
    with get_session() as session:
        old = legacy(session, batch.source_id, reference, record, None)
        old_id = old.observation_id
    stats = execute_durable_silver(connector, context, batch)
    assert stats["n_rejected"] == 1 and stats["n_review"] >= 1
    assert stats["n_inserted"] == 2 and stats["n_superseded"] == 0
    prior_parse = calls["parse"]
    assert execute_durable_silver(connector, context, batch) == stats
    assert calls["parse"] == prior_parse
    with get_session() as session:
        run = session.get(IngestionRun, batch.ingestion_run_id)
        assert run.n_rejected == 1 and run.n_review == stats["n_review"]
        row = session.get(PriceObservation, old_id)
        assert row.superseded_by is None and "normalization" not in row.evidence
        versions = list(
            session.scalars(
                text(
                    "SELECT m.normalizer_version FROM meta.silver_attempt_member m "
                    "JOIN meta.silver_attempt a USING (attempt_id) WHERE a.run_id=:run"
                ),
                {"run": batch.ingestion_run_id},
            )
        )
        assert versions == ["price_normalizer_v2"]


@pytest.mark.integration
@pytest.mark.parametrize("path", ["normalized", "historical"])
def test_other_source_reference_refused_before_any_price_write(case, path):
    session, source, reference, record = case
    before = session.scalar(select(func.count()).select_from(PriceObservation))
    with pytest.raises(ValueError, match="source_reference_mismatch"):
        load(session, record, source + "_other", reference, path)
    assert session.scalar(select(func.count()).select_from(PriceObservation)) == before
