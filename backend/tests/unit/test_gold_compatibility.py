"""Tests for automated pre-control and upgrade of historical Gold definitions (BL-019)."""

from pathlib import Path
from unittest.mock import MagicMock

from ketrika.gold.compatibility import (
    check_and_upgrade_historical_gold_definitions,
    get_gold_sql_dir,
    is_gold_definition_outdated,
)


def test_get_gold_sql_dir() -> None:
    """Verify that Gold SQL directory is resolved and contains all 14 definitions."""
    sql_dir = get_gold_sql_dir()
    assert sql_dir.exists()
    sql_files = list(sql_dir.glob("*.sql"))
    assert len(sql_files) >= 14


def test_is_gold_definition_outdated_query_execution() -> None:
    """Verify that is_gold_definition_outdated executes the proper attribute inspection query."""
    mock_bind = MagicMock()
    mock_cursor = MagicMock()
    mock_bind.execute.return_value = mock_cursor

    # Case 1: outdated (query returns 1)
    mock_cursor.scalar.return_value = 1
    assert is_gold_definition_outdated(mock_bind) is True

    # Case 2: compliant (query returns None)
    mock_cursor.scalar.return_value = None
    assert is_gold_definition_outdated(mock_bind) is False


def test_check_and_upgrade_noop_when_compliant() -> None:
    """Verify that check_and_upgrade_historical_gold_definitions is a no-op when already compliant."""
    mock_bind = MagicMock()
    mock_cursor = MagicMock()
    mock_bind.execute.return_value = mock_cursor
    mock_cursor.scalar.return_value = None  # Already compliant

    upgraded = check_and_upgrade_historical_gold_definitions(mock_bind)
    assert upgraded is False
    # Only the initial check query was executed
    assert mock_bind.execute.call_count == 1


def test_check_and_upgrade_executes_up_to_cutoff_with_no_data() -> None:
    """Verify that check_and_upgrade executes views up to cutoff WITH NO DATA when outdated."""
    mock_bind = MagicMock()
    mock_cursor = MagicMock()
    # First call is check query (returns 1 -> outdated), subsequent calls execute view DDLs
    mock_cursor.scalar.return_value = 1
    mock_bind.execute.return_value = mock_cursor

    upgraded = check_and_upgrade_historical_gold_definitions(mock_bind, target_cutoff_index=12)
    assert upgraded is True

    # Verify that execute was called for 1 check query + 12 view DDL files
    assert mock_bind.execute.call_count == 13

    # Verify all executed view DDLs contain WITH NO DATA;
    executed_statements = [call_args[0][0] for call_args in mock_bind.execute.call_args_list[1:]]
    for stmt in executed_statements:
        assert "WITH NO DATA;" in str(stmt.text)


def test_historical_upgrade_uses_pre_quarantine_definitions() -> None:
    """Migration0018 cannot read a table introduced by0020 on fresh or legacy DBs."""
    mock_bind = MagicMock()
    mock_bind.execute.return_value.scalar.return_value = 1
    directory = Path(__file__).resolve().parents[2] / "alembic/sql/pre_0020"
    assert check_and_upgrade_historical_gold_definitions(mock_bind, sql_directory=directory)
    statements = [str(call.args[0]) for call in mock_bind.execute.call_args_list[1:]]
    assert len(statements) == 12
    assert all("quarantine_ledger" not in statement for statement in statements)
    assert all("WITH NO DATA;" in statement for statement in statements)
