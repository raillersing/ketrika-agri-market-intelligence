"""Gold-only copilot privileges, including latent/inherited SQL grants."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ketrika.core.db import get_engine
from ketrika.core.qualification import require_synthetic_test_database


@pytest.fixture
def migration_connection(monkeypatch):
    engine = get_engine()
    require_synthetic_test_database(engine.url.host, engine.url.database)
    path = Path(__file__).parents[2] / "alembic/versions/0023_copilot_gold_only.py"
    spec = importlib.util.spec_from_file_location("copilot_gold_only_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.connect() as connection:
        transaction = connection.begin()
        monkeypatch.setattr(
            module, "op", SimpleNamespace(execute=lambda sql: connection.execute(text(sql)))
        )
        try:
            yield module, connection
        finally:
            transaction.rollback()


def can_select(connection, role, table):
    return connection.scalar(
        text("SELECT has_table_privilege(:role,:table,'SELECT')"),
        {"role": role, "table": table},
    )


def test_received_schema_has_no_latent_copilot_quarantine_grant(migration_connection):
    _, connection = migration_connection
    assert can_select(connection, "copilot_ro", "obs.quarantine_ledger") is False
    assert can_select(connection, "copilot_ro", "gold.price_monthly") is True
    connection.execute(text("SET LOCAL ROLE copilot_ro"))
    assert connection.scalar(text("SELECT current_user")) == "copilot_ro"
    connection.execute(text("EXPLAIN SELECT * FROM gold.price_monthly"))
    with pytest.raises(DBAPIError, match="permission denied"):
        with connection.begin_nested():
            connection.execute(text("SELECT * FROM obs.quarantine_ledger LIMIT 1"))


def test_upgrade_removes_only_copilot_grant_and_is_idempotent(migration_connection):
    migration, connection = migration_connection
    app_before = can_select(connection, "ketrika_app", "obs.quarantine_ledger")
    gold_before = can_select(connection, "copilot_ro", "gold.price_monthly")
    count_before = connection.scalar(text("SELECT count(*) FROM obs.quarantine_ledger"))
    connection.execute(text("GRANT SELECT ON obs.quarantine_ledger TO copilot_ro"))
    assert can_select(connection, "copilot_ro", "obs.quarantine_ledger") is True
    migration.upgrade()
    migration.upgrade()
    assert can_select(connection, "copilot_ro", "obs.quarantine_ledger") is False
    assert can_select(connection, "ketrika_app", "obs.quarantine_ledger") == app_before
    assert can_select(connection, "copilot_ro", "gold.price_monthly") == gold_before
    assert connection.scalar(text("SELECT count(*) FROM obs.quarantine_ledger")) == count_before
    migration.downgrade()
    assert can_select(connection, "copilot_ro", "obs.quarantine_ledger") is False


def test_inherited_public_privilege_requires_review_and_rolls_back(migration_connection):
    migration, connection = migration_connection
    connection.execute(text("GRANT SELECT ON obs.quarantine_ledger TO PUBLIC,copilot_ro"))
    before = connection.scalar(
        text("SELECT relacl::text FROM pg_class WHERE oid='obs.quarantine_ledger'::regclass")
    )
    with pytest.raises(DBAPIError, match="explicit role review required"):
        with connection.begin_nested():
            migration.upgrade()
    assert can_select(connection, "copilot_ro", "obs.quarantine_ledger") is True
    assert (
        connection.scalar(
            text("SELECT relacl::text FROM pg_class WHERE oid='obs.quarantine_ledger'::regclass")
        )
        == before
    )
