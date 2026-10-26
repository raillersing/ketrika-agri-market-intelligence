"""Automated Backup and Isolated Restore Certification (SPECS §25, R6.8, ADR-102).

Provides deterministic backup manifest generation, SHA-256 integrity audit,
strict active target guard against accidental overwrites, and post-restoration
clone consistency validation.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session


class ActiveDatabaseOverwriteBlockedError(RuntimeError):
    """Raised when a restoration attempts to target an active/production database."""


class CorruptedBackupError(RuntimeError):
    """Raised when backup file checksum or structural integrity validation fails."""


class MissingBackupError(FileNotFoundError):
    """Raised when the specified backup file does not exist."""


class BackupVerificationUnavailableError(RuntimeError):
    """Required verification tooling is unavailable; no success may be reported."""


class BackupManifest(BaseModel):
    """Certified backup manifest capturing database snapshot metadata and integrity hashes."""

    backup_id: str
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    git_commit: str = "unknown"
    dump_filename: str
    dump_sha256: str
    dump_size_bytes: int
    database_name: str
    table_counts: dict[str, int] = Field(default_factory=dict)
    bronze_manifest_count: int = 0
    verified_readable: bool = False

    def to_json(self) -> str:
        """Serialize manifest to pretty-printed JSON."""
        return self.model_dump_json(indent=2)

    def save(self, destination_path: Path) -> None:
        """Write manifest JSON to disk."""
        destination_path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, manifest_path: Path) -> BackupManifest:
        """Load manifest from JSON file on disk."""
        if not manifest_path.exists():
            raise FileNotFoundError(f"Backup manifest not found: {manifest_path}")
        content = manifest_path.read_text(encoding="utf-8")
        return cls.model_validate_json(content)


def calculate_file_sha256(filepath: Path) -> str:
    """Compute SHA-256 checksum of a file in 64KB chunks."""
    if not filepath.exists():
        raise MissingBackupError(f"File not found: {filepath}")

    hasher = hashlib.sha256()
    with filepath.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_backup_manifest(
    dump_path: Path,
    session: Session | None = None,
    git_commit: str = "unknown",
    database_name: str = "ketrika",
    bronze_count: int = 0,
    verify_archive: bool = True,
) -> BackupManifest:
    """Generate and write companion .meta.json manifest for a database dump."""
    if not dump_path.exists():
        raise MissingBackupError(f"Cannot generate manifest for missing dump: {dump_path}")

    dump_sha256 = calculate_file_sha256(dump_path)
    dump_size = dump_path.stat().st_size
    if verify_archive:
        _verify_archive_catalog(dump_path)
    backup_id = dump_path.stem

    table_counts: dict[str, int] = {}
    if session is not None:
        target_tables = [
            "meta.source_record",
            "obs.price_observation",
            "ops.bulletin",
            "auth.user_account",
            "ops.alert",
        ]
        for tbl in target_tables:
            cnt = session.execute(text(f"SELECT count(*) FROM {tbl}")).scalar_one()
            table_counts[tbl] = int(cnt)

    manifest = BackupManifest(
        backup_id=backup_id,
        timestamp_utc=datetime.now(UTC).isoformat(),
        git_commit=git_commit,
        dump_filename=dump_path.name,
        dump_sha256=dump_sha256,
        dump_size_bytes=dump_size,
        database_name=database_name,
        table_counts=table_counts,
        bronze_manifest_count=bronze_count,
        verified_readable=verify_archive,
    )

    manifest_path = dump_path.with_suffix(".meta.json")
    manifest.save(manifest_path)
    dump_path.with_name(f"{dump_path.name}.sha256").write_text(
        f"{dump_sha256}  {dump_path.name}\n", encoding="utf-8"
    )
    return manifest


def _verify_archive_catalog(dump_path: Path) -> None:
    if shutil.which("pg_restore") is None:
        raise BackupVerificationUnavailableError(
            "pg_restore is required to verify archive readability"
        )
    try:
        result = subprocess.run(
            ["pg_restore", "--list", str(dump_path)], capture_output=True, check=False, timeout=30
        )
    except (subprocess.TimeoutExpired, OSError) as error:
        raise CorruptedBackupError("Archive catalog verification could not complete") from error
    if result.returncode != 0:
        raise CorruptedBackupError("pg_restore --list rejected the archive")


def verify_backup_integrity(
    dump_path: Path,
    manifest_path: Path | None = None,
    check_pg_restore: bool = True,
) -> tuple[bool, str]:
    """Verify cryptographic checksum and structural readability of a database dump.

    Raises:
        MissingBackupError: if dump or companion checksum file does not exist.
        CorruptedBackupError: if SHA-256 hash mismatch or pg_restore catalog unreadable.
    """
    if not dump_path.exists():
        raise MissingBackupError(f"Backup dump file does not exist: {dump_path}")

    actual_sha256 = calculate_file_sha256(dump_path)

    # Both independent companions are mandatory, including on the metadata-only path.
    sha_file = dump_path.with_name(f"{dump_path.name}.sha256")
    if not sha_file.is_file():
        raise MissingBackupError("Companion SHA-256 file is required")
    checksum = sha_file.read_text(encoding="utf-8").strip().split()
    if len(checksum) != 2 or re.fullmatch(r"[a-f0-9]{64}", checksum[0]) is None:
        raise CorruptedBackupError("Malformed SHA-256 companion")
    if checksum[0] != actual_sha256 or checksum[1].lstrip("*") != dump_path.name:
        raise CorruptedBackupError("Checksum mismatch or archive filename mismatch")

    # 2. Check manifest if specified or companion exists
    target_manifest = manifest_path or dump_path.with_suffix(".meta.json")
    if manifest_path is None and not target_manifest.is_file():
        target_manifest = dump_path.with_name(f"{dump_path.name}.meta.json")
    if not target_manifest.is_file():
        raise MissingBackupError("Companion JSON manifest is required")
    try:
        manifest = BackupManifest.load(target_manifest)
        timestamp = datetime.fromisoformat(manifest.timestamp_utc.replace("Z", "+00:00"))
    except ValueError as error:
        raise CorruptedBackupError("Malformed backup manifest") from error
    if actual_sha256 != manifest.dump_sha256:
        raise CorruptedBackupError("Manifest SHA-256 mismatch")
    if (
        manifest.dump_filename != dump_path.name
        or manifest.dump_size_bytes != dump_path.stat().st_size
        or not manifest.database_name.strip()
        or timestamp.tzinfo is None
        or timestamp.utcoffset() != UTC.utcoffset(timestamp)
    ):
        raise CorruptedBackupError("Manifest archive identity, size or UTC timestamp mismatch")

    if check_pg_restore:
        _verify_archive_catalog(dump_path)
        if not manifest.verified_readable:
            raise CorruptedBackupError("Manifest does not certify archive readability")
        return True, "Backup metadata and archive catalog verified successfully"
    return True, "Backup metadata verified successfully; archive readability NOT checked"


DEFAULT_PROTECTED_ACTIVE_DATABASES: list[str] = [
    "ketrika",
    "ketrika_prod",
    "ketrika_active",
    "production",
    "postgres",
]


def enforce_active_target_guard(
    target_database: str,
    active_database_names: list[str] | None = None,
    allow_overwrite: bool = False,
    confirmed_database: str | None = None,
) -> None:
    """Enforce strict refusal to restore into an active/production database.

    Raises:
        ActiveDatabaseOverwriteBlockedError: if target_database is in protected active names
        and allow_overwrite is False.
    """
    clean_target = target_database.strip().lower()
    protected = [
        name.strip().lower()
        for name in (active_database_names or DEFAULT_PROTECTED_ACTIVE_DATABASES)
    ]

    if clean_target in protected:
        raise ActiveDatabaseOverwriteBlockedError(
            f"Restoration refused: Target database '{target_database}' is an active production database. "
            "Restorations are strictly restricted to isolated clones (e.g., 'ketrika_clone', 'ketrika_restore_test') "
            "to guarantee zero destruction of live operational data (R6.8, ADR-102)."
        )
    if (
        allow_overwrite
        or re.fullmatch(r"ketrika_restore_[a-z0-9_]+", target_database) is None
        or len(target_database) > 63
        or confirmed_database != target_database
    ):
        raise ActiveDatabaseOverwriteBlockedError(
            "Restoration requires an exactly confirmed fresh ketrika_restore_* target; overwrite is forbidden"
        )


def validate_restored_clone_consistency(
    session: Session,
    expected_counts: dict[str, int],
) -> dict[str, Any]:
    """Validate that restored clone database tables match expected record counts."""
    results: dict[str, Any] = {}
    all_matched = bool(expected_counts)

    for table_name, expected_cnt in expected_counts.items():
        if re.fullmatch(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*", table_name) is None:
            raise ValueError("Invalid schema-qualified table name")
        if expected_cnt < 0:
            raise ValueError("Expected table count cannot be negative")
        try:
            actual_cnt = session.execute(text(f"SELECT count(*) FROM {table_name}")).scalar()
            actual_int = int(actual_cnt) if actual_cnt is not None else 0
            matched = actual_int == expected_cnt
            results[table_name] = {
                "expected": expected_cnt,
                "restored": actual_int,
                "matches": matched,
            }
            if not matched:
                all_matched = False
        except Exception as exc:
            results[table_name] = {
                "expected": expected_cnt,
                "restored": -1,
                "matches": False,
                "error": type(exc).__name__,
            }
            all_matched = False

    return {
        "all_matched": all_matched,
        "details": results,
    }
