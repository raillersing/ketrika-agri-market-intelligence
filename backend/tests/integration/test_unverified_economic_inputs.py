"""Actual SQL quarantine and Gold exclusion; all seeded records are synthetic."""

import hashlib
import importlib.util
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ketrika.core.db import get_engine
from ketrika.core.models.db import (
    Forecast,
    Location,
    ModelRun,
    PriceObservation,
    Product,
    SourceRecord,
)
from ketrika.core.qualification import require_synthetic_test_database


@pytest.fixture
def migration_case(monkeypatch):
    engine = get_engine()
    require_synthetic_test_database(engine.url.host, engine.url.database)
    path = Path(__file__).parents[2] / "alembic/versions/0024_unverified_economic_inputs.py"
    spec = importlib.util.spec_from_file_location("unverified_economic_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.connect() as connection:
        transaction = connection.begin()
        monkeypatch.setattr(
            migration, "op", SimpleNamespace(execute=lambda sql: connection.execute(text(sql)))
        )
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            try:
                yield migration, connection, session
            finally:
                session.close()
                transaction.rollback()


def seed(session, *, cohort="all", cutoff=date(2026, 10, 1)):
    identifier = uuid4()
    digest = hashlib.sha256(identifier.bytes).hexdigest()
    source = "douanes_stats"
    session.execute(
        text(
            "INSERT INTO meta.source(source_id,spec,status) VALUES (:source,'{}','active') ON CONFLICT DO NOTHING"
        ),
        {"source": source},
    )
    reference = SourceRecord(
        source_record_id=identifier,
        source_id=source,
        source_url="https://www.douanes.gov.mg/stats/import-parity-benchmarks",
        object_key="synthetic/" + digest,
        content_sha256=digest,
        mime_type="text/csv",
        parser_version="1.0.0",
        fetched_at=datetime.now(UTC),
    )
    product = session.scalar(select(Product).limit(1))
    location = session.scalar(select(Location).limit(1))
    assert product is not None and location is not None
    observation = PriceObservation(
        observation_id=uuid4(),
        source_record_id=identifier,
        product_id=product.product_id,
        location_id=location.location_id,
        natural_key="synthetic_economic_guard_" + identifier.hex,
        product_raw="synthetic",
        location_raw="synthetic",
        actor_level="retail",
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        price_raw="1.25",
        price_value=1.25,
        price_mga_per_base=1.25,
        currency_raw="MGA",
        unit_raw="kg",
        base_unit="kg",
        conversion_status="exact",
        observed_or_imputed="imputed",
        extraction_method="deterministic",
        evidence={"synthetic": True},
        confidence=0.5,
    )
    run = ModelRun(
        model_run_id=uuid4(),
        task="forecast",
        model_name="synthetic",
        model_version="fixture",
        data_cutoff=cutoff,
        trained_at=datetime.now(UTC),
        params={} if cohort is None else {"cohort": cohort},
    )
    forecast = Forecast(
        forecast_id=uuid4(),
        model_run_id=run.model_run_id,
        product_id=product.product_id,
        location_id=location.location_id,
        series_key="synthetic_" + identifier.hex,
        actor_level="retail",
        target_period=date(2026, 11, 1),
        horizon=1,
        p10=1,
        p50=2,
        p90=3,
    )
    session.add_all([reference, observation, run, forecast])
    session.flush()
    return reference, observation, forecast


@pytest.mark.parametrize(
    "cohort,cutoff,excluded",
    [
        ("all", date(2026, 10, 1), True),
        ("mixed", date(2026, 10, 1), True),
        (None, date(2026, 10, 1), True),
        ("pure_observed", date(2026, 10, 1), False),
        ("all", date(2026, 9, 1), False),
    ],
)
def test_quarantine_is_append_only_idempotent_and_filters_forecasts(
    migration_case, cohort, cutoff, excluded
):
    migration, connection, session = migration_case
    reference, observation, forecast = seed(session, cohort=cohort, cutoff=cutoff)
    targets = [
        ("meta.source_record", reference.source_record_id),
        ("obs.price_observation", observation.observation_id),
        ("ml.forecast", forecast.forecast_id),
    ]
    snapshots = [
        connection.scalar(
            text(
                f"SELECT to_jsonb(t)::text FROM {table} t WHERE {('source_record_id' if table == 'meta.source_record' else 'forecast_id' if table == 'ml.forecast' else 'observation_id')}=:id"
            ),
            {"id": identifier},
        )
        for table, identifier in targets
    ]
    acl = connection.scalar(
        text("SELECT relacl::text FROM pg_class WHERE oid='gold.forecast_latest'::regclass")
    )
    migration.upgrade()
    first_count = connection.scalar(text("SELECT count(*) FROM obs.quarantine_ledger"))
    migration.upgrade()
    assert connection.scalar(text("SELECT count(*) FROM obs.quarantine_ledger")) == first_count
    for (table, identifier), before in zip(targets, snapshots, strict=True):
        key = (
            "source_record_id"
            if table == "meta.source_record"
            else "forecast_id"
            if table == "ml.forecast"
            else "observation_id"
        )
        assert (
            connection.scalar(
                text(f"SELECT to_jsonb(t)::text FROM {table} t WHERE {key}=:id"), {"id": identifier}
            )
            == before
        )
        assert connection.scalar(
            text(
                "SELECT count(*) FROM obs.quarantine_ledger WHERE table_name=:table AND observation_id=:id AND revoked_at IS NULL"
            ),
            {"table": table, "id": identifier},
        ) == (int(excluded) if table == "ml.forecast" else 1)
    assert (
        connection.scalar(
            text("SELECT relacl::text FROM pg_class WHERE oid='gold.forecast_latest'::regclass")
        )
        == acl
    )
    connection.execute(text("REFRESH MATERIALIZED VIEW gold.forecast_latest"))
    assert connection.scalar(
        text("SELECT count(*) FROM gold.forecast_latest WHERE forecast_id=:id"),
        {"id": forecast.forecast_id},
    ) == int(not excluded)
    with pytest.raises(RuntimeError, match="Refusing"):
        migration.downgrade()


def test_unknown_forecast_acl_refuses_without_quarantine_mutation(migration_case):
    migration, connection, _ = migration_case
    before = connection.scalar(text("SELECT count(*) FROM obs.quarantine_ledger"))
    connection.execute(text("GRANT SELECT ON gold.forecast_latest TO PUBLIC"))
    with pytest.raises(DBAPIError, match="explicit role review"):
        with connection.begin_nested():
            migration.upgrade()
    assert connection.scalar(text("SELECT count(*) FROM obs.quarantine_ledger")) == before
    assert (
        connection.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE c.oid='gold.forecast_latest'::regclass AND a.grantee=0 AND a.privilege_type='SELECT')"
            )
        )
        is True
    )


def test_latest_valid_forecast_remains_when_newer_candidate_is_quarantined(migration_case):
    migration, connection, session = migration_case
    _, _, rejected = seed(session)
    valid_run = ModelRun(
        model_run_id=uuid4(),
        task="forecast",
        model_name="synthetic",
        model_version="fixture",
        data_cutoff=date(2026, 9, 1),
        trained_at=datetime(2026, 9, 1, tzinfo=UTC),
        params={"cohort": "pure_observed"},
    )
    retained = Forecast(
        forecast_id=uuid4(),
        model_run_id=valid_run.model_run_id,
        product_id=rejected.product_id,
        location_id=rejected.location_id,
        series_key=rejected.series_key,
        actor_level=rejected.actor_level,
        target_period=rejected.target_period,
        horizon=rejected.horizon,
        p10=1,
        p50=2,
        p90=3,
    )
    session.add_all([valid_run, retained])
    session.flush()
    migration.upgrade()
    connection.execute(text("REFRESH MATERIALIZED VIEW gold.forecast_latest"))
    assert connection.scalars(
        text("SELECT forecast_id FROM gold.forecast_latest WHERE series_key=:series"),
        {"series": rejected.series_key},
    ).all() == [retained.forecast_id]
