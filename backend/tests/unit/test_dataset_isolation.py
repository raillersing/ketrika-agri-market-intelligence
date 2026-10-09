"""Synthetic datasets cannot enter real, demo or misbound sessions."""

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy.engine import make_url

from ketrika import demo
from ketrika.core.qualification import QualificationSafetyError
from tests.e2e_data.synthetic_gold_dataset import seed_synthetic_gold_data


@pytest.mark.parametrize("mode", ["real", "demo", "", "test"])
def test_seed_refused_before_sql_on_protected_session(monkeypatch, mode):
    monkeypatch.setenv("KETRIKA_DATASET_MODE", mode)
    session = MagicMock()
    session.get_bind.return_value.engine.url = make_url(
        "postgresql+psycopg://ketrika:public-fixture@db:5432/ketrika"
    )
    with pytest.raises(QualificationSafetyError):
        seed_synthetic_gold_data(session)
    session.get.assert_not_called()
    session.execute.assert_not_called()
    session.add.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()


def test_retired_demo_never_claims_success(capsys):
    assert demo.main() == 1
    result = capsys.readouterr()
    assert result.out == ""
    assert "pending R0.7" in result.err


def test_application_has_no_test_imports():
    for path in Path("src/ketrika").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("tests"), path
            elif isinstance(node, ast.Import):
                assert all(not item.name.startswith("tests") for item in node.names), path
