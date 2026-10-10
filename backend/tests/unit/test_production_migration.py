"""Mocked additive migration intent; SQL preservation qualified separately."""

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


def migration() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0004_production_raw.py"
    spec = importlib.util.spec_from_file_location("production_migration_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_adds_only_nullable_raw_column() -> None:
    module = migration()
    with patch.object(module.op, "execute") as execute:
        module.upgrade()
    execute.assert_called_once_with(
        "ALTER TABLE obs.production_observation ADD COLUMN value_raw TEXT"
    )


def test_downgrade_refuses_to_discard_lexemes() -> None:
    module = migration()
    bind = MagicMock()
    bind.scalar.return_value = True
    with (
        patch.object(module.op, "get_bind", return_value=bind),
        patch.object(module.op, "execute") as execute,
    ):
        with pytest.raises(RuntimeError, match="discard source lexemes"):
            module.downgrade()
        execute.assert_not_called()
