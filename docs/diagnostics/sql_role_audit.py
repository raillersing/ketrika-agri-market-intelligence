"""Read-only effective SQL role profile audit; never repairs permissions."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, bindparam, create_engine, text

SCHEMAS = ("auth", "dq", "gold", "meta", "ml", "obs", "ops", "ref")
ROLES = ("ketrika_app", "copilot_ro")
WRITES = ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
OBS = (
    "price_observation",
    "stock_observation",
    "trade_flow",
    "production_observation",
    "cpi_observation",
    "weather_observation",
    "macro_observation",
)
MAX_OBJECTS = 1024


def collect(connection: Connection) -> dict[str, Any]:
    """Caller must enter a read-only repeatable-read transaction first."""
    if connection.scalar(text("SHOW transaction_read_only")) != "on":
        raise ValueError("Read-only transaction required")
    if connection.scalar(text("SHOW transaction_isolation")) != "repeatable read":
        raise ValueError("Repeatable-read snapshot required")
    result: dict[str, Any] = {
        "captured_at": datetime.now(UTC).isoformat(),
        "database": connection.scalar(text("SELECT current_database()")),
        "read_only": True,
        "isolation": "repeatable read",
        "roles": {},
    }
    for role in ROLES:
        flags = (
            connection.execute(
                text(
                    "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolcanlogin "
                    "FROM pg_roles WHERE rolname=:role"
                ),
                {"role": role},
            )
            .mappings()
            .one_or_none()
        )
        if flags is None:
            result["roles"][role] = None
            continue
        schemas = (
            connection.execute(
                text(
                    "SELECT nspname,has_schema_privilege(:role,oid,'USAGE') AS usage,"
                    "has_schema_privilege(:role,oid,'CREATE') AS create "
                    "FROM pg_namespace WHERE nspname IN :schemas ORDER BY nspname"
                ).bindparams(bindparam("schemas", expanding=True)),
                {"role": role, "schemas": SCHEMAS},
            )
            .mappings()
            .all()
        )
        objects = (
            connection.execute(
                text(
                    "SELECT n.nspname AS schema,c.relname AS name,c.relkind AS kind,"
                    "has_table_privilege(:role,c.oid,'SELECT') AS select,"
                    "has_table_privilege(:role,c.oid,'INSERT') AS insert,"
                    "has_table_privilege(:role,c.oid,'UPDATE') AS update,"
                    "has_table_privilege(:role,c.oid,'DELETE') AS delete,"
                    "has_table_privilege(:role,c.oid,'TRUNCATE') AS truncate,"
                    "has_table_privilege(:role,c.oid,'REFERENCES') AS references,"
                    "has_table_privilege(:role,c.oid,'TRIGGER') AS trigger "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname IN :schemas AND c.relkind IN ('r','p','v','m','f') "
                    "ORDER BY n.nspname,c.relname LIMIT :bound"
                ).bindparams(bindparam("schemas", expanding=True)),
                {"role": role, "schemas": SCHEMAS, "bound": MAX_OBJECTS + 1},
            )
            .mappings()
            .all()
        )
        sequences = (
            connection.execute(
                text(
                    "SELECT n.nspname AS schema,c.relname AS name,"
                    "has_sequence_privilege(:role,c.oid,'USAGE') AS usage,"
                    "has_sequence_privilege(:role,c.oid,'SELECT') AS select,"
                    "has_sequence_privilege(:role,c.oid,'UPDATE') AS update "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname IN :schemas AND c.relkind='S' "
                    "ORDER BY n.nspname,c.relname LIMIT :bound"
                ).bindparams(bindparam("schemas", expanding=True)),
                {"role": role, "schemas": SCHEMAS, "bound": MAX_OBJECTS + 1},
            )
            .mappings()
            .all()
        )
        if len(objects) > MAX_OBJECTS or len(sequences) > MAX_OBJECTS:
            raise ValueError("Object inventory bound exceeded")
        # Only statement_timeout is extracted; arbitrary role settings may contain secrets.
        timeouts = (
            connection.execute(
                text(
                    "SELECT s.setdatabase AS database_oid,setting "
                    "FROM pg_db_role_setting s JOIN pg_roles r ON r.oid=s.setrole "
                    "CROSS JOIN LATERAL unnest(s.setconfig) setting "
                    "WHERE r.rolname=:role AND setting LIKE 'statement_timeout=%' "
                    "AND (s.setdatabase=0 OR s.setdatabase=(SELECT oid FROM pg_database "
                    "WHERE datname=current_database())) ORDER BY s.setdatabase"
                ),
                {"role": role},
            )
            .mappings()
            .all()
        )
        memberships = connection.scalars(
            text(
                "SELECT parent.rolname FROM pg_auth_members m "
                "JOIN pg_roles parent ON parent.oid=m.roleid "
                "JOIN pg_roles member ON member.oid=m.member "
                "WHERE member.rolname=:role ORDER BY parent.rolname"
            ),
            {"role": role},
        ).all()
        result["roles"][role] = {
            "flags": dict(flags),
            "schemas": [dict(row) for row in schemas],
            "objects": [dict(row) for row in objects],
            "sequences": [dict(row) for row in sequences],
            "statement_timeout_settings": [dict(row) for row in timeouts],
            "direct_memberships": list(memberships),
        }
    return result


def evaluate(snapshot: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, str]] = []

    def fail(role: str, subject: str, reason: str) -> None:
        failures.append({"role": role, "subject": subject, "reason": reason})

    for role in ROLES:
        profile = snapshot["roles"].get(role)
        if profile is None:
            fail(role, "role", "missing_role")
            continue
        flags = profile["flags"]
        if any(
            flags.get(flag) is not False
            for flag in (
                "rolsuper",
                "rolcreatedb",
                "rolcreaterole",
                "rolreplication",
                "rolbypassrls",
            )
        ):
            fail(role, "role", "elevated_or_unknown_role_flags")
        if flags.get("rolcanlogin") is not True:
            fail(role, "role", "login_not_enabled")
        if profile["direct_memberships"]:
            fail(role, "role", "membership_requires_explicit_review")
        schemas = {item["nspname"]: item for item in profile["schemas"]}
        required = SCHEMAS if role == "ketrika_app" else ("gold",)
        for schema in required:
            if schemas.get(schema, {}).get("usage") is not True:
                fail(role, schema, "missing_schema_usage")
        for schema, rights in schemas.items():
            if rights["create"] is not False:
                fail(role, schema, "schema_create_privilege")
            if role == "copilot_ro" and schema != "gold" and rights["usage"] is not False:
                fail(role, schema, "outside_gold_schema_usage")
        objects = {item["schema"] + "." + item["name"]: item for item in profile["objects"]}
        gold = [item for item in objects.values() if item["schema"] == "gold"]
        if not gold:
            fail(role, "gold", "missing_gold_objects")
        for name, rights in objects.items():
            if rights["schema"] == "gold":
                if rights["select"] is not True:
                    fail(role, name, "missing_gold_select")
                if any(rights[permission.lower()] is not False for permission in WRITES):
                    fail(role, name, "gold_write_privilege")
            elif role == "copilot_ro" and any(
                rights[permission.lower()] is not False for permission in ("SELECT", *WRITES)
            ):
                fail(role, name, "outside_gold_object_privilege")
        if role == "copilot_ro":
            for sequence in profile["sequences"]:
                if any(sequence[key] is not False for key in ("usage", "select", "update")):
                    fail(role, sequence["schema"] + "." + sequence["name"], "sequence_privilege")
            settings = profile["statement_timeout_settings"]
            # Effective per-role/per-database override takes precedence over role default.
            setting = settings[-1]["setting"] if settings else None
            if setting not in {
                "statement_timeout=5s",
                "statement_timeout=5000",
                "statement_timeout=5000ms",
            }:
                fail(role, "statement_timeout", "expected_explicit_5s_role_setting")
        else:
            expected = {
                "meta.source_record": ("select", "insert"),
                "obs.quarantine_ledger": ("select",),
                "auth.token_revocation": ("select", "insert"),
            }
            expected.update({"obs." + name: ("select", "insert", "update") for name in OBS})
            for name, permissions in expected.items():
                rights = objects.get(name, {})
                for permission in permissions:
                    if rights.get(permission) is not True:
                        fail(role, name, "missing_" + permission)
            revocation = objects.get("auth.token_revocation", {})
            if any(revocation.get(key) is not False for key in ("update", "delete", "truncate")):
                fail(role, "auth.token_revocation", "revocation_mutation_privilege")
    return {
        "passed": not failures,
        "failures": failures,
        "scope": "effective metadata privileges only; no login, workflow or deployment qualification",
    }


def audit(url: str) -> dict[str, Any]:
    engine = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout='5s'"))
            snapshot = collect(connection)
            snapshot["assessment"] = evaluate(snapshot)
            return snapshot
    finally:
        engine.dispose()


def main() -> int:
    try:
        report = audit(os.environ["DATABASE_URL"])
    except Exception as exc:
        # Exception strings/DSNs/SQL parameters can contain credentials: never export them.
        print(
            json.dumps({"passed": False, "error_type": type(exc).__name__, "scope": "audit_failed"})
        )
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["assessment"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
