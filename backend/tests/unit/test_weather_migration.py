"""Migration intent and downgrade guard only; not SQL execution evidence."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


def migration() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0003_weather_provenance.py"
    spec = importlib.util.spec_from_file_location("weather_migration_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_downgrade_refuses_before_any_mutation_when_proof_exists() -> None:
    module = migration()
    bind = MagicMock()
    bind.scalar.return_value = True
    with (
        patch.object(module.op, "get_bind", return_value=bind),
        patch.object(module.op, "execute") as execute,
    ):
        with pytest.raises(RuntimeError, match="discard evidence/history"):
            module.downgrade()
        execute.assert_not_called()


def test_empty_legacy_columns_can_be_removed_without_deleting_observations() -> None:
    module = migration()
    bind = MagicMock()
    bind.scalar.return_value = False
    with (
        patch.object(module.op, "get_bind", return_value=bind),
        patch.object(module.op, "execute") as execute,
    ):
        module.downgrade()
    ddl = execute.call_args.args[0]
    assert "DROP COLUMN evidence" in ddl and "ADD CONSTRAINT uq_weather_obs" in ddl
    assert "DELETE FROM" not in ddl and "TRUNCATE" not in ddl and "DROP TABLE" not in ddl


def test_upgrade_is_additive_for_observations_and_targets_only_known_gold_views() -> None:
    module = migration()
    with patch.object(module.op, "execute") as execute:
        module.upgrade()
    statements = [call.args[0] for call in execute.call_args_list]
    assert len(statements) == 4
    assert "ADD COLUMN evidence JSONB" in statements[0]
    assert "CREATE UNIQUE INDEX weather_current_uk" in statements[0]
    assert "INITIALLY DEFERRED" in statements[0]
    assert "to_jsonb(wo)->>'superseded_by' IS NULL" in statements[1]
    assert "quarantine_ledger" not in statements[1]
    assert "gold.market_health" in statements[2]
    for statement in statements:
        assert "DELETE FROM" not in statement and "TRUNCATE" not in statement
        assert "UPDATE obs." not in statement and "DROP TABLE" not in statement
