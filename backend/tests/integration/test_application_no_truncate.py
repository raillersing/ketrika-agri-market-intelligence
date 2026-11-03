"""Runtime role cannot erase append-only tables; actual SQL on isolated QA only."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ketrika.core.db import get_engine
from ketrika.core.qualification import require_synthetic_test_database


@pytest.fixture
def application_permissions(monkeypatch):
    engine = get_engine()
    require_synthetic_test_database(engine.url.host, engine.url.database)
    path = Path(__file__).parents[2] / "alembic/versions/0025_application_no_truncate.py"
    spec = importlib.util.spec_from_file_location("application_no_truncate", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.connect() as connection:
        transaction = connection.begin()
        monkeypatch.setattr(
            migration, "op", SimpleNamespace(execute=lambda sql: connection.execute(text(sql)))
        )
        try:
            yield migration, connection
        finally:
            transaction.rollback()


def other_permissions(connection):
    return connection.execute(
        text("""
        SELECT n.nspname,c.relname,a.grantee,a.grantor,a.privilege_type,a.is_grantable
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a
        WHERE n.nspname IN ('auth','dq','meta','ml','obs','ops','ref')
          AND c.relkind IN ('r','p') AND a.privilege_type <> 'TRUNCATE'
        ORDER BY 1,2,3,4,5,6
    """)
    ).all()


def test_application_cannot_erase_quarantine_witness(application_permissions):
    migration, connection = application_permissions
    migration.upgrade()
    identifier = uuid4()
    connection.execute(
        text(
            "INSERT INTO obs.quarantine_ledger(table_name,observation_id,reason_code,details) VALUES ('obs.price_observation',:id,'TEST_FIXTURE_ISOLATION',jsonb_build_object('synthetic',true))"
        ),
        {"id": identifier},
    )
    before = connection.scalar(
        text("SELECT to_jsonb(q)::text FROM obs.quarantine_ledger q WHERE observation_id=:id"),
        {"id": identifier},
    )
    connection.execute(text("SET LOCAL ROLE ketrika_app"))
    with pytest.raises(DBAPIError, match="permission denied"):
        with connection.begin_nested():
            connection.execute(text("TRUNCATE obs.quarantine_ledger"))
    assert (
        connection.scalar(
            text("SELECT to_jsonb(q)::text FROM obs.quarantine_ledger q WHERE observation_id=:id"),
            {"id": identifier},
        )
        == before
    )


@pytest.mark.parametrize("schema", ("auth", "dq", "meta", "ml", "obs", "ops", "ref"))
def test_only_truncate_is_removed_and_new_tables_remain_writable(application_permissions, schema):
    migration, connection = application_permissions
    connection.execute(text("GRANT TRUNCATE ON obs.quarantine_ledger TO ketrika_app"))
    connection.execute(
        text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT TRUNCATE ON TABLES TO ketrika_app")
    )
    before = other_permissions(connection)
    migration.upgrade()
    migration.upgrade()
    assert other_permissions(connection) == before
    assert (
        connection.scalar(
            text("SELECT has_table_privilege(current_user,'obs.quarantine_ledger','TRUNCATE')")
        )
        is True
    )
    assert (
        connection.scalar(
            text("SELECT has_table_privilege('ketrika_app','obs.quarantine_ledger','TRUNCATE')")
        )
        is False
    )
    table = schema + ".synthetic_permissions_" + uuid4().hex
    connection.execute(text(f"CREATE TABLE {table}(value integer)"))
    migration.downgrade()
    connection.execute(text("SET LOCAL ROLE ketrika_app"))
    connection.execute(text(f"INSERT INTO {table} VALUES (1)"))
    connection.execute(text(f"UPDATE {table} SET value=2"))
    with pytest.raises(DBAPIError, match="permission denied"):
        with connection.begin_nested():
            connection.execute(text(f"TRUNCATE {table}"))
    assert connection.scalar(text(f"SELECT value FROM {table}")) == 2
    connection.execute(text(f"DELETE FROM {table}"))
    assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0


@pytest.mark.parametrize("grant_kind", ("public", "inherited", "global_default"))
def test_effective_foreign_grants_require_review_and_roll_back(application_permissions, grant_kind):
    migration, connection = application_permissions
    connection.execute(text("GRANT TRUNCATE ON obs.quarantine_ledger TO ketrika_app"))
    if grant_kind == "global_default":
        connection.execute(text("ALTER DEFAULT PRIVILEGES GRANT TRUNCATE ON TABLES TO PUBLIC"))
    else:
        role = "PUBLIC"
        if grant_kind == "inherited":
            role = "synthetic_inherit_" + uuid4().hex
            connection.execute(text(f"CREATE ROLE {role} NOLOGIN"))
            connection.execute(text(f"GRANT {role} TO ketrika_app"))
        connection.execute(text(f"GRANT TRUNCATE ON obs.quarantine_ledger TO {role}"))
    before = connection.scalar(
        text("SELECT relacl::text FROM pg_class WHERE oid='obs.quarantine_ledger'::regclass")
    )
    defaults = connection.execute(
        text("SELECT oid,defaclacl::text FROM pg_default_acl ORDER BY oid")
    ).all()
    with pytest.raises(DBAPIError, match="explicit role review"):
        with connection.begin_nested():
            migration.upgrade()
    assert (
        connection.scalar(
            text("SELECT relacl::text FROM pg_class WHERE oid='obs.quarantine_ledger'::regclass")
        )
        == before
    )
    assert (
        connection.execute(
            text("SELECT oid,defaclacl::text FROM pg_default_acl ORDER BY oid")
        ).all()
        == defaults
    )
