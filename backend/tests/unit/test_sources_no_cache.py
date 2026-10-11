"""Simulated DataOps query contracts; actual SQL/API still required."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from ketrika.api.errors import ProblemDetailException
from ketrika.api.routers.sources import get_source_health, list_sources


@pytest.mark.parametrize("populated", [True, False, None])
def test_list_always_reports_meta_run_and_unpublished_freshness_is_null(populated):
    session = MagicMock()
    session.scalar.return_value = populated
    started = datetime(2026, 10, 11, tzinfo=UTC)
    session.execute.return_value.fetchall.return_value = [
        (
            "synthetic",
            "Synthetic",
            "P2",
            "disabled",
            15,
            3 if populated else None,
            False if populated else None,
            "failed",
            started,
        )
    ]
    result = list_sources(session)
    assert result[0].latest_run_status == "failed" and result[0].last_run_started_at == started
    sql = str(session.execute.call_args.args[0])
    assert "lr.latest_run_status AS latest_run_status" in sql
    assert "ir.run_id DESC" in sql and "COALESCE(sh.latest_run_status" not in sql
    if populated:
        assert "LEFT JOIN gold.source_health" in sql
    else:
        assert "gold.source_health" not in sql
        assert result[0].freshness_days is None and result[0].is_stale is None
    session.commit.assert_not_called()


@pytest.mark.parametrize("populated", [False, None])
def test_dedicated_health_without_cache_returns_503_never_empty_health(populated):
    session = MagicMock()
    session.scalar.return_value = populated
    with pytest.raises(ProblemDetailException) as failure:
        get_source_health("synthetic", session)
    assert failure.value.status_code == 503 and failure.value.type_uri == "about:blank"
    session.execute.assert_not_called()


def test_health_preserves_cached_metrics_but_queries_current_meta_run():
    session = MagicMock()
    session.scalar.return_value = True
    started = datetime(2026, 10, 11, tzinfo=UTC)
    session.execute.return_value.fetchone.return_value = (
        "synthetic",
        "Synthetic",
        "P2",
        15,
        3,
        False,
        "failed",
        started,
        4,
        0.75,
        2,
    )
    result = get_source_health("synthetic", session)
    assert result.latest_run_status == "failed" and result.last_run_started_at == started
    assert result.parse_success_rate == 0.75 and result.n_records_30d == 4
    sql = str(session.execute.call_args.args[0])
    assert "meta.ingestion_run" in sql and "lr.latest_run_status" in sql
    assert session.execute.call_args.args[1] == {"sid": "synthetic"}


@pytest.mark.parametrize("endpoint", ["list", "health"])
def test_catalog_errors_are_not_absorbed_as_unknown_or_fake_healthy(endpoint):
    session = MagicMock()
    session.scalar.side_effect = RuntimeError("simulated SQL transport failure")
    with pytest.raises(RuntimeError, match="simulated SQL transport failure"):
        if endpoint == "list":
            list_sources(session)
        else:
            get_source_health("synthetic", session)
    session.execute.assert_not_called()
