"""Deliberate defects exist only in disposable copies, never in application source."""

import os
import subprocess

import pytest

from ketrika.core.qualification import validate_environment


@pytest.mark.parametrize(
    "command,source",
    [
        (["ruff", "check"], "import os\n"),
        (["mypy", "--no-incremental"], 'value: int = "invalid fixture"\n'),
        (
            ["pytest", "-p", "no:cacheprovider"],
            "import os\nfrom sqlalchemy import create_engine, text\n"
            "def test_deliberate_bad_integration_fixture():\n"
            '    engine = create_engine(os.environ["DATABASE_URL"])\n'
            "    with engine.connect() as connection:\n"
            '        connection.execute(text("SELECT * FROM nonexistent_qa_failure_fixture"))\n',
        ),
    ],
    ids=["lint", "types", "integration-fixture"],
)
def test_real_quality_tools_refuse_defects_only_in_copy(tmp_path, command, source):
    validate_environment(os.environ)
    path = tmp_path / "test_negative_fixture.py"
    path.write_text(source)
    result = subprocess.run(
        [*command, str(path)],
        cwd=tmp_path,
        env=dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout or result.stderr
