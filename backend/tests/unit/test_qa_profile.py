"""Readonly profiler rejects invalid input and never certifies green outcomes."""

from pathlib import Path

import pytest

from ketrika.core import qa_profile


def report(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "report.xml"
    path.write_text(content)
    return path


def test_timings_group_parameters_and_preserve_failure_counts(tmp_path: Path) -> None:
    path = report(
        tmp_path,
        '<testsuite><testcase classname="tests.unit.test_x" name="test_a[secret]" time="0.1"/><testcase classname="tests.unit.test_x" name="test_a[other]" time="0.2"><failure/></testcase><testcase classname="tests.unit.test_x" name="test_b" time="0.05"><skipped/></testcase></testsuite>',
    )
    result = qa_profile.profile_junit(path)
    assert result["summed_testcase_seconds"] == "0.35"
    assert result["counts"] == {"tests": 3, "failures": 1, "errors": 0, "skipped": 1}
    assert result["slowest_groups"][0]["seconds"] == "0.3"
    assert result["slowest_groups"][0]["cases"] == 2
    assert "secret" not in str(result) and "passed" not in result


@pytest.mark.parametrize("duration", ["NaN", "Infinity", "-1", "oops", "1000000001"])
def test_invalid_duration(tmp_path: Path, duration: str) -> None:
    with pytest.raises(ValueError, match="invalid_duration"):
        qa_profile.profile_junit(
            report(
                tmp_path,
                f'<testsuite><testcase classname="x" name="y" time="{duration}"/></testsuite>',
            )
        )


@pytest.mark.parametrize(
    "content",
    [
        "<testsuite/>",
        "<other/>",
        '<testsuite><testcase classname="x" name="y"/></testsuite>',
        '<testsuite><testcase classname="bad name" name="y" time="1"/></testsuite>',
        "<!DOCTYPE testsuite><testsuite/>",
    ],
)
def test_invalid_report(tmp_path: Path, content: str) -> None:
    with pytest.raises(ValueError):
        qa_profile.profile_junit(report(tmp_path, content))


@pytest.mark.parametrize("limit", [0, 101, True])
def test_invalid_limit(tmp_path: Path, limit: int) -> None:
    with pytest.raises(ValueError, match="invalid_limit"):
        qa_profile.profile_junit(report(tmp_path, "<testsuite/>"), limit)


def test_size_and_count_bounds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = report(tmp_path, '<testsuite><testcase classname="x" name="y" time="1"/></testsuite>')
    monkeypatch.setattr(qa_profile, "MAX_BYTES", 4)
    with pytest.raises(ValueError, match="too_large"):
        qa_profile.profile_junit(path)
    monkeypatch.setattr(qa_profile, "MAX_BYTES", 1024)
    monkeypatch.setattr(qa_profile, "MAX_CASES", 0)
    with pytest.raises(ValueError, match="too_many_cases"):
        qa_profile.profile_junit(path)


@pytest.mark.parametrize(
    "argument", ["/etc/passwd", "../outside.xml", "docs/missing.xml", "docs/file.json"]
)
def test_cli_fails_closed(argument: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["qa-profile", argument])
    with pytest.raises(SystemExit) as error:
        qa_profile.main()
    assert error.value.code == 1
