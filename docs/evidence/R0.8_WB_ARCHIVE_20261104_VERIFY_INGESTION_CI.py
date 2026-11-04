"""Read-only validation of exported local originals; run inside Docker only."""

import hashlib
import json
import re
import sys
from pathlib import Path

from ketrika.core.qualification import validate_coverage
from ketrika.core.qualification_reports import (
    E2E_SCENARIOS,
    ENVIRONMENT_IDENTITY,
    frontend_counts,
    junit_counts,
    source_fingerprint,
)

root, source, expected_commit = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]


def read(path):
    return json.loads(path.read_text())


for role in ("backend", "frontend", "browser"):
    directory = root / role
    manifest = read(directory / "manifest.json")
    assert manifest["role"] == role
    for relative, entry in manifest["files"].items():
        path = directory / relative
        data = path.read_bytes()
        assert len(data) == entry["bytes"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]

inventory = read(root / "backend/qa-inventory.json")
frontend_root = root / "frontend"
frontend_id = read(frontend_root / "latest.json")["execution_id"]
frontend = read(frontend_root / frontend_id / "receipt.json")
browser_paths = [
    path
    for path in (root / "browser").glob("*/receipt.json")
    if read(path).get("commit") == expected_commit
]
assert len(browser_paths) == 1
browser = read(browser_paths[0])
fingerprint = source_fingerprint(source)
for receipt in (inventory, frontend, browser):
    assert receipt["commit"] == expected_commit
    assert receipt["source_fingerprint"] == fingerprint
    assert receipt["environment"] == inventory["environment"]
    assert receipt["dataset"] in ("test", "mixed")
for key, value in ENVIRONMENT_IDENTITY.items():
    assert inventory["environment"][key] == value
for role in ("backend", "web", "browser"):
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", inventory["environment"][role + "_image_id"])
backend_counts = junit_counts(root / "backend/qa-tests.xml", 340, 32, inventory["cases"])
assert backend_counts["tests"] == 2796
assert backend_counts["integration_tests"] == 301
coverage = validate_coverage(read(root / "backend/qa-coverage.json"))
front_counts = frontend_counts(frontend, read(frontend_root / frontend_id / "vitest.json"))
assert front_counts["tests"] == 113
login_suites = [
    suite
    for suite in read(frontend_root / frontend_id / "vitest.json")["testResults"]
    if suite["name"].endswith("/login-target.test.ts")
]
assert len(login_suites) == 1
assert len(login_suites[0]["assertionResults"]) == 23
territorial_suites = [
    suite
    for suite in read(frontend_root / frontend_id / "vitest.json")["testResults"]
    if suite["name"].endswith("/territorial-prices.test.ts")
]
assert len(territorial_suites) == 1
assert len(territorial_suites[0]["assertionResults"]) == 8
r03 = read(source / "scripts/qa-manifest.json")["tasks"]["R0.3"]
r03_counts = {}
for path in r03["tests"]:
    module = path.removesuffix(".py").replace("/", ".")
    r03_counts[module] = sum(
        case["classname"] == module or case["classname"].startswith(module + ".")
        for case in inventory["cases"]
    )
assert all(r03_counts.values())
assert sum(r03_counts.values()) >= r03["minimum_tests"]
assert (
    sum(count for module, count in r03_counts.items() if module.startswith("tests.integration."))
    >= r03["minimum_integration_tests"]
)
critical = {
    "tests.unit.test_provenance_wb_archive": 27,
    "tests.unit.test_rtfp_archive": 13,
    "tests.integration.test_native_wb_archive": 2,
    "tests.unit.test_wb_archive": 23,
    "tests.unit.test_corpus_wb_archive": 11,
    "tests.unit.test_product_filter_confidence": 12,
    "tests.integration.test_ambiguous_rice_alias_migration": 6,
    "tests.unit.test_api_climate": 8,
    "tests.integration.test_unverified_economic_inputs": 9,
    "tests.integration.test_application_no_truncate": 11,
    "tests.integration.test_trade_alias_aggregation": 6,
    "tests.integration.test_reconcile_products_admission": 27,
    "tests.unit.test_unverified_pricing_publication": 5,
    "tests.unit.test_parity_pricing": 5,
    "tests.integration.test_copilot_gold_only_migration": 3,
    "tests.unit.test_browser_rate_budget": 10,
    "tests.unit.test_qualification": 74,
    "tests.integration.test_quarantine_integration": 7,
    "tests.integration.test_supersession_cycles": 14,
    "tests.integration.test_quarantine_normalization": 6,
    "tests.integration.test_quarantine_typed_admission": 42,
    "tests.unit.test_quarantine_execution_guards": 30,
    "tests.unit.test_quarantine_reception_audit": 23,
    "tests.unit.test_quarantine_bronze_copy": 9,
    "tests.unit.test_gold_graph_migration": 1,
    "tests.unit.test_weather_migration": 3,
    "tests.unit.test_gold_compatibility": 5,
}
for classname, minimum in critical.items():
    assert sum(case["classname"] == classname for case in inventory["cases"]) == minimum
assert any(
    case["classname"] == "tests.integration.test_api_v1"
    and case["name"] == "test_api_auth_roles_and_status_codes"
    for case in inventory["cases"]
)
assert browser["passed"] is True
assert browser["login_return_target"] == "/prices"
assert browser["territorial_scope_verified"] is True
assert browser["completed_checks"] == list(E2E_SCENARIOS)
assert browser["expected_checks"] == list(E2E_SCENARIOS)
assert browser["checks"] == len(E2E_SCENARIOS) == 26
assert browser["browser_errors"] == []
assert browser["prices_status"] == 200 and browser["unauthenticated_status"] in (401, 403)
assert browser["owned_reading_fixtures_cleaned"] is True
assert re.fullmatch(r"[0-9a-f]{64}", browser["trace"]["sha256"])
recoveries = browser.get("session_readiness_recoveries", [])
budget_waits = browser.get("rate_budget_waits", [])
assert len(budget_waits) <= 40
for wait in budget_waits:
    assert wait["seconds"] == 60 and 0 <= wait["remaining"] < 20
    assert wait["stage"].startswith(
        ("/prices", "/map", "/trade", "/alerts", "/bulletins", "/economy")
    )
assert len(recoveries) <= 1
for recovery in recoveries:
    assert recovery == {
        "scenario": "first bulletin navigation",
        "initial_status": 503,
        "reloads": 1,
    }
print(
    json.dumps(
        {
            "commit": expected_commit,
            "source_fingerprint": fingerprint,
            "backend": backend_counts,
            "coverage": coverage,
            "frontend": front_counts,
            "browser_checks": browser["checks"],
            "browser_duration_seconds": browser["duration_seconds"],
            "session_readiness_recoveries": recoveries,
            "rate_budget_waits": budget_waits,
            "trace_sha256_only": browser["trace"]["sha256"],
            "critical_case_inclusion": critical,
            "r03_case_inclusion": r03_counts,
            "limits": "Software qualification only; raw session traces excluded from exported artefact",
        },
        indent=2,
    )
)
