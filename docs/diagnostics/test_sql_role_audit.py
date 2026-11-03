"""Dedicated diagnostics tests; no application fixtures or product qualification."""

from __future__ import annotations

import copy
import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, text

from sql_role_audit import OBS, ROLES, SCHEMAS, WRITES, audit, collect, evaluate, main


def valid_snapshot():
    result = {"roles": {}}
    for role in ROLES:
        objects = []
        for schema, name in [
            ("gold", "price_monthly"),
            ("meta", "source_record"),
            ("auth", "token_revocation"),
            ("obs", "quarantine_ledger"),
            *(("obs", name) for name in OBS),
        ]:
            rights = {key.lower(): False for key in ("SELECT", *WRITES)}
            rights["select"] = role == "ketrika_app" or schema == "gold"
            if role == "ketrika_app" and schema != "gold":
                rights["insert"] = True
                rights["update"] = name not in ("token_revocation", "source_record")
            objects.append({"schema": schema, "name": name, "kind": "r", **rights})
        result["roles"][role] = {
            "flags": {
                "rolsuper": False,
                "rolcreatedb": False,
                "rolcreaterole": False,
                "rolreplication": False,
                "rolbypassrls": False,
                "rolcanlogin": True,
            },
            "schemas": [
                {"nspname": name, "usage": role == "ketrika_app" or name == "gold", "create": False}
                for name in SCHEMAS
            ],
            "objects": objects,
            "sequences": [],
            "direct_memberships": [],
            "statement_timeout_settings": (
                [{"database_oid": 0, "setting": "statement_timeout=5s"}]
                if role == "copilot_ro"
                else []
            ),
        }
    return result


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = valid_snapshot()

    def test_valid_does_not_mutate_input(self):
        before = copy.deepcopy(self.snapshot)
        self.assertTrue(evaluate(self.snapshot)["passed"])
        self.assertEqual(before, self.snapshot)

    def test_missing_roles_refuse(self):
        for role in ROLES:
            with self.subTest(role=role):
                snapshot = valid_snapshot()
                snapshot["roles"][role] = None
                self.assertFalse(evaluate(snapshot)["passed"])

    def test_historical_missing_usage_detected(self):
        app = self.snapshot["roles"]["ketrika_app"]
        for schema in app["schemas"]:
            schema["usage"] = schema["nspname"] == "gold"
        failures = evaluate(self.snapshot)["failures"]
        self.assertEqual({item["subject"] for item in failures}, set(SCHEMAS) - {"gold"})
        self.assertEqual({item["reason"] for item in failures}, {"missing_schema_usage"})

    def test_unknown_privileges_fail_closed(self):
        self.snapshot["roles"]["ketrika_app"]["schemas"][0]["usage"] = None
        self.assertFalse(evaluate(self.snapshot)["passed"])

    def test_elevated_roles_and_membership_refuse(self):
        for role in ROLES:
            for flag in (
                "rolsuper",
                "rolcreatedb",
                "rolcreaterole",
                "rolreplication",
                "rolbypassrls",
            ):
                with self.subTest(role=role, flag=flag):
                    snapshot = valid_snapshot()
                    snapshot["roles"][role]["flags"][flag] = True
                    self.assertFalse(evaluate(snapshot)["passed"])
            snapshot = valid_snapshot()
            snapshot["roles"][role]["direct_memberships"] = ["owner"]
            self.assertFalse(evaluate(snapshot)["passed"])

    def test_copilot_write_read_sequence_and_timeout_overrides_refuse(self):
        for permission in (
            "select",
            "insert",
            "update",
            "delete",
            "truncate",
            "references",
            "trigger",
        ):
            with self.subTest(permission=permission):
                snapshot = valid_snapshot()
                snapshot["roles"]["copilot_ro"]["objects"][1][permission] = True
                self.assertFalse(evaluate(snapshot)["passed"])
        self.snapshot["roles"]["copilot_ro"]["sequences"] = [
            {"schema": "gold", "name": "seq", "select": False, "usage": True, "update": False}
        ]
        self.assertFalse(evaluate(self.snapshot)["passed"])
        snapshot = valid_snapshot()
        snapshot["roles"]["copilot_ro"]["statement_timeout_settings"].append(
            {"database_oid": 123, "setting": "statement_timeout=0"}
        )
        self.assertFalse(evaluate(snapshot)["passed"])

    def test_missing_tables_columns_and_gold_refuse(self):
        for role in ROLES:
            snapshot = valid_snapshot()
            snapshot["roles"][role]["objects"] = []
            self.assertFalse(evaluate(snapshot)["passed"])
        self.snapshot["roles"]["ketrika_app"]["objects"][2]["truncate"] = True
        self.assertFalse(evaluate(self.snapshot)["passed"])

    def test_cli_errors_do_not_export_credentials(self):
        with (
            patch.dict(os.environ, {"DATABASE_URL": "secret-url"}),
            patch("sql_role_audit.audit", side_effect=RuntimeError("PASSWORD=never-export")),
            patch("builtins.print") as output,
        ):
            self.assertEqual(main(), 2)
        self.assertNotIn("never-export", str(output.call_args))
        self.assertNotIn("secret-url", str(output.call_args))


class SqlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Explicit dedicated database only. No skip: absent SQL makes this suite red.
        url = os.environ["AUDIT_TEST_DATABASE_URL"]
        cls.engine = create_engine(url)
        if cls.engine.url.database != "ketrika_role_audit_20261029":
            raise ValueError("Dedicated audit test database required")
        with cls.engine.begin() as conn:
            for schema in SCHEMAS:
                conn.execute(text(f"CREATE SCHEMA {schema}"))
            conn.execute(text("CREATE ROLE ketrika_app LOGIN"))
            conn.execute(text("CREATE ROLE copilot_ro LOGIN"))
            conn.execute(text("ALTER ROLE copilot_ro SET statement_timeout='5s'"))
            for schema, name in [
                ("gold", "price_monthly"),
                ("meta", "source_record"),
                ("auth", "token_revocation"),
                ("obs", "quarantine_ledger"),
                *(("obs", name) for name in OBS),
            ]:
                conn.execute(text(f"CREATE TABLE {schema}.{name}(id integer)"))
                if schema == "gold":
                    conn.execute(text(f"GRANT SELECT ON {schema}.{name} TO ketrika_app,copilot_ro"))
                else:
                    conn.execute(
                        text(f"GRANT SELECT,INSERT,UPDATE ON {schema}.{name} TO ketrika_app")
                    )
            conn.execute(text("REVOKE UPDATE ON auth.token_revocation FROM ketrika_app"))
            conn.execute(
                text("GRANT USAGE ON SCHEMA auth,dq,gold,meta,ml,obs,ops,ref TO ketrika_app")
            )
            conn.execute(text("GRANT USAGE ON SCHEMA gold TO copilot_ro"))
        cls.url = url

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def test_actual_valid_catalog_and_readonly_transaction(self):
        report = audit(self.url)
        self.assertTrue(report["read_only"])
        self.assertTrue(report["assessment"]["passed"], report["assessment"])
        with self.engine.begin() as conn:
            with self.assertRaisesRegex(ValueError, "Read-only"):
                collect(conn)

    def test_actual_grants_inherited_public_and_historical_denial(self):
        # Mutate only this fresh fixture DB; restore ACLs in finally.
        with self.engine.begin() as conn:
            conn.execute(text("REVOKE USAGE ON SCHEMA obs FROM ketrika_app"))
            conn.execute(text("GRANT SELECT ON meta.source_record TO PUBLIC"))
        try:
            failures = audit(self.url)["assessment"]["failures"]
            self.assertIn(
                {"role": "ketrika_app", "subject": "obs", "reason": "missing_schema_usage"},
                failures,
            )
            self.assertIn(
                {
                    "role": "copilot_ro",
                    "subject": "meta.source_record",
                    "reason": "outside_gold_object_privilege",
                },
                failures,
            )
        finally:
            with self.engine.begin() as conn:
                conn.execute(text("GRANT USAGE ON SCHEMA obs TO ketrika_app"))
                conn.execute(text("REVOKE SELECT ON meta.source_record FROM PUBLIC"))


if __name__ == "__main__":
    unittest.main()
