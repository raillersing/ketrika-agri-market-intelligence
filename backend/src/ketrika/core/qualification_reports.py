"""Shared bounded readers; reports are data, never commands or live proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ketrika.core.qualification import QualificationSafetyError

MAX_REPORT_BYTES = 16 * 1024 * 1024
MAX_CASES = 100000

ENVIRONMENT_IDENTITY = {
    "project": "ketrika-qualification-main-final",
    "database": "ketrika_qualification",
    "bronze_bucket": "ketrika-qa-bronze",
    "network": "ketrika_qualification_main_final_network",
    "dataset_mode": "test",
}


E2E_SCENARIOS = (
    "protected UI redirects without a session",
    "UI rejects and clears an arbitrary session cookie",
    "form login establishes HttpOnly session",
    "reload retains authentication",
    "protected profile authenticates the browser session",
    "authenticated same-origin prices API",
    "price explorer renders",
    "economy explicitly reports unqualified data after reload",
    "mobile navigation opens, closes with Escape and with its link",
    "economy uses full content width at 390px without clipped message",
    "UI logout removes session",
    "API rejects access after logout",
    "API rejects reuse of the logged-out token",
    "UI rejects and clears a restored revoked cookie",
    "UI remains protected after logout",
)


def native_environment() -> dict[str, str]:
    result = dict(ENVIRONMENT_IDENTITY)
    for role in ("BACKEND", "WEB", "BROWSER"):
        value = os.environ.get("KETRIKA_PROOF_" + role + "_IMAGE_ID", "")
        if re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
            raise QualificationSafetyError("evidence_runtime_identity_missing")
        result[role.lower() + "_image_id"] = value
    return result


def capture_binding(root: Path, commit: str, dataset: str = "mixed") -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise QualificationSafetyError("evidence_commit_missing")
    return {
        "version": 1,
        "commit": commit,
        "source_fingerprint": source_fingerprint(root),
        "environment": native_environment(),
        "dataset": dataset,
        "captured_at": datetime.now(UTC).isoformat(),
    }


def source_fingerprint(root: Path) -> str:
    """Stable tracked-input content identity, excluding mutable reports and caches."""
    digest = hashlib.sha256()
    excluded = {
        ".git",
        ".venv",
        "node_modules",
        ".next",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
    paths: list[Path] = []
    generated_directories = {"backend/.hypothesis", "web/test-results"}
    for name in ("backend", "web", "scripts", "registry", "taxonomy", "geo", "docker"):
        base = root / name
        if not base.is_dir():
            continue
        for directory, subdirs, files in os.walk(base, followlinks=False):
            subdirs[:] = sorted(
                item
                for item in subdirs
                if item not in excluded
                and (Path(directory) / item).relative_to(root).as_posix()
                not in generated_directories
            )
            for filename in sorted(files):
                if filename.startswith(".env") or filename.endswith((".pyc", ".tsbuildinfo")):
                    continue
                if Path(directory) == root / "backend" and (
                    filename == ".coverage" or filename.startswith(".coverage.")
                ):
                    continue
                path = Path(directory) / filename
                if path.is_symlink():
                    raise QualificationSafetyError("source_symlink_forbidden")
                paths.append(path)
    for name in (
        "docker-compose.qualification.yml",
        "docker-compose.rebuild-qualification.yml",
        "docker-compose.price-preview.yml",
        ".gitattributes",
    ):
        if (root / name).is_symlink():
            raise QualificationSafetyError("source_symlink_forbidden")
        if (root / name).is_file():
            paths.append(root / name)
    if not paths:
        raise QualificationSafetyError("source_snapshot_empty")
    for path in sorted(paths):
        encoded_path = path.relative_to(root).as_posix().encode()
        digest.update(len(encoded_path).to_bytes(4, "big"))
        digest.update(encoded_path)
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def read_report(path: Path) -> bytes:
    if not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise QualificationSafetyError("evidence_missing_or_oversized")
    return path.read_bytes()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise QualificationSafetyError("evidence_duplicate_key")
        result[key] = value
    return result


def load_json_report(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_report(path), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise QualificationSafetyError("evidence_invalid_json") from None
    if not isinstance(value, dict):
        raise QualificationSafetyError("evidence_not_object")
    return value


def evidence_path(root: Path, reference: Mapping[str, Any]) -> Path:
    relative = reference.get("path")
    digest = reference.get("sha256")
    if (
        not isinstance(relative, str)
        or not relative
        or "\\" in relative
        or Path(relative).is_absolute()
        or any(part in ("..", ".") for part in relative.split("/"))
        or not isinstance(digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
    ):
        raise QualificationSafetyError("evidence_invalid_reference")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise QualificationSafetyError("evidence_outside_bundle")
    if hashlib.sha256(read_report(target)).hexdigest() != digest:
        raise QualificationSafetyError("evidence_hash_mismatch")
    return target


def junit_counts(
    path: Path,
    minimum_tests: int = 1,
    minimum_integrations: int = 0,
    inventory: Sequence[Mapping[str, str]] | None = None,
) -> dict[str, int]:
    content = read_report(path)
    if b"<!DOCTYPE" in content or b"<!ENTITY" in content:
        raise QualificationSafetyError("evidence_unsafe_xml")
    try:
        tree = ET.fromstring(content)
        cases = list(tree.iter("testcase"))
        leaves = [node for node in tree.iter("testsuite") if not node.findall("testsuite")]
        if (
            not leaves
            or len(cases) > MAX_CASES
            or sum(int(node.attrib["tests"]) for node in leaves) != len(cases)
        ):
            raise QualificationSafetyError("junit_inconsistent_summary")
        marked = [
            any(
                prop.get("name") == "ketrika.integration" and prop.get("value") == "true"
                for prop in node.findall("./properties/property")
            )
            for node in cases
        ]
        layout = [".integration." in node.get("classname", "") for node in cases]
        counts = {
            "tests": len(cases),
            "failures": sum(node.find("failure") is not None for node in cases),
            "errors": sum(node.find("error") is not None for node in cases),
            "skipped": sum(node.find("skipped") is not None for node in cases),
            "integration_by_layout": sum(layout),
            "integration_by_marker": sum(marked),
            "integration_tests": sum(a or b for a, b in zip(layout, marked, strict=True)),
        }
        if any(
            sum(int(node.attrib[key]) for node in leaves) != counts[key]
            for key in ("failures", "errors", "skipped")
        ):
            raise QualificationSafetyError("junit_inconsistent_outcomes")
    except (ET.ParseError, KeyError, ValueError) as error:
        if isinstance(error, QualificationSafetyError):
            raise
        raise QualificationSafetyError("junit_invalid") from None
    if any(counts[key] for key in ("failures", "errors", "skipped")):
        raise QualificationSafetyError("junit_red_or_skipped")
    if counts["tests"] < minimum_tests or counts["integration_tests"] < minimum_integrations:
        raise QualificationSafetyError("junit_below_minimum")
    if inventory is not None:
        if not inventory or len(inventory) > MAX_CASES:
            raise QualificationSafetyError("junit_inventory_empty")
        actual = Counter((node.get("classname", ""), node.get("name", "")) for node in cases)
        try:
            expected = Counter((item["classname"], item["name"]) for item in inventory)
        except (KeyError, TypeError):
            raise QualificationSafetyError("junit_inventory_invalid") from None
        if actual != expected:
            raise QualificationSafetyError("junit_inventory_incomplete")
    return counts


def frontend_counts(receipt: Mapping[str, Any], report: Mapping[str, Any]) -> dict[str, int]:
    steps = receipt.get("steps")
    if (
        receipt.get("passed") is not True
        or not isinstance(steps, list)
        or len(steps) != 4
        or any(
            not isinstance(step, dict)
            or step.get("exit_code") != 0
            or step.get("successful") is not True
            or step.get("timed_out") is not False
            or step.get("signal") is not None
            or step.get("error_code") is not None
            for step in steps
        )
    ):
        raise QualificationSafetyError("frontend_steps_failed_or_missing")
    expected_commands = [
        ("pnpm", "lint"),
        ("pnpm", "typecheck"),
        ("pnpm", "run", "test"),
        ("pnpm", "build"),
    ]
    for step, prefix in zip(steps, expected_commands, strict=True):
        command = step.get("command")
        if not isinstance(command, list) or tuple(command[: len(prefix)]) != prefix:
            raise QualificationSafetyError("frontend_step_wrong_command")
    suites = report.get("testResults")
    if not isinstance(suites, list) or not suites:
        raise QualificationSafetyError("frontend_suite_missing")
    cases = [case for suite in suites for case in suite.get("assertionResults", [])]
    if (
        report.get("success") is not True
        or not cases
        or len(cases) > MAX_CASES
        or report.get("numTotalTests") != len(cases)
        or report.get("numPassedTests") != len(cases)
        or any(
            report.get(key) != 0
            for key in (
                "numFailedTests",
                "numPendingTests",
                "numFailedTestSuites",
                "numPendingTestSuites",
            )
        )
        or any(case.get("status") != "passed" for case in cases)
    ):
        raise QualificationSafetyError("frontend_red_or_incomplete")
    counts = {"tests": len(cases), "suites": len(suites)}
    if receipt.get("counts") != counts:
        raise QualificationSafetyError("frontend_receipt_counts_mismatch")
    return counts


def e2e_counts(receipt: Mapping[str, Any], root: Path) -> dict[str, int]:
    if (
        receipt.get("passed") is not True
        or receipt.get("browser_errors") != []
        or receipt.get("expected_checks") != list(E2E_SCENARIOS)
        or receipt.get("completed_checks") != list(E2E_SCENARIOS)
        or receipt.get("checks") != len(E2E_SCENARIOS)
        or receipt.get("unauthenticated_status") not in (401, 403)
        or not isinstance(receipt.get("trace"), dict)
    ):
        raise QualificationSafetyError("e2e_failed_or_incomplete")
    evidence_path(root, receipt["trace"])
    return {"checks": len(receipt["completed_checks"])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fingerprint = sub.add_parser("fingerprint")
    fingerprint.add_argument("root", type=Path)
    junit = sub.add_parser("check-junit")
    junit.add_argument("report", type=Path)
    junit.add_argument("inventory", type=Path)
    junit.add_argument("--root", type=Path, default=Path("/workspace"))
    junit.add_argument("--commit", required=True)
    junit.add_argument("--minimum-tests", type=int, default=1)
    junit.add_argument("--minimum-integrations", type=int, default=0)
    frontend = sub.add_parser("check-frontend")
    frontend.add_argument("results", type=Path)
    frontend.add_argument("--root", type=Path, default=Path("/workspace"))
    frontend.add_argument("--commit", required=True)
    args = parser.parse_args()
    try:
        if args.command == "fingerprint":
            sys.stdout.write(source_fingerprint(args.root) + "\n")
            return 0
        from ketrika.core.qualify import verify_binding

        if args.command == "check-junit":
            inventory = load_json_report(args.inventory)
            verify_binding(
                inventory,
                args.commit,
                source_fingerprint(args.root),
                native_environment(),
                datetime.now(UTC),
            )
            counts = junit_counts(
                args.report, args.minimum_tests, args.minimum_integrations, inventory["cases"]
            )
        else:
            pointer = load_json_report(args.results / "latest.json")
            execution_id = pointer.get("execution_id", "")
            if (
                not isinstance(execution_id, str)
                or re.fullmatch(r"[0-9a-f-]{36}", execution_id) is None
            ):
                raise QualificationSafetyError("frontend_execution_unknown")
            directory = args.results / execution_id
            receipt = load_json_report(directory / "receipt.json")
            verify_binding(
                receipt,
                args.commit,
                source_fingerprint(args.root),
                native_environment(),
                datetime.now(UTC),
            )
            counts = frontend_counts(receipt, load_json_report(directory / "vitest.json"))
        sys.stdout.write(json.dumps(counts) + "\n")
        return 0
    except (OSError, KeyError, TypeError, ValueError) as error:
        reason = str(error) if isinstance(error, QualificationSafetyError) else "evidence_invalid"
        sys.stderr.write(reason + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
