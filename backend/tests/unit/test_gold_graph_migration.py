"""Frozen migration graph contracts; actual fresh PostgreSQL evidence remains separate."""

import importlib.util
import re
from pathlib import Path
from unittest.mock import patch

from ketrika.gold.refresh import GOLD_DEPENDENCIES, ORDERED_GOLD_VIEWS


def test_complete_quarantine_graph_is_installed_in_dependency_order() -> None:
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0021_gold_graph.py"
    spec = importlib.util.spec_from_file_location("gold_graph_migration_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with patch.object(module.op, "execute") as execute:
        module.upgrade()
    definition = execute.call_args_list[0].args[0]
    views = re.findall(r"CREATE MATERIALIZED VIEW gold\.(\w+) AS", definition)
    assert views == ORDERED_GOLD_VIEWS
    assert definition.count("WITH NO DATA;") == len(ORDERED_GOLD_VIEWS)
    for view, dependencies in GOLD_DEPENDENCIES.items():
        assert all(views.index(dependency) < views.index(view) for dependency in dependencies)
    assert "obs.quarantine_ledger" in definition
    assert "REFRESH MATERIALIZED VIEW" not in definition
    assert "UPDATE obs." not in definition
    assert "DELETE FROM" not in definition
