"""Real SQL normalization preserves raw data and never revives quarantine."""

import hashlib
import importlib.util
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

import ketrika.normalize.reconcile_products as reconcile
from ketrika.core.db import get_engine
from ketrika.core.models import db
from ketrika.core.qualification import require_synthetic_test_database


@pytest.fixture
def normalization_case(monkeypatch):
    engine = get_engine()
    require_synthetic_test_database(engine.url.host, engine.url.database)
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            tag = "synthetic_normalize_" + uuid4().hex
            source = db.Source(source_id=tag, spec={"synthetic": True}, status="active")
            old = db.Product(
                product_id=uuid4(),
                product_code=tag + "_old",
                canonical_name_fr=tag + "_old",
                category="synthetic",
                base_unit="kg",
            )
            target = db.Product(
                product_id=uuid4(),
                product_code=tag + "_new",
                canonical_name_fr=tag + "_new",
                category="synthetic",
                base_unit="kg",
            )
            refs = [
                db.SourceRecord(
                    source_record_id=uuid4(),
                    source_id=tag,
                    source_url="https://example.invalid/synthetic-only",
                    object_key="synthetic/" + uuid4().hex,
                    content_sha256=hashlib.sha256(uuid4().bytes).hexdigest(),
                    mime_type="application/json",
                    fetched_at=datetime.now(UTC),
                    parser_version="synthetic-only",
                )
                for _ in range(2)
            ]
            session.add_all([source, old, target, *refs])
            session.flush()
            location = session.scalar(select(db.Location).limit(1))
            assert location is not None
            monkeypatch.setattr(
                reconcile,
                "CODE_MAPPING",
                {old.product_code: target.product_code, "synthetic_absent": "synthetic_missing"},
            )
            try:
                yield session, connection, old, target, refs, location
            finally:
                session.close()
                transaction.rollback()


def make_row(kind, product, reference, location, *, short=False):
    suffix = (
        f"{location.location_id}|retail|2026-10-01"
        if kind == "price"
        else f"{location.location_id}|2026-10-01"
        if kind == "stock"
        else "import|None|2026-10-01"
    )
    common = {
        "observation_id": uuid4(),
        "source_record_id": reference.source_record_id,
        "product_id": product.product_id,
        "natural_key": "synthetic_short_" + uuid4().hex
        if short
        else product.product_code + "|" + suffix,
        "product_raw": "synthetic",
        "period_start": date(2026, 10, 1),
        "period_end": date(2026, 10, 31),
        "confidence": 0.9,
        "extraction_method": "deterministic",
        "evidence": {"synthetic": True},
    }
    if kind == "price":
        return db.PriceObservation(
            **common,
            location_id=location.location_id,
            location_raw="synthetic",
            actor_level="retail",
            price_raw="1.25",
            price_value=1.25,
            unit_raw="kg",
            currency_raw="MGA",
            price_mga_per_base=1.25,
            base_unit="kg",
            conversion_status="exact",
            observed_or_imputed="observed",
        )
    if kind == "stock":
        return db.StockObservation(
            **common,
            location_id=location.location_id,
            location_raw="synthetic",
            quantity_raw="1.25",
            quantity_value=1.25,
            quantity_base=1.25,
            unit_raw="kg",
            base_unit="kg",
        )
    return db.TradeFlow(
        **common,
        flow="import",
        partner_iso3=None,
        weight_raw="1.25",
        weight_kg=1.25,
        value_raw="10",
        value_mga=10,
    )


def snapshot(connection, row, *, omit_link=False):
    expression = "to_jsonb(t) - 'superseded_by'" if omit_link else "to_jsonb(t)"
    return connection.scalar(
        text(
            f"SELECT ({expression})::text FROM {row.__table__.fullname} t WHERE observation_id=:id"
        ),
        {"id": row.observation_id},
    )


def quarantine(session, row, *, source=False):
    identifier = row.source_record_id if source else row.observation_id
    session.add(
        db.QuarantineLedger(
            quarantine_id=uuid4(),
            table_name="meta.source_record" if source else row.__table__.fullname,
            observation_id=identifier,
            source_record_id=row.source_record_id,
            reason_code="TEST_FIXTURE_ISOLATION",
            details={"synthetic": True},
        )
    )
    session.flush()


@pytest.mark.parametrize("kind", ("price", "stock", "trade"))
@pytest.mark.parametrize("mode", ("copy", "existing", "short_key"))
def test_reconcile_preserves_raw_fields_and_is_idempotent(normalization_case, kind, mode):
    session, connection, old, target, refs, location = normalization_case
    row = make_row(kind, old, refs[0], location, short=mode == "short_key")
    session.add(row)
    existing = make_row(kind, target, refs[1], location) if mode == "existing" else None
    if existing is not None:
        session.add(existing)
    session.flush()
    before = snapshot(connection, row, omit_link=True)
    stats = reconcile.reconcile_products(session)
    assert (
        stats[
            "prices_reconciled"
            if kind == "price"
            else "stocks_reconciled"
            if kind == "stock"
            else "trades_reconciled"
        ]
        == 1
    )
    assert snapshot(connection, row, omit_link=True) == before
    assert row.superseded_by is not None
    new = session.get(type(row), row.superseded_by)
    assert new is not None and new.product_id == target.product_id
    if existing is not None:
        assert new.observation_id == existing.observation_id
    else:
        assert new.source_record_id == row.source_record_id
        assert new.evidence["reconciled_from"] == old.product_code
    assert reconcile.reconcile_products(session) == {
        "prices_reconciled": 0,
        "stocks_reconciled": 0,
        "trades_reconciled": 0,
    }


@pytest.mark.parametrize("kind", ("price", "stock", "trade"))
@pytest.mark.parametrize("blocked", ("parent", "source", "target", "target_source"))
def test_reconcile_refuses_quarantined_parent_source_and_target(normalization_case, kind, blocked):
    session, connection, old, target, refs, location = normalization_case
    row = make_row(kind, old, refs[0], location)
    session.add(row)
    other = make_row(kind, target, refs[1], location) if blocked.startswith("target") else None
    if other is not None:
        session.add(other)
    session.flush()
    quarantine(
        session, other if other is not None else row, source=blocked in ("source", "target_source")
    )
    before = snapshot(connection, row)
    with pytest.raises(ValueError, match="quarantined"):
        reconcile.reconcile_products(session)
    assert snapshot(connection, row) == before
    assert row.superseded_by is None


@pytest.mark.parametrize("kind", ("price", "stock", "trade"))
@pytest.mark.parametrize("same_source", (True, False))
def test_migration_quarantines_only_same_source_normalization_copies(
    normalization_case, kind, same_source, monkeypatch
):
    session, connection, old, target, refs, location = normalization_case
    parent = make_row(kind, old, refs[0], location)
    child = make_row(kind, target, refs[0] if same_source else refs[1], location)
    child.evidence = {"synthetic": True, "reconciled_from": old.product_code}
    session.add_all([parent, child])
    session.flush()
    quarantine(session, parent)
    parent.superseded_by = child.observation_id
    session.flush()
    before = snapshot(connection, child)
    forecast = None
    if kind == "price":
        run = db.ModelRun(
            model_run_id=uuid4(),
            task="forecast",
            model_name="synthetic",
            model_version="fixture",
            data_cutoff=date(2026, 10, 1),
            trained_at=datetime.now(UTC),
            params={"cohort": "pure_observed"},
        )
        forecast = db.Forecast(
            forecast_id=uuid4(),
            model_run_id=run.model_run_id,
            series_key="synthetic_" + uuid4().hex,
            product_id=target.product_id,
            location_id=location.location_id,
            actor_level="retail",
            target_period=date(2026, 11, 1),
            horizon=1,
            p10=1,
            p50=2,
            p90=3,
        )
        session.add_all([run, forecast])
        session.flush()
    path = Path(__file__).parents[2] / "alembic/versions/0027_quarantined_normalization_copies.py"
    spec = importlib.util.spec_from_file_location("normalization_copy_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setattr(
        migration, "op", SimpleNamespace(execute=lambda sql: connection.execute(text(sql)))
    )
    migration.upgrade()
    count = connection.scalar(
        text(
            "SELECT count(*) FROM obs.quarantine_ledger WHERE table_name=:table AND observation_id=:id AND revoked_at IS NULL"
        ),
        {"table": child.__table__.fullname, "id": child.observation_id},
    )
    assert count == int(same_source)
    if forecast is not None:
        assert connection.scalar(
            text(
                "SELECT count(*) FROM obs.quarantine_ledger WHERE table_name='ml.forecast' AND observation_id=:id AND revoked_at IS NULL"
            ),
            {"id": forecast.forecast_id},
        ) == int(same_source)
    migration.upgrade()
    assert snapshot(connection, child) == before
    assert (
        connection.scalar(
            text(
                "SELECT count(*) FROM obs.quarantine_ledger WHERE table_name=:table AND observation_id=:id AND revoked_at IS NULL"
            ),
            {"table": child.__table__.fullname, "id": child.observation_id},
        )
        == count
    )
