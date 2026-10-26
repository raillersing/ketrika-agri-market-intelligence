"""Exercise real restore shell processes with fake local tools and no database/network."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from ketrika.ops.backup_restore import (
    ActiveDatabaseOverwriteBlockedError,
    BackupVerificationUnavailableError,
    CorruptedBackupError,
    MissingBackupError,
    enforce_active_target_guard,
    generate_backup_manifest,
    validate_restored_clone_consistency,
    verify_backup_integrity,
)


@pytest.fixture
def archive(tmp_path):
    path = tmp_path / "fixture.dump"
    path.write_bytes(b"synthetic archive: never a real readability proof")
    generate_backup_manifest(path, verify_archive=False, database_name="fixture_source")
    return path


def test_missing_companions_and_tool_cannot_be_verified(archive):
    with patch("shutil.which", return_value=None):
        with pytest.raises(BackupVerificationUnavailableError):
            verify_backup_integrity(archive)
    archive.with_suffix(".meta.json").unlink()
    with pytest.raises(MissingBackupError, match="manifest"):
        verify_backup_integrity(archive, check_pg_restore=False)
    archive.with_name(archive.name + ".sha256").unlink()
    with pytest.raises(MissingBackupError, match="SHA-256"):
        verify_backup_integrity(archive, check_pg_restore=False)


@pytest.mark.parametrize(
    "field,value",
    [
        ("dump_filename", "another.dump"),
        ("dump_size_bytes", 1),
        ("database_name", ""),
        ("timestamp_utc", "2026-10-26T10:00:00"),
        ("timestamp_utc", "2026-10-26T10:00:00+03:00"),
    ],
)
def test_mismatched_manifest_metadata_is_refused(archive, field, value):
    manifest = archive.with_suffix(".meta.json")
    data = json.loads(manifest.read_text())
    data[field] = value
    manifest.write_text(json.dumps(data))
    with pytest.raises(CorruptedBackupError):
        verify_backup_integrity(archive, check_pg_restore=False)


def test_source_sql_errors_never_become_zero_counts(archive):
    session = MagicMock()
    session.execute.side_effect = OperationalError("test", {}, Exception("private detail"))
    with pytest.raises(OperationalError):
        generate_backup_manifest(archive, session=session, verify_archive=False)
    result = validate_restored_clone_consistency(session, {"meta.source_record": 0})
    assert result["all_matched"] is False
    assert result["details"]["meta.source_record"]["restored"] == -1
    assert "private detail" not in json.dumps(result)
    assert validate_restored_clone_consistency(session, {})["all_matched"] is False
    with pytest.raises(ValueError):
        validate_restored_clone_consistency(
            session, {"meta.source_record; DROP DATABASE postgres": 0}
        )


@pytest.mark.parametrize(
    "name,confirmed,override",
    [
        ("production", "production", True),
        ("arbitrary_live", "arbitrary_live", False),
        ("ketrika_restore_x", None, False),
        ("ketrika_restore_x", "ketrika_restore_y", False),
        ("ketrika_restore_x", "ketrika_restore_x", True),
        ("ketrika_restore_" + "x" * 60, "ketrika_restore_" + "x" * 60, False),
        ("ketrika_restore_x'", "ketrika_restore_x'", False),
    ],
)
def test_clone_confirmation_has_no_override(name, confirmed, override):
    with pytest.raises(ActiveDatabaseOverwriteBlockedError):
        enforce_active_target_guard(name, allow_overwrite=override, confirmed_database=confirmed)


@pytest.fixture
def shell_fixture(tmp_path, archive):
    tools = tmp_path / "tools"
    tools.mkdir()
    log = tmp_path / "tools.jsonl"
    stub = (
        "#!"
        + sys.executable
        + "\n"
        + """
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
sql = sys.stdin.read() if name == 'psql' else ''
with open(os.environ['RESTORE_TOOL_LOG'], 'a') as log:
    log.write(json.dumps({'tool':name, 'args':sys.argv[1:], 'sql':sql})+'\\n')
mode = os.environ.get('RESTORE_TEST_MODE', '')
if name == 'psql':
    if 'WITH m AS' in sql: print('fixture_source' if mode != 'bad_manifest' else '')
    elif 'pg_database' in sql: print('t' if mode == 'exists' else 'f')
    elif 'current_database' in sql: print('t')
    elif mode == 'sql_error': sys.exit(1)
    else: print('meta.source_record|0')
if name == 'pg_restore':
    if '--list' in sys.argv and mode == 'catalog_error': sys.exit(1)
    if '--list' not in sys.argv and mode == 'restore_error': sys.exit(1)
"""
    )
    for name in ("psql", "createdb", "pg_restore"):
        tool = tools / name
        tool.write_text(stub)
        tool.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": str(tools) + os.pathsep + os.environ["PATH"],
        "PGDATABASE": "ketrika_restore_unit",
        "RESTORE_CONFIRM_DATABASE": "ketrika_restore_unit",
        "RESTORE_TOOL_LOG": str(log),
        "ALLOW_ACTIVE_DB_OVERWRITE": "0",
    }
    root = Path("/workspace")
    if not (root / "deploy/restore.sh").exists():
        root = Path(__file__).resolve().parents[3]

    def run(mode="", overrides=None):
        result = subprocess.run(
            ["bash", str(root / "deploy/restore.sh"), str(archive)],
            env={**environment, "RESTORE_TEST_MODE": mode, **(overrides or {})},
            capture_output=True,
            text=True,
            timeout=20,
        )
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls

    return run


@pytest.mark.parametrize("mode", ["exists", "bad_manifest", "catalog_error"])
def test_shell_refuses_before_creating_any_database(shell_fixture, mode):
    result, calls = shell_fixture(mode)
    assert result.returncode != 0
    assert "[SUCCESS]" not in result.stdout
    assert not any(call["tool"] == "createdb" for call in calls)
    assert not any(call["tool"] == "pg_restore" and "--list" not in call["args"] for call in calls)


@pytest.mark.parametrize("mode", ["restore_error", "sql_error"])
def test_shell_never_accepts_exit_one_as_success(shell_fixture, mode):
    result, calls = shell_fixture(mode)
    assert result.returncode == 1
    assert "[SUCCESS]" not in result.stdout
    restore = next(
        call for call in calls if call["tool"] == "pg_restore" and "--list" not in call["args"]
    )
    assert "--single-transaction" in restore["args"] and "--exit-on-error" in restore["args"]
    assert "--clean" not in restore["args"]
    assert all("pg_terminate_backend" not in call["sql"] for call in calls)


@pytest.mark.parametrize(
    "overrides",
    [
        {"RESTORE_CONFIRM_DATABASE": ""},
        {"PGDATABASE": "other_active_database"},
        {"ALLOW_ACTIVE_DB_OVERWRITE": "1"},
        {"PGDATABASE": "ketrika_restore_x';"},
    ],
)
def test_shell_target_guards_make_no_database_calls(shell_fixture, overrides):
    result, calls = shell_fixture(overrides=overrides)
    assert result.returncode == 2
    assert calls == []


@pytest.mark.parametrize("confirmed", [False, True])
def test_linux_entrypoint_never_uses_active_compose_restore(tmp_path, archive, confirmed):
    tools = tmp_path / "entry-tools"
    tools.mkdir()
    log = tmp_path / "docker.jsonl"
    docker = tools / "docker"
    docker.write_text(
        "#!"
        + sys.executable
        + "\n"
        + """
import json, os, sys
with open(os.environ['DOCKER_TEST_LOG'], 'a') as log:
    log.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[1:3] == ['network','inspect']:
    print('true|restore-qualification')
    raise SystemExit(0)
raise SystemExit(17)
"""
    )
    docker.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": str(tools) + os.pathsep + os.environ["PATH"],
        "DOCKER_TEST_LOG": str(log),
        "PGHOST": "isolated-db",
        "PGUSER": "test",
        "PGDATABASE": "ketrika_restore_unit",
        "KETRIKA_RESTORE_NETWORK": "owned-test-network",
        "RESTORE_CONFIRM_DATABASE": "ketrika_restore_unit" if confirmed else "",
    }
    root = Path("/workspace")
    if not (root / "scripts/dev.sh").exists():
        root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        ["bash", str(root / "scripts/dev.sh"), "restore", str(archive)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    if not confirmed:
        assert result.returncode == 2 and calls == []
    else:
        assert result.returncode == 17
        assert calls[0][:2] == ["network", "inspect"]
        assert calls[1][0] == "run"
        assert "/workspace/deploy/restore.sh" in calls[1]
        assert any("target=/backup,readonly" in arg for arg in calls[1])
        assert not any("compose" in call for call in calls)
    assert "Restoration complete" not in result.stdout
