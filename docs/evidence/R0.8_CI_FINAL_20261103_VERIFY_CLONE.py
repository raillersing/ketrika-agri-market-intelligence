"""Verify raw data, lineage and deliberate permission/quarantine deltas only."""

import importlib.util
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text


def verify(before, after):
    if (
        before["revision"] != "0021_gold_graph"
        or after["revision"] != "0027_quarantined_normalization_copies"
    ):
        raise ValueError("unexpected_migration_range")
    if set(before["tables"]) != set(after["tables"]):
        raise ValueError("table_inventory_changed")
    removed = 0
    for table, prior in before["tables"].items():
        current = after["tables"][table]
        expected_grants = [
            grant
            for grant in prior["permissions"]
            if not (
                grant[0] == "ketrika_app"
                and grant[2] == "TRUNCATE"
                or table == "obs.quarantine_ledger"
                and grant[0] == "copilot_ro"
                and grant[2] == "SELECT"
            )
        ]
        removed += len(prior["permissions"]) - len(expected_grants)
        if current["owner"] != prior["owner"] or current["permissions"] != expected_grants:
            raise ValueError("unexpected_rights_change:" + table)
        if table != "obs.quarantine_ledger":
            expected = dict(prior, permissions=expected_grants)
            if current != expected:
                raise ValueError("protected_data_or_lineage_changed:" + table)
    old = {json.dumps(row, sort_keys=True) for row in before["quarantines"]}
    new = {json.dumps(row, sort_keys=True) for row in after["quarantines"]}
    if not old.issubset(new):
        raise ValueError("old_quarantine_changed")
    additions = [json.loads(row) for row in new - old]
    allowed = {
        "UNVERIFIED_ECONOMIC_INPUTS",
        "QUARANTINED_NORMALIZATION_PARENT",
        "POTENTIALLY_CONTAMINATED_TRAINING",
    }
    counts = {}
    for row in additions:
        if row["revoked"] or row["reason_code"] not in allowed:
            raise ValueError("unexpected_quarantine_addition")
        key = row["reason_code"] + ":" + row["table_name"]
        counts[key] = counts.get(key, 0) + 1
    if len(additions) != 4916:
        raise ValueError("quarantine_addition_count_changed")
    if any(row["reason_code"] in allowed for row in before["quarantines"]):
        raise ValueError("original_quarantine_scope_requires_review")
    engine = create_engine(os.environ["DATABASE_URL"])
    if engine.url.database != "ketrika_restore_final_20261103":
        raise ValueError("isolated_final_clone_required")
    spec = importlib.util.spec_from_file_location(
        "snapshot", "/app/scripts/qualify_quarantine_clone.py"
    )
    assert spec is not None and spec.loader is not None
    snapshot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(snapshot)
    with engine.connect() as connection, connection.begin():
        connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        rows = connection.scalars(
            text(
                "SELECT to_jsonb(q)::text FROM obs.quarantine_ledger q WHERE reason_code NOT IN ('UNVERIFIED_ECONOMIC_INPUTS','QUARANTINED_NORMALIZATION_PARENT','POTENTIALLY_CONTAMINATED_TRAINING')"
            )
        ).all()
        if snapshot.digest(rows) != before["tables"]["obs.quarantine_ledger"]["raw_sha256"]:
            raise ValueError("original_quarantine_bytes_changed")
    engine.dispose()
    caches = {row["matviewname"]: row["ispopulated"] for row in after["gold"]}
    for name in (
        "price_obs_current",
        "price_monthly",
        "price_monthly_best",
        "price_changes",
        "market_health",
        "market_coverage",
        "stock_latest",
        "trade_monthly",
        "import_dependency",
        "forecast_latest",
    ):
        if caches[name]:
            raise ValueError("unsafe_cache_still_populated:" + name)
    return {
        "passed": True,
        "protected_tables": len(before["tables"]),
        "unchanged_original_quarantines": len(old),
        "quarantine_additions": counts,
        "permission_entries_removed": removed,
        "unsafe_caches_invalidated": True,
        "active_database_modified": False,
        "scope": "isolated SQL reception, not market/model/deployment qualification",
    }


if __name__ == "__main__":
    before, after = [json.loads(Path(path).read_text()) for path in sys.argv[1:3]]
    print(json.dumps(verify(before, after), sort_keys=True))
