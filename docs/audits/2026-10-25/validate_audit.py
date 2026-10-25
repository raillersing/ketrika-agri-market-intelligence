"""Validate documentary traceability and saved evidence, without repeating app tests."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from ketrika.core.execution_plan import read_states, read_tasks, validate_documents
from ketrika.core.qualification_reports import source_fingerprint

root = Path("/workspace")
folder = root / "docs/audits/2026-10-25"
plan = root.joinpath("docs/plan/MARKET_INTELLIGENCE_EXECUTION_PLAN.md").read_text()
progress = root.joinpath("docs/plan/PROGRESS.md").read_text()
result: dict[str, Any] = {"scope": "documentary reception, no product gate"}
result["governance"] = validate_documents(plan, progress)
tasks, states = read_tasks(plan), read_states(progress)
matrix = json.loads(folder.joinpath("task_matrix.json").read_text())
assert len(matrix) == 74 and {row["task_id"] for row in matrix} == set(tasks)
for row in matrix:
    task = tasks[row["task_id"]]
    assert row["historical_status"] == states[row["task_id"]].status
    assert set(row["dependencies"]) == task.dependencies
    assert row["priority"] == task.priority
assert Counter(row["historical_status"] for row in matrix) == {
    "DONE": 7,
    "IN_PROGRESS": 52,
    "TODO": 15,
}
corrective = folder.joinpath("CORRECTIVE_EXECUTION_PLAN.md").read_text()
lots = re.findall(r"(?m)^### (AU-\d+) — ", corrective)
assert lots == [f"AU-{n:02d}" for n in range(1, 27)]
audit = folder.joinpath("INDEPENDENT_AUDIT.md").read_text()
issues = re.findall(r"(?m)^\| (IA-\d+) \|", audit)
assert issues == [f"IA-{n:02d}" for n in range(1, 21)]
runtime = json.loads(folder.joinpath("evidence/runtime.json").read_text())
assert len(runtime["api"]) == 60
assert "sr.storage_key" in runtime["as_of_dataset"]["detail"]
browser = json.loads(folder.joinpath("evidence/browser.json").read_text())
assert len(browser["pages"]) == 12 and all(page.get("status") == 200 for page in browser["pages"])
assert not browser["errors"] and browser["mobile_overflow_px"] == 0
assert browser["invalid_cookie_home_status"] == 200
assert browser["invalid_cookie_home_contains_hardcoded_price"] is True
safety = json.loads(folder.joinpath("evidence/safety.json").read_text())
for field in (
    "smtp_alert_transport_attempted_with_gate_off",
    "smtp_failure_transport_attempted_with_gate_off",
    "invalid_dump_without_manifest_or_tool_accepted",
    "revoked_token_accepted_other_process",
):
    assert safety[field] is True
assert safety["revoked_token_accepted_same_process"] is False
npm = json.loads(folder.joinpath("evidence/npm-audit.json").read_text())
prod = json.loads(folder.joinpath("evidence/npm-prod-audit.json").read_text())
python_audit = json.loads(folder.joinpath("evidence/python-audit.json").read_text())
result["npm_all"] = npm["metadata"]["vulnerabilities"]
result["npm_prod"] = prod["metadata"]["vulnerabilities"]
result["python_affected_packages"] = sum(
    bool(dep.get("vulns")) for dep in python_audit["dependencies"]
)
result["python_reported_ids"] = sum(
    len(dep.get("vulns", [])) for dep in python_audit["dependencies"]
)
assert result["python_affected_packages"] == 5 and result["python_reported_ids"] == 44
fingerprint = source_fingerprint(root)
assert fingerprint == "7c79ce2e064d6c049bc1b4ed3f8f5e0c0d176dcb8ea7300a4c3d8854c1b836a5"
result["source_fingerprint"] = fingerprint
broken = []
documents = list(folder.glob("*.md")) + [
    root / "README.md",
    root / "docs/HANDOFF.md",
    root / "docs/SECURITY_REVIEW.md",
    root / "docs/MARKET_INTELLIGENCE_REPORT.md",
]
for path in documents:
    for link in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if "://" in link or link.startswith("#"):
            continue
        target = (path.parent / link.split("#")[0]).resolve()
        if not target.exists():
            broken.append({"document": str(path.relative_to(root)), "target": link})
assert not broken, broken
result.update(
    {
        "tasks": len(matrix),
        "corrective_lots": len(lots),
        "findings": len(issues),
        "links_checked": len(documents),
        "passed": True,
    }
)
folder.joinpath("evidence/documentary-validation.json").write_text(
    json.dumps(result, indent=2, ensure_ascii=False)
)
manifest = {}
for path in sorted(folder.rglob("*")):
    if path.is_file() and path.name != "manifest.json":
        manifest[str(path.relative_to(folder))] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
folder.joinpath("evidence/manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(result, ensure_ascii=False))
