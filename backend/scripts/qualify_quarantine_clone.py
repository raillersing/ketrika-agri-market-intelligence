"""Read-only clone snapshots and strict historical-quarantine comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

from ketrika.gold.refresh import ORDERED_GOLD_VIEWS

OBSERVATIONS = {
    "obs." + name
    for name in (
        "price_observation",
        "stock_observation",
        "trade_flow",
        "production_observation",
        "cpi_observation",
        "weather_observation",
        "macro_observation",
    )
}
SCHEMAS = ("auth", "meta", "ref", "obs", "ml", "ops")


def digest(rows):
    h = hashlib.sha256()
    for row in sorted(rows):
        encoded = row.encode()
        h.update(len(encoded).to_bytes(8, "big"))
        h.update(encoded)
    return h.hexdigest()


def capture():
    engine = create_engine(os.environ["DATABASE_URL"])
    if not re.fullmatch(r"ketrika_restore_[a-z0-9_]+", engine.url.database or ""):
        raise ValueError("An explicitly selected restore clone is required")
    result = {"captured_at": datetime.now(UTC).isoformat(), "tables": {}}
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
            result["database"] = connection.scalar(text("SELECT current_database()"))
            result["revision"] = connection.scalar(text("SELECT version_num FROM alembic_version"))
            result["read_only"] = connection.scalar(text("SHOW transaction_read_only")) == "on"
            tables = connection.execute(
                text(
                    "SELECT n.nspname,c.relname,pg_get_userbyid(c.relowner),c.oid "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE c.relkind='r' ORDER BY n.nspname,c.relname"
                )
            ).all()
            for schema, name, owner, oid in tables:
                if schema not in SCHEMAS:
                    continue
                if not re.fullmatch(r"[a-z_][a-z_0-9]*", name):
                    raise ValueError("Unexpected table identifier")
                table = schema + "." + name
                projection = "to_jsonb(t)" + (" - 'superseded_by'" if table in OBSERVATIONS else "")
                rows = connection.scalars(
                    text(f"SELECT ({projection})::text FROM {table} t LIMIT 100001")
                ).all()
                if len(rows) > 100000:
                    raise ValueError("Snapshot row budget exceeded")
                permissions = connection.execute(
                    text(
                        "SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END, "
                        "pg_get_userbyid(a.grantor),a.privilege_type,a.is_grantable "
                        "FROM pg_class c CROSS JOIN LATERAL "
                        "aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a "
                        "WHERE c.oid=:oid ORDER BY 1,2,3,4"
                    ),
                    {"oid": oid},
                ).all()
                snapshot = {
                    "count": len(rows),
                    "raw_sha256": digest(rows),
                    "owner": owner,
                    "permissions": [list(row) for row in permissions],
                }
                if table in OBSERVATIONS:
                    primary = connection.scalars(
                        text(
                            "SELECT a.attname FROM pg_index i JOIN pg_attribute a "
                            "ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey) "
                            "WHERE i.indrelid=:oid AND i.indisprimary ORDER BY a.attnum"
                        ),
                        {"oid": oid},
                    ).all()
                    if primary != ["observation_id"]:
                        raise ValueError(
                            "Observation primary key does not match the repair contract"
                        )
                    snapshot["links"] = dict(
                        connection.execute(
                            text(f"SELECT observation_id::text,superseded_by::text FROM {table}")
                        ).all()
                    )
                    snapshot["origins"] = dict(
                        connection.execute(
                            text(f"SELECT observation_id::text,source_record_id::text FROM {table}")
                        ).all()
                    )
                result["tables"][table] = snapshot
            result["records"] = [
                dict(row)
                for row in connection.execute(
                    text(
                        "SELECT source_record_id::text,object_key,content_sha256 FROM meta.source_record "
                        "ORDER BY source_record_id"
                    )
                ).mappings()
            ]
            result["quarantines"] = []
            if "obs.quarantine_ledger" in result["tables"]:
                result["quarantines"] = [
                    dict(row)
                    for row in connection.execute(
                        text(
                            "SELECT table_name,observation_id::text,source_record_id::text,reason_code, "
                            "revoked_at IS NOT NULL AS revoked FROM obs.quarantine_ledger "
                            "ORDER BY table_name,observation_id"
                        )
                    ).mappings()
                ]
            result["gold"] = [
                dict(row)
                for row in connection.execute(
                    text(
                        "SELECT matviewname,ispopulated FROM pg_matviews WHERE schemaname='gold' "
                        "ORDER BY matviewname"
                    )
                ).mappings()
            ]
            result["cycle_guard_tables"] = connection.scalars(
                text(
                    "SELECT n.nspname||'.'||c.relname FROM pg_trigger t "
                    "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "JOIN pg_proc p ON p.oid=t.tgfoid WHERE n.nspname='obs' "
                    "AND p.proname='check_supersession_acyclic' AND NOT p.prosecdef "
                    "AND t.tgenabled='O' ORDER BY 1"
                )
            ).all()
    finally:
        engine.dispose()
    return result


def verify(before, after, bronze_before, bronze_after):
    def require(condition, reason):
        if not condition:
            raise ValueError(reason)

    require(before["database"] == after["database"], "Clone identity changed")
    require(
        re.fullmatch(r"ketrika_restore_[a-z0-9_]+", before["database"]) is not None,
        "Expected a restore clone",
    )
    require(after["revision"] == "0022_supersession_cycle_guard", "Wrong target revision")
    require(
        set(after["cycle_guard_tables"]) == OBSERVATIONS, "Cycle protection missing or not enabled"
    )
    require(before["read_only"] and after["read_only"], "Snapshot was not read-only")
    require(OBSERVATIONS <= before["tables"].keys(), "Observation inventory incomplete")
    require(before["records"] == after["records"], "Source records changed")
    require(
        after["tables"].keys() - before["tables"].keys()
        <= {"auth.token_revocation", "obs.quarantine_ledger"},
        "Unexpected new data table",
    )
    for table, original in before["tables"].items():
        require(table in after["tables"], "Existing table disappeared")
        current = after["tables"][table]
        require(
            type(original["count"]) is int and original["count"] >= 0,
            "Invalid protected table count",
        )
        require(
            isinstance(original["raw_sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", original["raw_sha256"]) is not None,
            "Invalid protected table digest",
        )
        for key in ("count", "raw_sha256", "owner", "permissions"):
            require(original[key] == current[key], f"Protected table changed: {table}/{key}")
    active = {
        (q["table_name"], q["observation_id"], q["reason_code"]): q["source_record_id"]
        for q in after["quarantines"]
        if not q["revoked"]
    }
    repaired = 0
    for table in sorted(OBSERVATIONS):
        original = before["tables"][table]["links"]
        current = after["tables"][table]["links"]
        require(original.keys() == current.keys(), "Observation identity inventory changed")
        for identifier, previous in original.items():
            replacement = current[identifier]
            if previous != replacement:
                require(previous == identifier and replacement is None, "Unexpected link mutation")
                require(
                    (table, identifier, "HISTORICAL_SELF_LINK") in active,
                    "Historical repair lacks permanent quarantine",
                )
                require(
                    active[(table, identifier, "HISTORICAL_SELF_LINK")]
                    == before["tables"][table]["origins"][identifier],
                    "Historical quarantine refers to a different source record",
                )
                repaired += 1
            visited, cursor = set(), identifier
            while cursor is not None:
                require(cursor in current, "Dangling revision target")
                require(cursor not in visited, "Cycle remains after repair")
                visited.add(cursor)
                cursor = current[cursor]
    for report in (bronze_before, bronze_after):
        require(report["unchanged_during_audit"], "Bronze changed during inventory")
        require(not report["invalid_objects"], "Invalid original Bronze object")
    require(
        bronze_before["inventory_after"] == bronze_after["inventory_before"],
        "Original Bronze inventory changed between audits",
    )
    require(bronze_before["objects"] == bronze_after["objects"], "Original Bronze bytes changed")
    latest = {obj["key"]: obj["sha256"] for obj in bronze_after["objects"] if obj["latest"]}
    missing = 0
    for record in after["records"]:
        if latest.get(record["object_key"]) != record["content_sha256"]:
            require(
                ("meta.source_record", record["source_record_id"], "MISSING_BRONZE_OBJECT")
                in active,
                "Unverifiable source record not quarantined",
            )
            require(
                active[("meta.source_record", record["source_record_id"], "MISSING_BRONZE_OBJECT")]
                == record["source_record_id"],
                "Source quarantine identity mismatch",
            )
            missing += 1
    require(
        sorted(view["matviewname"] for view in after["gold"]) == sorted(ORDERED_GOLD_VIEWS),
        "Gold graph incomplete",
    )
    require(all(not view["ispopulated"] for view in after["gold"]), "Unexpected Gold publication")
    return {
        "passed": True,
        "scope": "historical repair on isolated clone, not rebuild/source/model qualification",
        "protected_tables": len(before["tables"]),
        "historical_links_repaired": repaired,
        "unverifiable_records_quarantined": missing,
        "cycles_remaining": 0,
        "bronze_versions_preserved": len(bronze_after["objects"]),
        "original_bronze_fully_qualified": False,
        "r08_qualified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "verify"))
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    if args.action == "capture":
        if len(args.files) != 1:
            parser.error("capture requires one new output file")
        output, result = args.files[0], capture()
    else:
        if len(args.files) != 5:
            parser.error("verify requires before/after SQL, before/after Bronze and new output")
        *inputs, output = args.files
        result = verify(*(json.loads(path.read_text()) for path in inputs))
    with output.open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)


if __name__ == "__main__":
    main()
