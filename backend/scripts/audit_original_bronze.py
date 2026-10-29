"""Read-only original-bucket diagnostic; no export/rebuild or market qualification."""

import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from ketrika.core.bronze import BronzeStore
from ketrika.core.settings import get_settings

MAX_OBJECTS = 10_000
MAX_BYTES = 256 * 1024 * 1024


def inventory(client: Any, bucket: str) -> list[dict[str, Any]]:
    """Retain version identity, including delete markers; never use ETag as SHA."""
    rows: list[dict[str, Any]] = []
    for page in client.get_paginator("list_object_versions").paginate(Bucket=bucket):
        for category in ("Versions", "DeleteMarkers"):
            for item in page.get(category, []):
                rows.append(
                    {
                        "key": item["Key"],
                        "version_id": item["VersionId"],
                        "latest": item["IsLatest"],
                        "modified": item["LastModified"].isoformat(),
                        "size_bytes": item.get("Size"),
                        "delete_marker": category == "DeleteMarkers",
                    }
                )
                if len(rows) > MAX_OBJECTS:
                    raise ValueError("inventory_object_budget_exceeded")
    return sorted(rows, key=lambda row: (row["key"], row["version_id"]))


def main() -> int:
    started = datetime.now(UTC).isoformat()
    copy_root = None
    if os.environ.get("KETRIKA_AUDIT_COPY"):
        copy_root = Path(os.environ["KETRIKA_AUDIT_COPY"])
        if not copy_root.is_absolute() or copy_root.is_symlink():
            raise ValueError("copy_destination_must_be_new_and_absolute")
        copy_root.mkdir(exist_ok=False)
    store = BronzeStore()
    client = store.client
    before = inventory(client, store.bucket)
    total = sum(row["size_bytes"] or 0 for row in before)
    if total > MAX_BYTES:
        raise ValueError("inventory_byte_budget_exceeded")
    objects = []
    for row in before:
        if row["delete_marker"]:
            continue
        response = client.get_object(
            Bucket=store.bucket, Key=row["key"], VersionId=row["version_id"]
        )
        digest = hashlib.sha256()
        size = 0
        payload = bytearray()
        try:
            for chunk in response["Body"].iter_chunks(chunk_size=1024 * 1024):
                size += len(chunk)
                if size > row["size_bytes"]:
                    raise ValueError("object_size_changed_during_read")
                digest.update(chunk)
                if copy_root is not None:
                    payload.extend(chunk)
        finally:
            response["Body"].close()
        name = row["key"].rsplit("/", 1)[-1]
        addressed = re.fullmatch(r"([0-9a-f]{64})\.[^.]+", name)
        objects.append(
            dict(
                row,
                sha256=digest.hexdigest(),
                size_verified=size == row["size_bytes"],
                address_verified=(digest.hexdigest() == addressed[1] if addressed else None),
            )
        )
        if copy_root is not None:
            destination = copy_root / (digest.hexdigest() + ".blob")
            try:
                with destination.open("xb") as stream:
                    stream.write(payload)
            except FileExistsError:
                if destination.read_bytes() != payload:
                    raise ValueError("immutable_copy_collision") from None
    engine = create_engine(get_settings().database_url)
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            ledger = [
                dict(row)
                for row in connection.execute(
                    text(
                        "SELECT source_id, object_key, content_sha256 "
                        "FROM meta.source_record ORDER BY source_id, object_key, content_sha256"
                    )
                ).mappings()
            ]
    finally:
        engine.dispose()
    current = {row["key"]: row for row in objects if row["latest"]}
    mismatches = [
        row
        for row in ledger
        if row["object_key"] not in current
        or current[row["object_key"]]["sha256"] != row["content_sha256"]
    ]
    after = inventory(client, store.bucket)
    unchanged = before == after
    invalid = [
        row for row in objects if not row["size_verified"] or row["address_verified"] is False
    ]
    passed = unchanged and not invalid and not mismatches
    report = {
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "scope": "original local S3 bucket read-only, not independent archival attestation",
        "audit_tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "audit_tool_base_commit": os.environ.get("KETRIKA_AUDIT_TOOL_BASE_COMMIT", "unknown"),
        "source_application_commit": "unverified",
        "bucket": store.bucket,
        "versioning": client.get_bucket_versioning(Bucket=store.bucket).get("Status", "absent"),
        "inventory_before": before,
        "inventory_after": after,
        "objects": objects,
        "bytes_read": total,
        "ledger_count": len(ledger),
        "ledger_mismatches": mismatches,
        "invalid_objects": invalid,
        "unchanged_during_audit": unchanged,
        "integrity_passed": passed,
        "historical_immutability_qualified": False,
        "copy_destination": str(copy_root) if copy_root is not None else None,
        "copied_versions": len(objects) if copy_root is not None else 0,
        "revisions_qualified": False,
        "scientific_recompute_qualified": False,
    }
    with Path(sys.argv[1]).open("x") as output:
        json.dump(report, output, sort_keys=True, indent=2)
    sys.stdout.write(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k
                not in {
                    "inventory_before",
                    "inventory_after",
                    "objects",
                    "ledger_mismatches",
                    "invalid_objects",
                }
            }
        )
        + "\n"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
