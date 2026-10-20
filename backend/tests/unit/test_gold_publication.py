"""Publication control intent with mocks, never proof of SQL atomicity."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ketrika.gold.provenance_gate import PublicationCheck
from ketrika.gold.refresh import (
    ORDERED_GOLD_VIEWS,
    init_gold_views,
    publication_views,
    refresh_gold_views,
)


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        (["price_changes"], ORDERED_GOLD_VIEWS[:4]),
        (
            ["market_health"],
            [*ORDERED_GOLD_VIEWS[:5], "weather_monthly", "market_health"],
        ),
        (["weather_monthly"], ["weather_monthly"]),
    ],
)
def test_dependency_closure_never_reuses_an_old_ancestor(requested, expected) -> None:
    assert publication_views(requested) == expected


def refreshes(session: MagicMock) -> list[str]:
    return [
        str(call.args[0])
        for call in session.execute.call_args_list
        if str(call.args[0]).startswith("REFRESH")
    ]


@pytest.mark.parametrize(
    "views", [[], ["unknown"], ["weather_monthly; DROP TABLE obs.weather_observation"]]
)
def test_bad_views_refused_before_any_database_or_audit(views) -> None:
    session = MagicMock(spec=Session)
    with patch("ketrika.gold.refresh.require_gold_provenance") as audit:
        with pytest.raises(ValueError, match="unsupported_gold_view"):
            refresh_gold_views(session, views=views, reader=MagicMock())
    session.execute.assert_not_called()
    audit.assert_not_called()


def test_missing_view_is_failure_not_skip() -> None:
    session = MagicMock(spec=Session)
    session.execute.return_value.scalar.return_value = None
    with patch("ketrika.gold.refresh.require_gold_provenance") as audit:
        with pytest.raises(ValueError, match="gold_view_missing"):
            refresh_gold_views(session, views=["weather_monthly"], reader=MagicMock())
    audit.assert_not_called()
    assert not refreshes(session)


def test_topological_deduplication_and_empty_result_never_claim_100_percent() -> None:
    session, reader = MagicMock(spec=Session), MagicMock()
    session.execute.return_value.scalar.return_value = 1
    with patch(
        "ketrika.gold.refresh.require_gold_provenance",
        return_value=PublicationCheck("empty", (), None),
    ) as audit:
        result = refresh_gold_views(
            session, views=["price_monthly", "price_obs_current", "price_monthly"], reader=reader
        )
    audit.assert_called_once_with(session, reader, ["price_obs_current", "price_monthly"])
    assert result["views_refreshed"] == ["price_obs_current", "price_monthly"]
    assert result["count"] == 2 and result["errors"] == {}
    assert result["source_observations_total"] == result["source_observations_valid"] == 0
    assert result["source_cell_rate"] is None and result["source_cell_dq_id"] is None
    assert result["provenance_state"] == "empty"
    assert result["provenance_scope"] == "source_cells_not_authenticity_conversions_or_model"
    assert session.begin_nested.call_count == 1
    session.commit.assert_not_called()


def test_failed_audit_never_executes_refresh() -> None:
    session = MagicMock(spec=Session)
    session.execute.return_value.scalar.return_value = 1
    with patch(
        "ketrika.gold.refresh.require_gold_provenance",
        side_effect=ValueError("gold_provenance_rejected"),
    ):
        with pytest.raises(ValueError, match="gold_provenance_rejected"):
            refresh_gold_views(session, views=["weather_monthly"], reader=MagicMock())
    assert not refreshes(session)
    session.begin_nested.assert_not_called()


def test_sql_failure_propagates_sanitized_and_exits_whole_savepoint_with_error() -> None:
    session = MagicMock(spec=Session)

    def execute(statement, *args):
        if str(statement).startswith("REFRESH MATERIALIZED VIEW gold.price_monthly;"):
            raise SQLAlchemyError("secret simulated SQL detail")
        result = MagicMock()
        result.scalar.return_value = 1
        return result

    session.execute.side_effect = execute
    with patch(
        "ketrika.gold.refresh.require_gold_provenance",
        return_value=PublicationCheck("empty", (), None),
    ):
        with pytest.raises(ValueError) as error:
            refresh_gold_views(
                session, views=["price_obs_current", "price_monthly"], reader=MagicMock()
            )
    assert str(error.value) == "gold_publication_failed" and error.value.__suppress_context__
    assert session.begin_nested.return_value.__exit__.call_args.args[0] is SQLAlchemyError
    session.commit.assert_not_called()


def test_concurrent_failure_has_local_savepoint_before_nonconcurrent_retry() -> None:
    session = MagicMock(spec=Session)

    def execute(statement, *args):
        if str(statement).startswith("REFRESH MATERIALIZED VIEW CONCURRENTLY"):
            raise SQLAlchemyError("simulated first refresh failure")
        result = MagicMock()
        result.scalar.return_value = 1
        return result

    session.execute.side_effect = execute
    with patch(
        "ketrika.gold.refresh.require_gold_provenance",
        return_value=PublicationCheck("empty", (), None),
    ):
        result = refresh_gold_views(
            session, concurrently=True, views=["weather_monthly"], reader=MagicMock()
        )
    assert result["count"] == 1 and session.begin_nested.call_count == 2
    assert refreshes(session) == [
        "REFRESH MATERIALIZED VIEW CONCURRENTLY gold.weather_monthly;",
        "REFRESH MATERIALIZED VIEW gold.weather_monthly;",
    ]


def test_initialization_creates_all_views_unpopulated_without_certification() -> None:
    session = MagicMock(spec=Session)
    result = init_gold_views(session)
    assert result == {"views_initialized": len(ORDERED_GOLD_VIEWS), "views_populated": 0}
    statements = [str(call.args[0]) for call in session.execute.call_args_list]
    assert len(statements) == len(ORDERED_GOLD_VIEWS) + 1
    for view, statement in zip(
        ORDERED_GOLD_VIEWS, statements[: len(ORDERED_GOLD_VIEWS)], strict=True
    ):
        assert f"CREATE MATERIALIZED VIEW gold.{view} AS" in statement
        assert "WITH NO DATA;" in statement
    session.commit.assert_not_called()


def test_missing_schema_definition_refused_before_ddl(tmp_path: Path) -> None:
    session = MagicMock(spec=Session)
    with patch("ketrika.gold.refresh.get_sql_dir", return_value=tmp_path):
        with pytest.raises(ValueError, match="gold_schema_definition_missing"):
            init_gold_views(session)
    session.execute.assert_not_called()
