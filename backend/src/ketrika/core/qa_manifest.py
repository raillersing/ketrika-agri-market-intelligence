"""Measured software QA subsets; absent, empty or skipped suites never qualify."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ketrika.core.qualification import QualificationSafetyError, validate_environment
from ketrika.core.qualification_reports import junit_counts


@dataclass(frozen=True)
class Suite:
    tests: tuple[str, ...]
    minimum_tests: int
    minimum_integration_tests: int


def select_suite(document: Mapping[str, Any], task_id: str, root: Path) -> Suite:
    """Treat manifest values as bounded data, never shell commands."""
    if (
        not isinstance(document, Mapping)
        or type(document.get("version")) is not int
        or document.get("version") != 1
        or not re.fullmatch(r"R[0-6]\.[1-9][0-9]*", task_id)
    ):
        raise QualificationSafetyError("Unknown manifest version or task ID")
    tasks = document.get("tasks")
    if not isinstance(tasks, dict) or task_id not in tasks:
        raise QualificationSafetyError("Task suite is absent or not yet implemented")
    entry = tasks[task_id]
    if not isinstance(entry, dict):
        raise QualificationSafetyError("Malformed task suite")
    tests = entry.get("tests")
    if not isinstance(tests, list) or not tests or any(not isinstance(item, str) for item in tests):
        raise QualificationSafetyError("Nonempty string test paths are mandatory")
    if len(tests) != len(set(tests)):
        raise QualificationSafetyError("Nonempty unique test paths are mandatory")
    for item in tests:
        if not isinstance(item, str) or not re.fullmatch(r"tests/[A-Za-z0-9_/]+\.py", item):
            raise QualificationSafetyError("Only relative test files are accepted")
        target = (root / item).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            raise QualificationSafetyError("Test path is missing or outside the snapshot")
    minimum = entry.get("minimum_tests")
    integration = entry.get("minimum_integration_tests")
    if type(minimum) is not int or minimum < 1:
        raise QualificationSafetyError("Positive test minimum is mandatory")
    if type(integration) is not int or not 0 <= integration <= minimum:
        raise QualificationSafetyError("Invalid integration minimum")
    return Suite(tuple(tests), minimum, integration)


def read_junit(path: Path, suite: Suite) -> dict[str, int]:
    """Use the same outcome verifier as measured qualification."""
    return junit_counts(path, suite.minimum_tests, suite.minimum_integration_tests)


def run_suite(suite: Suite, task_id: str, root: Path, reports: Path) -> dict[str, Any]:
    """Create a fresh execution directory before launching the declared suite."""
    validate_environment(os.environ)
    execution_id = uuid.uuid4().hex
    target = reports / execution_id
    target.mkdir(parents=True, exist_ok=False)
    junit = target / "tests.xml"
    command = [
        "pytest",
        "-p",
        "pytest_asyncio.plugin",
        "-p",
        "pytest_cov.plugin",
        "-p",
        "_hypothesis_pytestplugin",
        "-p",
        "pytest_httpserver.pytest_plugin",
        "-m",
        "not network",
        *suite.tests,
        f"--junitxml={junit}",
    ]
    environment = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    started = time.monotonic()
    receipt: dict[str, Any] = {
        "task": task_id,
        "execution_id": execution_id,
        "scope": "software subset only; not task DONE or market certification",
        "pytest_exit": None,
        "command": command,
        "passed": False,
    }
    try:
        result = subprocess.run(command, cwd=root, env=environment, check=False, timeout=3600)
        receipt["pytest_exit"] = result.returncode
        if result.returncode != 0:
            raise QualificationSafetyError("Test process returned nonzero")
        receipt["counts"] = read_junit(junit, suite)
        receipt["passed"] = True
    except (OSError, ValueError, KeyError, ET.ParseError, subprocess.TimeoutExpired) as exc:
        receipt["reason"] = str(exc)
    receipt["duration_seconds"] = round(time.monotonic() - started, 3)
    (target / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument(
        "--manifest", type=Path, default=Path("/workspace/scripts/qa-manifest.json")
    )
    args = parser.parse_args()
    try:
        document = json.loads(args.manifest.read_text())
        root = Path("/workspace/backend") if args.validate_only else Path("/app")
        suite = select_suite(document, args.task_id, root)
        if args.validate_only:
            sys.stdout.write(
                json.dumps({"task": args.task_id, "selection_valid": True, "tests_executed": 0})
                + "\n"
            )
            return 0
        receipt = run_suite(suite, args.task_id, Path("/app"), Path("/app/.venv/qa-results"))
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"QA refused: {exc}\n")
    sys.stdout.write(json.dumps(receipt) + "\n")
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
