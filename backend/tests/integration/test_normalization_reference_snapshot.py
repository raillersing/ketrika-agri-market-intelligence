"""Prepared SQL/S3 snapshot consumption; execute only after principal check ends."""

import hashlib
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session, get_sessionmaker
from ketrika.core.models.db import PriceObservation, Product, ProductAlias, Source
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.normalize.price_loader import load_normalized_price
from ketrika.normalize.products import normalize_product_string
from ketrika.normalize.reference_snapshot import prepare_reference_snapshot
from tests.integration.test_normalized_price_load import persist_artifact


def guard(session):
    url = session.get_bind().engine.url
    require_synthetic_test_database(url.host, url.database)


def setup_reference():
    store = BronzeStore()
    assert store.bucket == "ketrika-qa-bronze"
    source_id, product_id = f"dummy_snapshot_{uuid4().hex}", uuid4()
    alias = f"Synthetic snapshot commodity {uuid4().hex}"
    with get_session() as session:
        guard(session)
        session.add_all(
            [
                Source(
                    source_id=source_id,
                    status="disabled",
                    spec={"dataset": "synthetic", "verified": False},
                ),
                Product(
                    product_id=product_id,
                    product_code=f"SYNTHETIC_{uuid4().hex}",
                    canonical_name_fr=alias,
                    category="synthetic",
                    base_unit="kg",
                    verified=False,
                ),
            ]
        )
        session.flush()
        session.add(
            ProductAlias(
                alias_id=uuid4(),
                alias_norm=normalize_product_string(alias),
                alias_display=alias,
                lang="fr",
                product_id=product_id,
                source_id=source_id,
                confidence=Decimal(1),
                origin="synthetic_test",
                human_reviewed=False,
            )
        )
        session.flush()
        reference_id, record = persist_artifact(
            session, store, source_id, alias, "14250.1250", "FMG"
        )
    return store, source_id, product_id, reference_id, record


@pytest.mark.integration
def test_normalizer_snapshot_reloaded_and_retry_without_duplicate_then_context_expires():
    store, source_id, _, reference_id, record = setup_reference()
    session = get_sessionmaker()()
    try:
        guard(session)
        snapshot = prepare_reference_snapshot(session, store)
        first = load_normalized_price(
            session, record, source_id, reference_id, reference_snapshot=snapshot
        )
        assert first.action == "inserted"
        replay = load_normalized_price(
            session, record, source_id, reference_id, reference_snapshot=snapshot
        )
        assert (
            replay.action == "idempotent_skipped" and replay.observation_id == first.observation_id
        )
        session.commit()
        with pytest.raises(ValueError, match="^normalization_reference_context_invalid$"):
            load_normalized_price(
                session, record, source_id, reference_id, reference_snapshot=snapshot
            )
        session.rollback()
        session.expire_all()
        row = session.get(PriceObservation, first.observation_id)
        assert row is not None and row.price_mga_per_base == Decimal("2850.0250")
        evidence = row.evidence["normalization"]["reference_snapshot"]
        assert evidence["sha256"] == snapshot.manifest.sha256
        assert evidence["object_key"] == snapshot.archive.object_key
        assert evidence["source_verified"] is False
        content = BronzeProofReader(store).get(evidence["object_key"])
        assert content == snapshot.manifest.content
        assert hashlib.sha256(content).hexdigest() == evidence["sha256"]
        renewed = prepare_reference_snapshot(session, store)
        retried = load_normalized_price(
            session, record, source_id, reference_id, reference_snapshot=renewed
        )
        assert (
            retried.action == "idempotent_skipped"
            and retried.observation_id == first.observation_id
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(PriceObservation)
                .where(PriceObservation.source_record_id == reference_id)
            )
            == 1
        )
    finally:
        session.rollback()
        session.close()


@pytest.mark.integration
@pytest.mark.parametrize("change", ["own_sql", "pending_orm"])
def test_reference_changes_refuse_without_observation_or_overwriting_pending_data(change):
    store, source_id, product_id, reference_id, record = setup_reference()
    session = get_sessionmaker()()
    try:
        guard(session)
        snapshot = prepare_reference_snapshot(session, store)
        if change == "own_sql":
            session.execute(
                text("UPDATE ref.product SET canonical_name_fr=:name WHERE product_id=:id"),
                {"name": "Synthetic changed", "id": product_id},
            )
            reason = "normalization_reference_manifest_changed"
        else:
            product = session.get(Product, product_id)
            assert product is not None
            product.canonical_name_fr = "Synthetic pending; do not overwrite"
            reason = "normalization_reference_changes_pending"
        with pytest.raises(ValueError, match=f"^{reason}$"):
            load_normalized_price(
                session, record, source_id, reference_id, reference_snapshot=snapshot
            )
        if change == "pending_orm":
            assert product.canonical_name_fr == "Synthetic pending; do not overwrite"
            assert product in session.dirty
        session.rollback()
        assert (
            session.scalar(
                select(func.count())
                .select_from(PriceObservation)
                .where(PriceObservation.source_record_id == reference_id)
            )
            == 0
        )
    finally:
        session.rollback()
        session.close()


@pytest.mark.integration
def test_cached_product_is_refreshed_to_the_transaction_snapshot():
    store, source_id, product_id, reference_id, record = setup_reference()
    session = get_sessionmaker()()
    try:
        guard(session)
        cached = session.get(Product, product_id)
        assert cached is not None
        initial_name = cached.canonical_name_fr
        with get_session() as writer:
            guard(writer)
            writer.execute(
                text("UPDATE ref.product SET canonical_name_fr=:name WHERE product_id=:id"),
                {"name": "Synthetic newer configured name", "id": product_id},
            )
        assert cached.canonical_name_fr == initial_name
        snapshot = prepare_reference_snapshot(session, store)
        loaded = load_normalized_price(
            session, record, source_id, reference_id, reference_snapshot=snapshot
        )
        assert loaded.action == "inserted"
        assert cached.canonical_name_fr == "Synthetic newer configured name"
        row = session.get(PriceObservation, loaded.observation_id)
        assert row is not None
        assert (
            row.evidence["normalization"]["reference_snapshot"]["sha256"]
            == snapshot.manifest.sha256
        )
        session.rollback()
        assert (
            session.scalar(
                select(func.count())
                .select_from(PriceObservation)
                .where(PriceObservation.source_record_id == reference_id)
            )
            == 0
        )
    finally:
        session.rollback()
        session.close()
