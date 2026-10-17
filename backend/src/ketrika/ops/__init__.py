"""Ketrika Operations, Backup, Recovery, and Infrastructure Supervision (SPECS §25, R6.8)."""

from __future__ import annotations

from ketrika.ops.backup_restore import (
    ActiveDatabaseOverwriteBlockedError,
    BackupManifest,
    CorruptedBackupError,
    MissingBackupError,
    calculate_file_sha256,
    enforce_active_target_guard,
    generate_backup_manifest,
    validate_restored_clone_consistency,
    verify_backup_integrity,
)

__all__ = [
    "ActiveDatabaseOverwriteBlockedError",
    "BackupManifest",
    "CorruptedBackupError",
    "MissingBackupError",
    "calculate_file_sha256",
    "enforce_active_target_guard",
    "generate_backup_manifest",
    "validate_restored_clone_consistency",
    "verify_backup_integrity",
]
