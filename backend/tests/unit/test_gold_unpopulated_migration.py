"""Migration intent only; these mocks do not prove SQL preservation."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock


def migration():
    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0005_gold_unpopulated.py"
    spec = importlib.util.spec_from_file_location("gold_unpopulated_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = MagicMock()
    return module


def test_upgrade_only_recreates_unpopulated_gold_and_permissions() -> None:
    module = migration()
    module.upgrade()
    statements = [call.args[0] for call in module.op.execute.call_args_list]
    assert len(statements) == 13
    for statement in statements[:12]:
        assert "WITH NO DATA;" in statement
        assert "DROP MATERIALIZED VIEW IF EXISTS gold." in statement
        assert "CREATE MATERIALIZED VIEW gold." in statement
        assert "TRUNCATE" not in statement and "DELETE FROM" not in statement
        assert "UPDATE obs." not in statement and "ALTER TABLE obs." not in statement
    assert statements[-1].startswith("GRANT USAGE ON SCHEMA gold")


def test_downgrade_never_republishes_unverified_old_caches() -> None:
    module = migration()
    module.downgrade()
    module.op.execute.assert_not_called()
