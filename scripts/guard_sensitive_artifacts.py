"""Fail CI when a commit introduces likely private data or backup artifacts.

This checks added/modified paths, not file contents. It deliberately does not
delete or classify the historical database dump already committed on main.
Use a separate secret scanner and a private review to assess actual exposure.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import PurePosixPath

DENIED_SUFFIXES = (
    ".dump", ".pgdump", ".backup", ".bak", ".sqlite", ".sqlite3",
    ".p12", ".pfx", ".pem", ".key",
)
DENIED_NAMES = {"id_rsa", "id_ed25519", "credentials.json", "service-account.json"}


def is_sensitive_artifact(path: str) -> bool:
    """Reject known private file patterns irrespective of Git ignore rules."""
    p = PurePosixPath(path.replace("\\", "/"))
    name = p.name.lower()
    if name in DENIED_NAMES or name.endswith(DENIED_SUFFIXES):
        return True
    if name == ".env" or name.startswith(".env."):
        return not (name == ".env.example" or name.endswith(".example"))
    return False


def added_or_modified_paths(base: str) -> list[str]:
    """Inspect all additions, copies, modifications and renames in this CI diff."""
    command = [
        "git", "diff", "--no-renames", "--name-only", "-z",
        "--diff-filter=ACMR", base, "HEAD",
    ]
    output = subprocess.check_output(command)
    return [name.decode("utf-8", "surrogateescape") for name in output.split(b"\0") if name]


def self_test() -> None:
    blocked = [
        "backups/production.dump", "private/pg.backup", "postgres.pgdump",
        "db.sqlite", "db.sqlite3", "certificate.pem", "ssh/id_rsa",
        ".env", ".env.production", "subdir/.env.staging",
        "credentials.json",
    ]
    allowed = [
        "README.md", "backend/alembic/versions/0001_initial.sql",
        ".env.example", ".env.production.example",
        "docs/plan/DATA_PRODUCT_IMPROVEMENT_PLAN.md",
        "backend/tests/fixtures/prices.csv",
    ]
    assert all(is_sensitive_artifact(path) for path in blocked)
    assert all(not is_sensitive_artifact(path) for path in allowed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD^", help="Git revision to diff against HEAD")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("Sensitive artifact path guard self-test: PASS")
        return 0

    try:
        changes = added_or_modified_paths(args.base)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"Cannot inspect commit diff; refusing unverified commit: {type(exc).__name__}", file=sys.stderr)
        return 2

    denied = [name for name in changes if is_sensitive_artifact(name)]
    if denied:
        print("BLOCKED: sensitive backup/credential file paths introduced or modified:", file=sys.stderr)
        for path in denied:
            print(f" - {path}", file=sys.stderr)
        print("Store backups privately; never add credentials to Git.", file=sys.stderr)
        return 1

    print(f"Sensitive artifact path guard: PASS ({len(changes)} changed paths inspected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
