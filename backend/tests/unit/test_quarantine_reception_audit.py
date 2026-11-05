"""The clone receiver rejects value loss, fake repairs and incomplete provenance."""

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

PATH = Path("/workspace/backend/scripts/qualify_quarantine_clone.py")
if not PATH.exists():
    PATH = Path(__file__).resolve().parents[2] / "scripts" / "qualify_quarantine_clone.py"
spec = importlib.util.spec_from_file_location("quarantine_clone_audit", PATH)
assert spec is not None and spec.loader is not None
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def fixture_reports():
    tables = {
        table: {
            "count": 0,
            "raw_sha256": audit.digest([]),
            "owner": "ketrika",
            "permissions": [],
            "links": {},
            "origins": {},
        }
        for table in audit.OBSERVATIONS
    }
    tables["obs.price_observation"].update(
        count=1,
        raw_sha256=audit.digest(["synthetic raw"]),
        links={"observation": "observation"},
        origins={"observation": "source-record"},
    )
    tables["meta.source_record"] = {
        "count": 1,
        "raw_sha256": audit.digest(["synthetic record"]),
        "owner": "ketrika",
        "permissions": [],
    }
    before = {
        "database": "ketrika_restore_unit",
        "revision": "0018_gold_scope_permissions",
        "read_only": True,
        "tables": tables,
        "quarantines": [],
        "cycle_guard_tables": [],
        "records": [
            {
                "source_record_id": "source-record",
                "object_key": "missing",
                "content_sha256": "a" * 64,
            }
        ],
        "gold": [{"matviewname": name, "ispopulated": False} for name in audit.ORDERED_GOLD_VIEWS],
    }
    after = deepcopy(before)
    after["revision"] = "0022_supersession_cycle_guard"
    after["cycle_guard_tables"] = sorted(audit.OBSERVATIONS)
    after["tables"]["obs.price_observation"]["links"]["observation"] = None
    after["quarantines"] = [
        {
            "table_name": "obs.price_observation",
            "observation_id": "observation",
            "source_record_id": "source-record",
            "reason_code": "HISTORICAL_SELF_LINK",
            "revoked": False,
        },
        {
            "table_name": "meta.source_record",
            "observation_id": "source-record",
            "source_record_id": "source-record",
            "reason_code": "MISSING_BRONZE_OBJECT",
            "revoked": False,
        },
    ]
    bronze = {
        "unchanged_during_audit": True,
        "invalid_objects": [],
        "inventory_before": ["synthetic-version"],
        "inventory_after": ["synthetic-version"],
        "objects": [{"key": "other", "sha256": "b" * 64, "latest": True}],
    }
    return before, after, bronze, deepcopy(bronze)


def test_permanent_link_repair_is_bounded_and_not_rebuild_qualification():
    result = audit.verify(*fixture_reports())
    assert result["passed"] and result["historical_links_repaired"] == 1
    assert result["unverifiable_records_quarantined"] == 1
    assert result["r08_qualified"] is False
    assert result["original_bronze_fully_qualified"] is False


@pytest.mark.parametrize(
    "case",
    [
        "raw",
        "count",
        "rights",
        "missing_table",
        "new_table",
        "new_record",
        "cycle",
        "dangling",
        "missing_quarantine",
        "revoked",
        "wrong_reason",
        "wrong_source",
        "missing_bronze_quarantine",
        "bronze_changed",
        "bad_object",
        "gold_published",
        "fake_gold",
        "guard_missing",
        "wrong_database",
        "wrong_revision",
        "not_readonly",
    ],
)
def test_incomplete_or_corrupt_reception_cannot_pass(case):
    before, after, bronze_before, bronze_after = fixture_reports()
    price = after["tables"]["obs.price_observation"]
    if case == "raw":
        price["raw_sha256"] = "corrupted"
    elif case == "count":
        price["count"] = 2
    elif case == "rights":
        price["permissions"] = [["copilot_ro", "INSERT"]]
    elif case == "missing_table":
        del after["tables"]["meta.source_record"]
    elif case == "new_table":
        after["tables"]["obs.unknown"] = {}
    elif case == "new_record":
        after["records"][0]["object_key"] = "fabricated"
    elif case == "cycle":
        price["links"]["observation"] = "observation"
    elif case == "dangling":
        price["links"]["observation"] = "unknown"
    elif case == "missing_quarantine":
        after["quarantines"].pop(0)
    elif case == "revoked":
        after["quarantines"][0]["revoked"] = True
    elif case == "wrong_reason":
        after["quarantines"][0]["reason_code"] = "MANUAL_INVESTIGATION"
    elif case == "wrong_source":
        after["quarantines"][0]["source_record_id"] = "other"
    elif case == "missing_bronze_quarantine":
        after["quarantines"].pop(1)
    elif case == "bronze_changed":
        bronze_after["inventory_before"] = ["changed"]
    elif case == "bad_object":
        bronze_after["invalid_objects"] = ["corrupted"]
    elif case == "gold_published":
        after["gold"][0]["ispopulated"] = True
    elif case == "fake_gold":
        after["gold"][0]["matviewname"] = "invented"
    elif case == "guard_missing":
        after["cycle_guard_tables"].pop()
    elif case == "wrong_database":
        before["database"] = after["database"] = "ketrika"
    elif case == "wrong_revision":
        after["revision"] = "0018_gold_scope_permissions"
    elif case == "not_readonly":
        after["read_only"] = False
    with pytest.raises(ValueError):
        audit.verify(before, after, bronze_before, bronze_after)


def test_row_hash_is_order_independent_but_not_ambiguous():
    assert audit.digest(["a", "bc"]) == audit.digest(["bc", "a"])
    assert audit.digest(["a", "bc"]) != audit.digest(["ab", "c"])
