"""Readonly comparison of isolated pricing-quarantine snapshots; no row exports."""

import json
import sys
from pathlib import Path


def verify(before, after):
    if set(before["tables"]) != set(after["tables"]):
        raise ValueError("table_inventory_changed")
    protected = 0
    for table, snapshot in before["tables"].items():
        if table == "obs.quarantine_ledger":
            continue
        if snapshot != after["tables"][table]:
            raise ValueError("protected_table_changed:" + table)
        protected += 1
    old = {json.dumps(row, sort_keys=True) for row in before["quarantines"]}
    current = {json.dumps(row, sort_keys=True) for row in after["quarantines"]}
    if not old.issubset(current):
        raise ValueError("historical_quarantine_changed")
    additions = [json.loads(row) for row in current - old]
    if any(row["revoked"] for row in additions):
        raise ValueError("new_quarantine_already_revoked")
    counts = {}
    for row in additions:
        key = row["reason_code"] + ":" + row["table_name"]
        counts[key] = counts.get(key, 0) + 1
    expected = {
        "UNVERIFIED_ECONOMIC_INPUTS:meta.source_record": 4,
        "UNVERIFIED_ECONOMIC_INPUTS:obs.price_observation": 4592,
        "POTENTIALLY_CONTAMINATED_TRAINING:ml.forecast": 84,
    }
    if counts != expected:
        raise ValueError("quarantine_scope_mismatch")
    if after["revision"] != "0024_unverified_economic_inputs":
        raise ValueError("migration_not_received")
    return {
        "passed": True,
        "protected_tables": protected,
        "quarantine_additions": counts,
        "historical_quarantines_preserved": len(old),
        "active_database_modified": False,
        "bronze_api_used": False,
        "scope": "isolated SQL migration; not source, rebuild, model or deployment qualification",
    }


if __name__ == "__main__":
    before, after = (json.loads(Path(path).read_text()) for path in sys.argv[1:3])
    print(json.dumps(verify(before, after), sort_keys=True))
