"""Integration suites require isolated targets; selected skips are not a green check."""

import os

import pytest

from ketrika.core.qualification import QualificationSafetyError, validate_environment


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if any(
        item.get_closest_marker("integration") or "/integration/" in item.nodeid for item in items
    ):
        try:
            validate_environment(os.environ)
        except QualificationSafetyError as exc:
            raise pytest.UsageError(f"Integration suite refused before execution: {exc}") from exc


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if os.environ.get("KETRIKA_QUALIFICATION") != "1":
        return
    reporter = session.config.pluginmanager.getplugin("terminalreporter")
    if exitstatus == 0 and reporter is not None and reporter.stats.get("skipped"):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
