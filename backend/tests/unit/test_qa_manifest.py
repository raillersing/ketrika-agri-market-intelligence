"""Manifest and measured reports fail closed on missing, empty or skipped tests."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from ketrika.core.qa_manifest import Suite, main, read_junit, run_suite, select_suite
from ketrika.core.qualification import QualificationSafetyError


@pytest.fixture
def manifest(tmp_path):
    test = tmp_path / "tests/test_valid.py"
    test.parent.mkdir()
    test.write_text("# Parser fixture only, not a runnable acceptance suite\n")
    return {
        "version": 1,
        "tasks": {
            "R0.3": {
                "tests": ["tests/test_valid.py"],
                "minimum_tests": 1,
                "minimum_integration_tests": 0,
            }
        },
    }


def test_select_known_suite(manifest, tmp_path):
    suite = select_suite(manifest, "R0.3", tmp_path)
    assert suite == Suite(("tests/test_valid.py",), 1, 0)


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"version": True},
        {"version": 2},
        {"version": 1, "tasks": []},
        {"version": 1, "tasks": {"R0.3": []}},
    ],
)
def test_malformed_manifest_refused(document, tmp_path):
    with pytest.raises(QualificationSafetyError):
        select_suite(document, "R0.3", tmp_path)


def test_timeout_is_failed_receipt(tmp_path, monkeypatch):
    def timed_out(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr("ketrika.core.qa_manifest.subprocess.run", timed_out)
    receipt = run_suite(
        Suite(("tests/test_valid.py",), 1, 0), "R0.3", tmp_path, tmp_path / "reports"
    )
    assert not receipt["passed"]
    assert receipt["pytest_exit"] is None
    assert "reason" in receipt


@pytest.mark.parametrize("passed", [False, True])
def test_cli_returns_measured_outcome(tmp_path, monkeypatch, passed, capsys):
    document = tmp_path / "manifest.json"
    document.write_text("{}")
    monkeypatch.setattr("sys.argv", ["qa", "R0.3", "--manifest", str(document)])
    monkeypatch.setattr(
        "ketrika.core.qa_manifest.select_suite", lambda *args: Suite(("tests/test_valid.py",), 1, 0)
    )
    monkeypatch.setattr("ketrika.core.qa_manifest.run_suite", lambda *args: {"passed": passed})
    assert main() == (0 if passed else 1)
    assert json.loads(capsys.readouterr().out)["passed"] == passed


def test_preflight_never_executes_tests(tmp_path, monkeypatch, capsys):
    document = tmp_path / "manifest.json"
    document.write_text("{}")
    monkeypatch.setattr("sys.argv", ["qa", "R0.3", "--manifest", str(document), "--validate-only"])
    monkeypatch.setattr(
        "ketrika.core.qa_manifest.select_suite", lambda *args: Suite(("tests/test_valid.py",), 1, 0)
    )

    def forbidden(*args):
        raise AssertionError("Preflight must not run tests")

    monkeypatch.setattr("ketrika.core.qa_manifest.run_suite", forbidden)
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["tests_executed"] == 0


def test_cli_missing_manifest_fails(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["qa", "R0.3", "--manifest", str(tmp_path / "absent.json")])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


@pytest.mark.parametrize(
    "source",
    [
        "# deliberately empty suite\n",
        "import pytest\ndef test_required():\n    pytest.skip('deliberate negative fixture')\n",
        "def test_required():\n    assert False\n",
    ],
)
def test_real_empty_skipped_and_failed_suites_do_not_qualify(tmp_path, source):
    test = tmp_path / "tests/test_deliberate_negative.py"
    test.parent.mkdir()
    test.write_text(source)
    receipt = run_suite(
        Suite(("tests/test_deliberate_negative.py",), 1, 0), "R0.3", tmp_path, tmp_path / "reports"
    )
    assert not receipt["passed"]
    assert "reason" in receipt


@pytest.mark.parametrize("task", ["", "R0.99", "R6.11", "R9.1", "R0.3;cmd", "../R0.3"])
def test_unknown_or_unavailable_task_refused(manifest, tmp_path, task):
    with pytest.raises(QualificationSafetyError):
        select_suite(manifest, task, tmp_path)


@pytest.mark.parametrize(
    "tests",
    [
        [],
        ["/tests/test_valid.py"],
        ["tests/../test_valid.py"],
        ["--collect-only"],
        ["tests/missing.py"],
        ["tests/test_valid.py", "tests/test_valid.py"],
        [{}],
    ],
)
def test_empty_unsafe_or_missing_selection_refused(manifest, tmp_path, tests):
    manifest["tasks"]["R0.3"]["tests"] = tests
    with pytest.raises(QualificationSafetyError):
        select_suite(manifest, "R0.3", tmp_path)


@pytest.mark.parametrize(
    "minimum,integration", [(0, 0), (-1, 0), (True, 0), (1, 2), (1, -1), (1, True)]
)
def test_invalid_minima_refused(manifest, tmp_path, minimum, integration):
    manifest["tasks"]["R0.3"].update(minimum_tests=minimum, minimum_integration_tests=integration)
    with pytest.raises(QualificationSafetyError):
        select_suite(manifest, "R0.3", tmp_path)


def junit(path, outcome="", count=1, classname="tests.unit.test_fixture"):
    failure = int(outcome == "failure")
    error = int(outcome == "error")
    skipped = int(outcome == "skipped")
    child = f"<{outcome}/>" if outcome else ""
    path.write_text(
        f'<testsuites><testsuite tests="{count}" failures="{failure}" errors="{error}" skipped="{skipped}"><testcase classname="{classname}" name="fixture">{child}</testcase></testsuite></testsuites>'
    )


def test_junit_recounts_passed_cases(tmp_path):
    path = tmp_path / "report.xml"
    junit(path, classname="tests.integration.test_fixture")
    result = read_junit(path, Suite(("tests/test_valid.py",), 1, 1))
    assert result["tests"] == result["integration_by_layout"] == 1
    assert result["failures"] == result["errors"] == result["skipped"] == 0


@pytest.mark.parametrize("layout", ["tests.unit.test_fixture", "tests.integration.test_fixture"])
def test_junit_marked_integration_is_counted_once(tmp_path, layout):
    path = tmp_path / "report.xml"
    path.write_text(
        '<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0">'
        f'<testcase classname="{layout}" name="fixture"><properties>'
        '<property name="ketrika.integration" value="true"/>'
        "</properties></testcase></testsuite></testsuites>"
    )
    result = read_junit(path, Suite(("tests/test_valid.py",), 1, 1))
    assert result["integration_by_marker"] == result["integration_tests"] == 1
    assert result["integration_by_layout"] == int(".integration." in layout)


def test_real_marker_outside_integration_directory_is_reported(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "conftest.py").write_text((Path(__file__).parents[1] / "conftest.py").read_text())
    (tests / "test_marker.py").write_text(
        "import pytest\n@pytest.mark.integration\ndef test_required():\n    assert True\n"
    )
    receipt = run_suite(
        Suite(("tests/test_marker.py",), 1, 1), "R0.3", tmp_path, tmp_path / "reports"
    )
    assert receipt["passed"]
    assert receipt["counts"]["integration_by_layout"] == 0
    assert receipt["counts"]["integration_by_marker"] == 1
    assert receipt["counts"]["integration_tests"] == 1


@pytest.mark.parametrize("outcome", ["failure", "error", "skipped"])
def test_negative_junit_outcome_refused(tmp_path, outcome):
    path = tmp_path / "report.xml"
    junit(path, outcome=outcome)
    with pytest.raises(QualificationSafetyError):
        read_junit(path, Suite(("tests/test_valid.py",), 1, 0))


def test_empty_and_inconsistent_report_refused(tmp_path):
    path = tmp_path / "report.xml"
    path.write_text(
        '<testsuites><testsuite tests="0" failures="0" errors="0" skipped="0"/></testsuites>'
    )
    with pytest.raises(QualificationSafetyError):
        read_junit(path, Suite(("tests/test_valid.py",), 1, 0))
    junit(path, count=100)
    with pytest.raises(QualificationSafetyError):
        read_junit(path, Suite(("tests/test_valid.py",), 1, 0))
    junit(path)
    with pytest.raises(QualificationSafetyError):
        read_junit(path, Suite(("tests/test_valid.py",), 1, 1))


@pytest.mark.parametrize(
    "exit_code,write_report,skip",
    [(0, True, False), (1, True, False), (0, False, False), (0, True, True)],
)
def test_execution_receipt_requires_current_real_report(
    tmp_path, monkeypatch, exit_code, write_report, skip
):
    def fake_run(command, **kwargs):
        assert kwargs["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
        if write_report:
            report = Path(
                next(part.split("=", 1)[1] for part in command if part.startswith("--junitxml="))
            )
            junit(report, outcome="skipped" if skip else "")
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr("ketrika.core.qa_manifest.subprocess.run", fake_run)
    suite = Suite(("tests/test_valid.py",), 1, 0)
    receipt = run_suite(suite, "R0.3", tmp_path, tmp_path / "reports")
    assert receipt["passed"] == (exit_code == 0 and write_report and not skip)
    stored = json.loads(
        (tmp_path / "reports" / receipt["execution_id"] / "receipt.json").read_text()
    )
    assert stored == receipt
    second = run_suite(suite, "R0.3", tmp_path, tmp_path / "reports")
    assert second["execution_id"] != receipt["execution_id"]
