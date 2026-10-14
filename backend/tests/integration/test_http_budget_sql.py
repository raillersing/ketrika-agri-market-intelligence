"""Real dedicated PostgreSQL transactions; no cleanup of retained HTTP history."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from ketrika.core.db import get_engine, get_session
from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import Admission, SqlBudgetBackend
from ketrika.core.models.db import Source
from ketrika.core.policy import PolicyStop
from ketrika.core.qualification import require_synthetic_test_database

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 14, 23, 59, 59, 900000, tzinfo=UTC)


def admission():
    engine = get_engine()
    require_synthetic_test_database(engine.url.host, engine.url.database)
    name = "dummy_http_" + uuid4().hex
    return Admission(name, name + ".invalid", "https://" + name + ".invalid", 3, 3, 500)


def counts(item):
    with get_engine().connect() as connection:
        return dict(
            connection.execute(
                text(
                    "SELECT scope, request_count FROM meta.http_daily_budget WHERE scope_key IN (:source,:domain) AND day_utc=:day"
                ),
                {"source": item.source_id, "domain": item.domain, "day": NOW.date()},
            ).all()
        )


def test_sql_domain_exhaustion_preserves_source_counter_atomically():
    item = admission()
    backend = SqlBudgetBackend(get_engine())
    backend.reserve(replace(item, source_id=item.source_id + "_other", domain_limit=1), NOW)
    with pytest.raises(PolicyStop, match="exhausted"):
        backend.reserve(item, NOW)
    assert counts(item) == {"domain": 1, "source": 0}


def test_sql_source_exhaustion_commits_lower_cap_without_domain_increment():
    item = admission()
    backend = SqlBudgetBackend(get_engine())
    backend.reserve(item, NOW)
    with pytest.raises(PolicyStop, match="exhausted"):
        backend.reserve(replace(item, source_limit=0), NOW)
    with pytest.raises(PolicyStop, match="exhausted"):
        SqlBudgetBackend(get_engine()).reserve(item, NOW)
    assert counts(item) == {"domain": 1, "source": 1}


def test_sql_concurrent_workers_never_exceed_quota():
    item = admission()

    def reserve(_):
        try:
            SqlBudgetBackend(get_engine()).reserve(item, NOW)
            return True
        except PolicyStop as error:
            assert error.reason == "http_daily_budget_exhausted"
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(24))) == 3
    assert counts(item) == {"domain": 3, "source": 3}


def test_sql_quota_persists_across_real_process_restart():
    item = replace(admission(), source_limit=1)
    SqlBudgetBackend(get_engine()).reserve(item, NOW)
    code = (
        "from datetime import datetime; from ketrika.core.db import get_engine; "
        "from ketrika.core.http_budget import Admission, SqlBudgetBackend; "
        "from ketrika.core.policy import PolicyStop; "
        f"a=Admission({item.source_id!r},{item.domain!r},{item.origin!r},1,3,500); "
        f"now=datetime.fromisoformat({NOW.isoformat()!r}); "
        "\ntry: SqlBudgetBackend(get_engine()).reserve(a,now)"
        "\nexcept PolicyStop as error: assert error.reason=='http_daily_budget_exhausted'"
        "\nelse: raise AssertionError('quota bypass after restart')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert counts(item) == {"domain": 1, "source": 1}


def test_sql_midnight_resets_quota_not_shared_pacing():
    item = replace(admission(), max_rps=1)
    backend = SqlBudgetBackend(get_engine())
    assert backend.reserve(item, NOW) == 0
    assert backend.reserve(item, NOW + timedelta(seconds=0.2)) == pytest.approx(0.8)
    assert counts(item) == {"domain": 1, "source": 1}


def test_sql_challenge_stop_and_disabled_source_survive_restart():
    item = admission()
    with get_session() as session:
        session.add(
            Source(source_id=item.source_id, spec={"dataset": "synthetic"}, status="active")
        )
    SqlBudgetBackend(get_engine()).stop(item.source_id, item.origin, 403)
    with get_session() as session:
        assert session.get(Source, item.source_id).status == "disabled"
    with pytest.raises(PolicyStop, match="disabled"):
        SqlBudgetBackend(get_engine()).reserve(item, NOW)
    assert not counts(item)


def test_sql_stop_survives_outer_rollback_without_waiting_on_source_lock():
    item = admission()
    with get_session() as session:
        session.add(
            Source(source_id=item.source_id, spec={"dataset": "synthetic"}, status="active")
        )
    with pytest.raises(RuntimeError, match="outer_rollback"):
        with get_session() as session:
            session.execute(
                text("UPDATE meta.source SET status='degraded' WHERE source_id=:source"),
                {"source": item.source_id},
            )
            SqlBudgetBackend(get_engine()).stop(item.source_id, item.origin, 401)
            raise RuntimeError("outer_rollback")
    with get_session() as session:
        assert session.get(Source, item.source_id).status == "active"
    with pytest.raises(PolicyStop, match="disabled"):
        SqlBudgetBackend(get_engine()).check(item.source_id, item.origin)
    with get_engine().connect() as connection:
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM meta.http_policy_stop WHERE scope_key IN (:source,:origin)"
                ),
                {"source": item.source_id, "origin": item.origin},
            ).scalar_one()
            == 2
        )


def test_sql_tighter_domain_rate_is_shared_across_sources():
    item = admission()
    backend = SqlBudgetBackend(get_engine())
    assert backend.reserve(replace(item, max_rps=1), NOW) == 0
    assert (
        backend.reserve(replace(item, source_id=item.source_id + "_other", max_rps=0.2), NOW) == 1
    )
    assert backend.reserve(replace(item, max_rps=100), NOW) == 6


def test_http_client_default_sql_counts_robots_and_redirect_and_refuses_third_wire():
    item = admission()
    requests = []

    def handler(request):
        requests.append(request)
        return (
            httpx.Response(404)
            if request.url.path == "/robots.txt"
            else httpx.Response(302, headers={"Location": "/next"})
        )

    with PoliteHttpClient(transport=httpx.MockTransport(handler)) as client:
        assert isinstance(client.budget, SqlBudgetBackend)
        client.bind_source(item.source_id, 2, 5)
        with pytest.raises(PolicyStop, match="exhausted"):
            client.get(item.origin + "/data")
    assert [request.url.path for request in requests] == ["/robots.txt", "/data"]
    with get_engine().connect() as connection:
        rows = (
            connection.execute(
                text(
                    "SELECT request_count FROM meta.http_daily_budget WHERE scope_key IN (:source,:domain)"
                ),
                {"source": item.source_id, "domain": item.domain},
            )
            .scalars()
            .all()
        )
    assert sorted(rows) == [2, 2]


def test_http_challenge_persists_on_default_sql_client_before_retry_or_redirect():
    item = admission()
    with get_session() as session:
        session.add(
            Source(source_id=item.source_id, spec={"dataset": "synthetic"}, status="active")
        )
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(503, text="CAPTCHA", headers={"Location": "/next"})

    for restarted in (False, True):
        with PoliteHttpClient(transport=httpx.MockTransport(handler)) as client:
            client.bind_source(item.source_id, 3, 5)
            client.policy.set_robots_txt(item.origin, "User-agent: *\nDisallow:\n")
            with pytest.raises(PolicyStop, match="disabled" if restarted else "Challenge"):
                client.get(item.origin + "/data")
    assert len(requests) == 1
