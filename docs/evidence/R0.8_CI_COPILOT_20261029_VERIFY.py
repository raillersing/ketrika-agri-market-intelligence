"""Verify a targeted ACL migration changed no historical business state."""
import json
from pathlib import Path

base = Path("/tmp")
before = json.loads((base / "copilot-migration-before-20261029.json").read_text())
after = json.loads((base / "copilot-migration-after-20261029.json").read_text())
audit = json.loads((base / "copilot-migration-role-audit-20261029.json").read_text())
assert before["database"] == after["database"] == "ketrika_restore_copilot_20261029"
assert before.pop("revision") == "0022_supersession_cycle_guard"
assert after.pop("revision") == "0023_copilot_gold_only"
before.pop("captured_at")
after.pop("captured_at")
permissions = before["tables"]["obs.quarantine_ledger"]["permissions"]
removed = ["copilot_ro", "ketrika", "SELECT", False]
assert permissions.count(removed) == 1
permissions.remove(removed)
assert before == after, "Unexpected change outside the one declared ACL"
failures = audit["assessment"]["failures"]
assert len(failures) == 27 and all(row["role"] == "ketrika_app" for row in failures)
assert {row["reason"] for row in failures} == {
    "missing_schema_usage", "missing_select", "missing_insert", "missing_update"
}
print(json.dumps({
    "passed": True, "tables_preserved": len(before["tables"]),
    "acl_removed": removed, "historical_application_profile_failures": len(failures),
    "r08_qualified": False, "deployment_qualified": False,
    "scope": "isolated second historical clone; one ACL removed, no business change"
}, indent=2, sort_keys=True))
