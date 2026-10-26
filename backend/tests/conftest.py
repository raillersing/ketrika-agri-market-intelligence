"""Integration suites require isolated targets; selected skips are not a green check."""

import json
import os
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from ketrika.core.http_budget import Admission, SqlBudgetBackend
from ketrika.core.qualification import QualificationSafetyError, validate_environment
from ketrika.core.qualification_reports import capture_binding


def _loopback_admission(admission: Admission, namespace: str) -> Admission:
    if admission.domain not in {"localhost", "127.0.0.1", "::1"}:
        return admission
    return replace(admission, domain=f"fixture-{namespace}-{admission.domain}")


@pytest.fixture(autouse=True)
def isolated_loopback_http_budget(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fixture domains are scenario-local; real SQL admission and history remain intact."""
    if not (
        request.node.get_closest_marker("integration") or "/integration/" in request.node.nodeid
    ):
        return
    validate_environment(os.environ)
    namespace = uuid4().hex
    reserve: Callable[[SqlBudgetBackend, Admission, datetime], float] = SqlBudgetBackend.reserve

    def isolated_reserve(self: SqlBudgetBackend, admission: Admission, now: datetime) -> float:
        return reserve(self, _loopback_admission(admission, namespace), now)

    monkeypatch.setattr(SqlBudgetBackend, "reserve", isolated_reserve)


@pytest.fixture(autouse=True)
def isolated_schema_declarations(monkeypatch):
    """Declarations must be explicit in each scenario, not inherited from an earlier test."""
    from ketrika.core.schema_contracts import SchemaContractRegistry

    monkeypatch.setattr(
        "ketrika.core.schema_contracts.DEFAULT_SCHEMA_CONTRACT_REGISTRY", SchemaContractRegistry()
    )


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if any(
        item.get_closest_marker("integration") or "/integration/" in item.nodeid for item in items
    ):
        try:
            validate_environment(os.environ)
        except QualificationSafetyError as exc:
            raise pytest.UsageError(f"Integration suite refused before execution: {exc}") from exc
    for item in items:
        if item.get_closest_marker("integration") is not None:
            item.user_properties.append(("ketrika.integration", "true"))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if os.environ.get("KETRIKA_QUALIFICATION") != "1":
        return
    reporter = session.config.pluginmanager.getplugin("terminalreporter")
    if exitstatus == 0 and reporter is not None and reporter.stats.get("skipped"):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_collection_finish(session: pytest.Session) -> None:
    target = os.environ.get("KETRIKA_QA_INVENTORY")
    if not target or os.environ.get("KETRIKA_QA_INVENTORY_OWNER_PID") != str(os.getppid()):
        return
    from _pytest.junitxml import mangle_test_address

    validate_environment(os.environ)
    inventory = capture_binding(
        Path(os.environ["KETRIKA_REPO_ROOT"]), os.environ["KETRIKA_SOURCE_COMMIT"]
    )
    cases = []
    for item in session.items:
        names = mangle_test_address(item.nodeid)
        cases.append({"classname": ".".join(names[:-1]), "name": names[-1]})
    inventory["cases"] = cases
    path = Path(target).resolve()
    if not path.is_relative_to(Path("/app/.venv")):
        raise pytest.UsageError("Inventory destination is not the dedicated report volume")
    path.write_text(json.dumps(inventory, indent=2) + "\n")


@pytest.fixture
def authenticated_unit_reader():
    """Explicit opt-in for business unit cases; security tests use real authentication."""
    from ketrika.api.auth import get_current_user
    from ketrika.api.main import app
    from ketrika.core.models.db import UserAccount

    def reader() -> UserAccount:
        return UserAccount(
            user_id=uuid4(), email="unit-reader@ketrika.local", role="client", disabled=False
        )

    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = reader
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = previous
