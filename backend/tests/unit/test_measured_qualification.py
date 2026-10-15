"""Simulated receipts are software fixtures, never an authentic market proof."""

import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ketrika.core import qualification_metrics as metrics
from ketrika.core.qualification import QualificationSafetyError
from ketrika.core.qualification_reports import (
    E2E_SCENARIOS,
    ENVIRONMENT_IDENTITY,
    capture_binding,
    e2e_counts,
    evidence_path,
    frontend_counts,
    junit_counts,
    load_json_report,
    native_environment,
    source_fingerprint,
)
from ketrika.core.qualify import CRITERIA, markdown, qualify, verify_binding
from ketrika.core.registry import REQUIRED_SOURCES

NOW = datetime(2026, 10, 14, 9, tzinfo=UTC)
COMMIT = "a" * 40


def emit(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def workspace(tmp_path):
    (tmp_path / "backend/src").mkdir(parents=True)
    (tmp_path / "backend/src/module.py").write_text("value = 1\n")
    (tmp_path / "registry").mkdir()
    (tmp_path / "registry/sources.yaml").write_text("[]\n")
    (tmp_path / "evidence").mkdir()
    return tmp_path


def test_source_fingerprint_ignores_unreadable_generated_test_outputs(tmp_path):
    root = workspace(tmp_path)
    expected = source_fingerprint(root)
    paths = [
        "backend/.hypothesis/constants/cached",
        "backend/.coverage",
        "backend/.coverage.worker",
        "web/test-results/.last-run.json",
    ]
    for name in paths:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated fixture output")
        path.chmod(0)
    try:
        assert source_fingerprint(root) == expected
    finally:
        for name in paths:
            (root / name).chmod(0o600)


@pytest.mark.parametrize(
    "name",
    [
        "backend/src/.hypothesis/model.py",
        "backend/.coverage_module.py",
        "web/src/test-results/model.ts",
    ],
)
def test_generated_names_in_real_source_remain_fingerprinted(tmp_path, name):
    root = workspace(tmp_path)
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("value = 1\n")
    previous = source_fingerprint(root)
    path.write_text("value = 2\n")
    assert source_fingerprint(root) != previous


def test_source_symlink_is_still_refused(tmp_path):
    root = workspace(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("value = 1\n")
    (root / "backend/src/link.py").symlink_to(outside)
    with pytest.raises(QualificationSafetyError, match="source_symlink_forbidden"):
        source_fingerprint(root)


def binding(root, dataset="synthetic"):
    return {
        "version": 1,
        "commit": COMMIT,
        "source_fingerprint": source_fingerprint(root),
        "environment": ENVIRONMENT_IDENTITY,
        "dataset": dataset,
        "captured_at": NOW.isoformat(),
    }


def junit(path, outcome="", summary=None):
    count = 'failures="0" errors="0" skipped="0"' if summary is None else summary
    path.write_text(
        f'<testsuites><testsuite tests="1" {count}>'
        '<testcase classname="tests.integration.example" name="test_case">'
        '<properties><property name="ketrika.integration" value="true"/></properties>'
        f"{outcome}</testcase></testsuite></testsuites>"
    )


def frontend():
    report = {
        "success": True,
        "numTotalTests": 1,
        "numPassedTests": 1,
        "numFailedTests": 0,
        "numPendingTests": 0,
        "numFailedTestSuites": 0,
        "numPendingTestSuites": 0,
        "testResults": [{"assertionResults": [{"status": "passed"}]}],
    }
    steps = [
        {
            "command": command,
            "exit_code": 0,
            "successful": True,
            "timed_out": False,
            "signal": None,
            "error_code": None,
        }
        for command in (
            ["pnpm", "lint"],
            ["pnpm", "typecheck"],
            ["pnpm", "run", "test"],
            ["pnpm", "build"],
        )
    ]
    return {"passed": True, "steps": steps, "counts": {"tests": 1, "suites": 1}}, report


def test_absent_bundle_produces_complete_unknown_report_without_seeding(tmp_path, monkeypatch):
    root = workspace(tmp_path)
    monkeypatch.setattr("ketrika.core.db.get_engine", lambda: pytest.fail("SQL forbidden"))
    result = qualify(root, root / "evidence", COMMIT, "all", now=NOW)
    assert not result["passed"] and result["exit_code"] == 1
    assert len(result["criteria"]) == len(CRITERIA)
    assert all(
        item["state"] == "unknown" and item["numerator"] is None for item in result["criteria"]
    )
    assert "PARTIAL" in markdown(result) and not result["program_R6_complete"]


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"commit": "b" * 40}, "commit_stale"),
        ({"source_fingerprint": "b" * 64}, "source_changed"),
        ({"environment": {"project": "production"}}, "environment_changed"),
        ({"captured_at": (NOW - timedelta(days=2)).isoformat()}, "date_stale"),
        ({"captured_at": (NOW + timedelta(seconds=1)).isoformat()}, "date_stale"),
        ({"captured_at": "2026-10-14T09:00:00"}, "not_utc"),
        ({"version": True}, "version_unknown"),
        ({"dataset": "approved"}, "dataset_unknown"),
    ],
)
def test_binding_rejects_old_changed_or_unknown_proof(tmp_path, change, reason):
    root = workspace(tmp_path)
    document = binding(root)
    document.update(change)
    with pytest.raises(QualificationSafetyError, match=reason):
        verify_binding(document, COMMIT, source_fingerprint(root), ENVIRONMENT_IDENTITY, NOW)


def test_binding_accepts_exact_scope_only(tmp_path):
    root = workspace(tmp_path)
    verify_binding(binding(root), COMMIT, source_fingerprint(root), ENVIRONMENT_IDENTITY, NOW)
    (root / "backend/src/module.py").write_text("value = 2\n")
    with pytest.raises(QualificationSafetyError, match="source_changed"):
        verify_binding(
            binding(root) | {"source_fingerprint": "0" * 64},
            COMMIT,
            source_fingerprint(root),
            ENVIRONMENT_IDENTITY,
            NOW,
        )


def test_missing_or_wrong_hash_never_qualifies(tmp_path):
    reference = emit(tmp_path / "data.json", {"records": []})
    assert evidence_path(tmp_path, reference) == tmp_path / "data.json"
    (tmp_path / "data.json").write_text("changed")
    with pytest.raises(QualificationSafetyError, match="hash"):
        evidence_path(tmp_path, reference)
    (tmp_path / "data.json").unlink()
    with pytest.raises(QualificationSafetyError, match="missing"):
        evidence_path(tmp_path, reference)


@pytest.mark.parametrize("path", ["../secret", "/secret", "a/../../secret", "a\\secret", "./data"])
def test_paths_are_data_and_cannot_escape(tmp_path, path):
    with pytest.raises(QualificationSafetyError):
        evidence_path(tmp_path, {"path": path, "sha256": "a" * 64})


def test_duplicate_json_keys_and_external_symlink_rejected(tmp_path):
    (tmp_path / "data").write_text('{"passed":false,"passed":true}')
    with pytest.raises(QualificationSafetyError, match="duplicate"):
        load_json_report(tmp_path / "data")
    outside = tmp_path.parent / (uuid4().hex + ".json")
    outside.write_text("{}")
    (tmp_path / "link").symlink_to(outside)
    with pytest.raises(QualificationSafetyError, match="outside"):
        evidence_path(tmp_path, {"path": "link", "sha256": hashlib.sha256(b"{}").hexdigest()})


def test_junit_recounts_cases_and_requires_exact_collected_inventory(tmp_path):
    path = tmp_path / "tests.xml"
    junit(path)
    expected = [{"classname": "tests.integration.example", "name": "test_case"}]
    counts = junit_counts(path, inventory=expected)
    assert counts["tests"] == counts["integration_tests"] == 1
    with pytest.raises(QualificationSafetyError, match="incomplete"):
        junit_counts(path, inventory=expected + [{"classname": "other", "name": "missing"}])
    with pytest.raises(QualificationSafetyError, match="empty"):
        junit_counts(path, inventory=[])


@pytest.mark.parametrize(
    "tag,summary",
    [
        ("<failure/>", 'failures="1" errors="0" skipped="0"'),
        ("<error/>", 'failures="0" errors="1" skipped="0"'),
        ("<skipped/>", 'failures="0" errors="0" skipped="1"'),
        ("<failure/>", 'failures="0" errors="0" skipped="0"'),
    ],
)
def test_red_skipped_and_falsified_junit_fail(tmp_path, tag, summary):
    path = tmp_path / "tests.xml"
    junit(path, tag, summary)
    with pytest.raises(QualificationSafetyError):
        junit_counts(path)


def test_unsafe_xml_is_not_processed(tmp_path):
    path = tmp_path / "tests.xml"
    path.write_text('<!DOCTYPE a [<!ENTITY x SYSTEM "file:///secret">]><testsuites/>')
    with pytest.raises(QualificationSafetyError, match="unsafe_xml"):
        junit_counts(path)


@pytest.mark.parametrize(
    "change", [{"passed": False}, {"steps": []}, {"counts": {"tests": 2, "suites": 1}}]
)
def test_frontend_requires_complete_receipt(change):
    receipt, report = frontend()
    assert frontend_counts(receipt, report) == {"tests": 1, "suites": 1}
    receipt.update(change)
    with pytest.raises(QualificationSafetyError):
        frontend_counts(receipt, report)


@pytest.mark.parametrize(
    "key,value",
    [("numTotalTests", 2), ("numPendingTests", 1), ("numFailedTests", 1), ("success", False)],
)
def test_frontend_summary_cannot_replace_real_case_outcomes(key, value):
    receipt, report = frontend()
    report[key] = value
    with pytest.raises(QualificationSafetyError):
        frontend_counts(receipt, report)


def test_e2e_requires_every_declared_scenario_and_trace(tmp_path):
    trace = tmp_path / "trace.zip"
    trace.write_bytes(b"synthetic trace")
    receipt = {
        "passed": True,
        "expected_checks": list(E2E_SCENARIOS),
        "completed_checks": list(E2E_SCENARIOS),
        "checks": len(E2E_SCENARIOS),
        "browser_errors": [],
        "unauthenticated_status": 401,
        "trace": {"path": "trace.zip", "sha256": hashlib.sha256(trace.read_bytes()).hexdigest()},
    }
    assert e2e_counts(receipt, tmp_path)["checks"] == len(E2E_SCENARIOS)
    incomplete = copy.deepcopy(receipt)
    incomplete["completed_checks"].pop()
    with pytest.raises(QualificationSafetyError):
        e2e_counts(incomplete, tmp_path)
    trace.unlink()
    with pytest.raises(QualificationSafetyError):
        e2e_counts(receipt, tmp_path)


def test_green_synthetic_backend_is_only_demonstration_and_missing_proof_fails(tmp_path):
    root = workspace(tmp_path)
    directory = root / "evidence"
    header = binding(root)
    junit(directory / "backend.xml")
    inventory = header | {
        "cases": [{"classname": "tests.integration.example", "name": "test_case"}]
    }
    references = {
        "backend_junit": {
            "path": "backend.xml",
            "sha256": hashlib.sha256((directory / "backend.xml").read_bytes()).hexdigest(),
        },
        "backend_inventory": emit(directory / "inventory.json", inventory),
    }
    emit(directory / "bundle.json", header | {"evidence": references})
    result = qualify(root, directory, COMMIT, "R0", now=NOW)
    backend = next(item for item in result["criteria"] if item["id"] == "backend")
    assert backend["state"] == "passed" and backend["numerator"] == 1
    assert result["scope"] == "démonstration logicielle" and not result["operational_passed"]
    assert result["exit_code"] == 1
    (directory / "backend.xml").unlink()
    result = qualify(root, directory, COMMIT, "R0", now=NOW)
    assert (
        next(item for item in result["criteria"] if item["id"] == "backend")["state"] == "unknown"
    )


def test_run_rates_use_each_run_not_only_a_good_weighted_average():
    data = {
        "runs": [
            {"run_id": str(uuid4()), "n_candidates": 10000, "n_parsed": 10000, "status": "success"},
            {"run_id": str(uuid4()), "n_candidates": 100, "n_parsed": 98, "status": "success"},
        ]
    }
    result = metrics.parsing(data)
    assert result["percent"] > 99 and not result["passed"] and result["minimum_run_percent"] == 98


@pytest.mark.parametrize("value", [-1, True, float("nan"), float("inf")])
def test_invalid_measurements_are_not_accepted(value):
    with pytest.raises(QualificationSafetyError):
        metrics.number(value)


def test_golden_is_per_field_and_both_sources_required():
    fields = [
        {"source_id": source, "field": "price", "expected": "100", "actual": "100"}
        for source in ("miasa_odr", "mincc_ppn")
    ]
    assert metrics.golden({"fields": fields})["passed"]
    fields.append(
        {"source_id": "miasa_odr", "field": "currency", "expected": "MGA", "actual": "USD"}
    )
    assert not metrics.golden({"fields": fields})["passed"]


def test_equal_rebuild_counts_are_not_equal_content():
    data = {
        "before": [{"id": "one", "value": "100"}],
        "after": [{"id": "one", "value": "101"}],
        "network_requests": 0,
    }
    result = metrics.rebuild(data)
    assert result["numerator"] == 0 and not result["passed"] and not result["content_identical"]
    data["after"] = data["before"]
    assert metrics.rebuild(data)["passed"]
    data["network_requests"] = 1
    assert not metrics.rebuild(data)["passed"]


def test_less_than_ten_series_is_visible_and_not_compensated():
    series = [
        {
            "series_id": str(index),
            "forecast_count": 3,
            "backtest_windows": 3,
            "wape": 0.1,
            "leakage_detected": False,
            "training_snapshot_sha256": "a" * 64,
        }
        for index in range(9)
    ]
    result = metrics.forecasts({"series": series})
    assert not result["passed"] and result["numerator"] == result["denominator"] == 9
    series.append(series[0] | {"series_id": "tenth"})
    assert metrics.forecasts({"series": series})["passed"]


def test_latency_is_recomputed_from_all_samples():
    endpoints = [
        "/v1/prices",
        "/v1/prices/latest",
        "/v1/stocks",
        "/v1/trade",
        "/v1/kpis/market-health",
        "/v1/weather/anomalies",
    ]
    samples = [
        {"endpoint": endpoint, "status_code": 200, "elapsed_ms": 20}
        for endpoint in endpoints
        for _ in range(200)
    ]
    assert metrics.api_latency({"samples": samples})["passed"]
    for item in samples[-30:]:
        item["elapsed_ms"] = 2000
    assert not metrics.api_latency({"samples": samples})["passed"]


def test_copilot_revalidates_sql_without_executing_it():
    questions = [
        {
            "question_id": "one",
            "expected_view": "gold.price_monthly",
            "sql": "SELECT * FROM gold.price_monthly",
        }
    ]
    assert metrics.copilot({"questions": questions})["passed"]
    questions.append(
        {
            "question_id": "two",
            "expected_view": "gold.price_monthly",
            "sql": "DROP TABLE gold.price_monthly",
        }
    )
    assert not metrics.copilot({"questions": questions})["passed"]


def test_bulletin_numbers_must_equal_a_cited_fact():
    data = {
        "numbers": [{"fact_id": "one", "value": "100"}],
        "facts": {"one": {"value": "100", "citation": "query receipt"}},
    }
    assert metrics.bulletin(data)["passed"]
    data["numbers"][0]["value"] = "101"
    assert not metrics.bulletin(data)["passed"]


def test_planned_sources_are_never_active_qualified(tmp_path):
    registry = {
        identity: SimpleNamespace(status="planned", entrypoints=[]) for identity in REQUIRED_SOURCES
    }
    document = {
        "sources": [
            {
                "source_id": identity,
                "status": "active",
                "source_record_ids": ["fake"],
                "acquisition_receipt": "fake",
                "permission_receipt": "fake",
            }
            for identity in REQUIRED_SOURCES
        ]
    }
    result = metrics.source_counts(document, registry, tmp_path, NOW)
    assert result["numerator"] == 0 and result["denominator"] == len(REQUIRED_SOURCES) == 9
    assert not result["passed"]


def test_native_context_requires_runtime_image_identities(tmp_path, monkeypatch):
    root = workspace(tmp_path)
    for role in ("BACKEND", "WEB", "BROWSER"):
        monkeypatch.delenv("KETRIKA_PROOF_" + role + "_IMAGE_ID", raising=False)
    with pytest.raises(QualificationSafetyError, match="runtime_identity"):
        native_environment()
    for role in ("BACKEND", "WEB", "BROWSER"):
        monkeypatch.setenv("KETRIKA_PROOF_" + role + "_IMAGE_ID", "sha256:" + "a" * 64)
    value = capture_binding(root, COMMIT)
    assert value["environment"]["backend_image_id"] == "sha256:" + "a" * 64
    assert value["dataset"] == "mixed" and len(value["source_fingerprint"]) == 64


def test_provenance_binds_stored_values_to_real_fixture_cells(tmp_path):
    content = b'[{"product":"rice","price":2800}]'
    digest = hashlib.sha256(content).hexdigest()
    path = tmp_path / "source.json"
    path.write_bytes(content)
    source_record_id, observation_id = str(uuid4()), str(uuid4())
    proof = {
        "version": 1,
        "format": "json",
        "scope_path": [0],
        "cells": [
            {
                "field": "product_raw",
                "role": "identity",
                "kind": "text",
                "path": [0, "product"],
                "expected": "untrusted expectation",
            },
            {
                "field": "price_value",
                "role": "value",
                "kind": "number",
                "path": [0, "price"],
                "expected": "9999",
                "number_style": "decimal_dot",
                "raw_encoding": "json_number_lexeme",
            },
        ],
    }
    document = {
        "references": [
            {
                "source_record_id": source_record_id,
                "source_id": "fixture_metrics",
                "object_key": f"fixture_metrics/2026/10/{digest}.json",
                "content_sha256": digest,
                "mime_type": "application/json",
                "file": {"path": "source.json", "sha256": digest},
            }
        ],
        "observations": [
            {
                "table": "price_observation",
                "values": {
                    "observation_id": observation_id,
                    "source_record_id": source_record_id,
                    "product_raw": "rice",
                    "price_raw": "2800",
                    "price_value": "2800",
                    "extraction_method": "deterministic",
                    "evidence": {"provenance": proof},
                },
            }
        ],
    }
    result = metrics.provenance(document, tmp_path)
    assert result["passed"] and result["numerator"] == result["denominator"] == 1
    document["observations"][0]["values"]["price_value"] = "2900"
    assert not metrics.provenance(document, tmp_path)["passed"]
    document["observations"][0]["values"]["extraction_method"] = "llm_unverified"
    result = metrics.provenance(document, tmp_path)
    assert result["llm_unverified"] == 1 and result["numerator"] == 0
    assert result["denominator"] == 1 and not result["passed"]


@pytest.mark.parametrize("domain", ["localhost", "127.0.0.1", "::1"])
def test_loopback_budget_isolation_preserves_real_admission(domain):
    from dataclasses import replace

    from ketrika.core.http_budget import Admission
    from tests.conftest import _loopback_admission

    admission = Admission("source", domain, "http://localhost:1234", 3, 5, 0.2)
    first = _loopback_admission(admission, "first")
    assert first == replace(admission, domain=f"fixture-first-{domain}")
    assert first == _loopback_admission(admission, "first")
    assert first != _loopback_admission(admission, "second")


@pytest.mark.parametrize("domain", ["example.org", "fixture.invalid", "localhost.example.org"])
def test_loopback_isolation_never_changes_non_loopback_budget(domain):
    from ketrika.core.http_budget import Admission
    from tests.conftest import _loopback_admission

    admission = Admission("source", domain, "https://example.org", 3, 5, 0.2)
    assert _loopback_admission(admission, "first") is admission


def test_child_pytest_cannot_overwrite_parent_inventory(monkeypatch):
    from tests import conftest

    monkeypatch.setenv("KETRIKA_QA_INVENTORY", "/app/.venv/qa-inventory.json")
    monkeypatch.setenv("KETRIKA_QA_INVENTORY_OWNER_PID", "different-parent")
    monkeypatch.setattr(
        conftest, "capture_binding", lambda *_: pytest.fail("child overwrote inventory")
    )
    conftest.pytest_collection_finish(None)
