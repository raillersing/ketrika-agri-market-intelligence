"""Real PostgreSQL cycle guards; graph probes never enter observation/Bronze tables."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ketrika.core.db import get_engine
from ketrika.core.qualification import require_synthetic_test_database


@pytest.fixture
def graph(request):
    engine = get_engine()
    require_synthetic_test_database(engine.url.host, engine.url.database)
    schema = "qa_cycle_" + uuid4().hex
    table = schema + ".graph"
    ids = [uuid4() for _ in range(4)]
    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
        connection.execute(
            text(
                f"CREATE TABLE {table} (observation_id uuid PRIMARY KEY, "
                f"superseded_by uuid REFERENCES {table}(observation_id) "
                "DEFERRABLE INITIALLY DEFERRED, raw_value integer NOT NULL, source_record_id uuid)"
            )
        )
        historical = getattr(request, "param", False)
        connection.execute(
            text(
                f"INSERT INTO {table} (observation_id,superseded_by,raw_value,source_record_id) "
                "VALUES (:id,:superseded,:value,:source)"
            ),
            [
                {
                    "id": identifier,
                    "value": index + 10,
                    "superseded": identifier if historical and index == 0 else None,
                    "source": uuid4() if historical == "mismatch" and index == 0 else None,
                }
                for index, identifier in enumerate(ids)
            ],
        )
        for name, function, operations in (
            ("legacy_guard", "check_obs_superseded_only", "INSERT OR UPDATE OR DELETE"),
            ("zz_cycle_guard", "check_supersession_acyclic", "INSERT OR UPDATE"),
        ):
            connection.execute(
                text(
                    f"CREATE TRIGGER {name} BEFORE {operations} ON {table} "
                    f"FOR EACH ROW EXECUTE FUNCTION obs.{function}()"
                )
            )
    try:
        yield engine, table, ids
    finally:
        # Only this test's unique graph schema, never any application data.
        with engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))


def link(connection, table, previous, replacement):
    connection.execute(
        text(f"UPDATE {table} SET superseded_by = :new WHERE observation_id = :old"),
        {"old": previous, "new": replacement},
    )


def test_cycle_guard_installed_on_every_observation_table():
    engine = get_engine()
    require_synthetic_test_database(engine.url.host, engine.url.database)
    with engine.connect() as connection:
        tables = connection.scalars(
            text(
                "SELECT c.relname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='obs' AND t.tgname='trg_zz_obs_supersession_cycle' "
                "AND t.tgenabled='O' ORDER BY c.relname"
            )
        ).all()
    assert tables == sorted(
        [
            "price_observation",
            "stock_observation",
            "trade_flow",
            "production_observation",
            "cpi_observation",
            "weather_observation",
            "macro_observation",
        ]
    )


def test_valid_chain_preserves_raw_values(graph):
    engine, table, ids = graph
    with engine.begin() as connection:
        link(connection, table, ids[0], ids[1])
        link(connection, table, ids[1], ids[2])
        values = (
            connection.execute(text(f"SELECT raw_value FROM {table} ORDER BY raw_value"))
            .scalars()
            .all()
        )
        assert values == [10, 11, 12, 13]
        assert (
            connection.scalar(text(f"SELECT count(*) FROM {table} WHERE superseded_by IS NOT NULL"))
            == 2
        )


@pytest.mark.parametrize("length", [2, 3, 4])
def test_multi_row_cycles_are_rejected(graph, length):
    engine, table, ids = graph
    with engine.begin() as connection:
        for previous, replacement in zip(ids[: length - 1], ids[1:length], strict=True):
            link(connection, table, previous, replacement)
        with pytest.raises(DBAPIError, match="Supersession cycle is forbidden"):
            with connection.begin_nested():
                link(connection, table, ids[length - 1], ids[0])
        assert (
            connection.scalar(text(f"SELECT count(*) FROM {table} WHERE superseded_by IS NOT NULL"))
            == length - 1
        )


def test_deferred_insert_cannot_close_a_cycle(graph):
    engine, table, _ = graph
    a, b = uuid4(), uuid4()
    with engine.begin() as connection:
        with pytest.raises(DBAPIError, match="Supersession cycle is forbidden"):
            with connection.begin_nested():
                connection.execute(
                    text(
                        f"INSERT INTO {table} (observation_id,superseded_by,raw_value) VALUES (:a,:b,20)"
                    ),
                    {"a": a, "b": b},
                )
                connection.execute(
                    text(
                        f"INSERT INTO {table} (observation_id,superseded_by,raw_value) VALUES (:b,:a,30)"
                    ),
                    {"a": a, "b": b},
                )
        assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 4


def test_cycle_guard_does_not_weaken_immutability(graph):
    engine, table, ids = graph
    with engine.begin() as connection:
        for statement in (
            f"UPDATE {table} SET raw_value=99, superseded_by=:other WHERE observation_id=:id",
            f"DELETE FROM {table} WHERE observation_id=:id",
        ):
            with pytest.raises(DBAPIError, match="forbidden"):
                with connection.begin_nested():
                    connection.execute(text(statement), {"id": ids[0], "other": ids[1]})
        link(connection, table, ids[0], ids[1])
        with pytest.raises(DBAPIError, match="already superseded"):
            with connection.begin_nested():
                link(connection, table, ids[0], ids[2])


@pytest.mark.parametrize(
    "reason,graph,allowed",
    [
        ("MANUAL_INVESTIGATION", True, False),
        ("HISTORICAL_SELF_LINK", True, True),
        ("HISTORICAL_SELF_LINK", "mismatch", False),
    ],
    indirect=["graph"],
)
def test_historical_repair_requires_permanent_matching_quarantine(graph, reason, allowed):
    engine, table, ids = graph
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(
                text(
                    "INSERT INTO obs.quarantine_ledger "
                    "(table_name,observation_id,reason_code,operator) VALUES (:table,:id,:reason,'pytest_graph')"
                ),
                {"table": table, "id": ids[0], "reason": reason},
            )
            if allowed:
                link(connection, table, ids[0], None)
                assert (
                    connection.scalar(
                        text(f"SELECT superseded_by FROM {table} WHERE observation_id=:id"),
                        {"id": ids[0]},
                    )
                    is None
                )
            else:
                with pytest.raises(DBAPIError, match="matching permanent quarantine"):
                    with connection.begin_nested():
                        link(connection, table, ids[0], None)
        finally:
            transaction.rollback()


def test_application_role_can_revise_but_cannot_create_a_cycle(graph):
    engine, table, ids = graph
    schema = table.split(".")[0]
    with engine.begin() as connection:
        connection.execute(text(f"GRANT USAGE ON SCHEMA {schema} TO ketrika_app"))
        connection.execute(text(f"GRANT SELECT,UPDATE ON {table} TO ketrika_app"))
        connection.execute(text("SET LOCAL ROLE ketrika_app"))
        link(connection, table, ids[0], ids[1])
        with pytest.raises(DBAPIError, match="Supersession cycle is forbidden"):
            with connection.begin_nested():
                link(connection, table, ids[1], ids[0])


@pytest.mark.parametrize("isolation", ["READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"])
def test_concurrent_opposite_edges_cannot_both_commit(graph, isolation):
    engine, table, ids = graph
    barrier = Barrier(2)

    def revise(previous, replacement):
        try:
            with engine.connect().execution_options(isolation_level=isolation) as connection:
                with connection.begin():
                    connection.execute(text("SET LOCAL statement_timeout='15s'"))
                    connection.execute(
                        text(
                            f"SELECT observation_id FROM {table} WHERE observation_id=:id FOR UPDATE"
                        ),
                        {"id": previous},
                    )
                    barrier.wait(timeout=10)
                    link(connection, table, previous, replacement)
            return "committed"
        except DBAPIError as error:
            return error.orig.sqlstate

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(revise, ids[0], ids[1]), executor.submit(revise, ids[1], ids[0])]
        outcomes = [future.result(timeout=20) for future in futures]
    assert outcomes.count("committed") == 1, outcomes
    assert set(outcomes) <= {"committed", "40P01", "40001"}, outcomes
    with engine.connect() as connection:
        assert (
            connection.scalar(text(f"SELECT count(*) FROM {table} WHERE superseded_by IS NOT NULL"))
            == 1
        )
        assert (
            connection.scalar(
                text(
                    f"SELECT count(*) FROM {table} a JOIN {table} b ON a.superseded_by=b.observation_id WHERE b.superseded_by=a.observation_id"
                )
            )
            == 0
        )
