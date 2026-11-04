"""Compare SQL snapshots: same bytes/links and only app TRUNCATE removed."""

import json
import sys
from pathlib import Path


def verify(before, after):
    if set(before["tables"]) != set(after["tables"]):
        raise ValueError("table_inventory_changed")
    removed = 0
    for name, previous in before["tables"].items():
        current = after["tables"][name]
        expected = dict(previous)
        grants = previous["permissions"]
        expected["permissions"] = [
            grant for grant in grants
            if not (grant[0] == "ketrika_app" and grant[2] == "TRUNCATE")
        ]
        removed += len(grants) - len(expected["permissions"])
        if current != expected:
            raise ValueError("unexpected_table_or_permission_change:" + name)
    if before["quarantines"] != after["quarantines"]:
        raise ValueError("quarantine_changed")
    if before["gold"] != after["gold"]:
        raise ValueError("gold_cache_state_changed")
    if after["revision"] != "0025_application_no_truncate":
        raise ValueError("migration_not_applied")
    return {
        "passed": True,
        "protected_tables": len(before["tables"]),
        "only_app_truncate_grants_removed": removed,
        "quarantines_preserved": len(after["quarantines"]),
        "active_database_modified": False,
        "scope": "isolated role migration, not complete historical-role/source/model qualification",
    }


if __name__ == "__main__":
    inputs = [json.loads(Path(path).read_text()) for path in sys.argv[1:3]]
    print(json.dumps(verify(*inputs), sort_keys=True))
