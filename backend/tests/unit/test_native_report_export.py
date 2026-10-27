"""CI exports must preserve bytes and exclude session or ambient files."""

from pathlib import Path

import pytest

from ketrika.core.qualification import QualificationSafetyError
from ketrika.core.qualification_reports import export_native_reports


def test_browser_export_preserves_failed_receipt_and_excludes_trace(tmp_path: Path) -> None:
    source = tmp_path / "reports"
    run = source / "qa-browser-results" / ("a" * 32)
    run.mkdir(parents=True)
    original = b'{"passed":false,"reason":"synthetic failure"}\n'
    (run / "receipt.json").write_bytes(original)
    (run / "trace.zip").write_bytes(b"private browser trace")
    (source / ".env").write_text("PRIVATE=not-an-export")
    destination = tmp_path / "export"
    result = export_native_reports("browser", source, destination)
    assert result["files"] == 1
    assert (destination / ("a" * 32) / "receipt.json").read_bytes() == original
    assert not list(destination.rglob("*.zip"))
    assert not list(destination.rglob(".env"))
    with pytest.raises(QualificationSafetyError, match="destination_exists"):
        export_native_reports("browser", source, destination)


def test_backend_export_never_treats_missing_reports_as_acceptance(tmp_path: Path) -> None:
    source = tmp_path / "reports"
    source.mkdir()
    (source / "qa-tests.xml").write_bytes(b"<testsuites/>\n")
    (source / "other.json").write_text("not allowed")
    result = export_native_reports("backend", source, tmp_path / "export")
    assert result == {"role": "backend", "files": 1, "scope": "original bytes, not qualification"}
    assert not (tmp_path / "export" / "other.json").exists()


def test_frontend_export_uses_only_known_execution_files(tmp_path: Path) -> None:
    source = tmp_path / "reports"
    base = source / ".qa-results"
    run = base / "12345678-1234-1234-1234-123456789abc"
    run.mkdir(parents=True)
    (base / "latest.json").write_text('{"execution_id":"test"}')
    (run / "receipt.json").write_text('{"passed":false}')
    (run / "vitest.json").write_text('{"success":false}')
    (run / "session.json").write_text("not allowed")
    result = export_native_reports("frontend", source, tmp_path / "export")
    assert result["files"] == 3
    assert not list((tmp_path / "export").rglob("session.json"))


def test_export_rejects_symlinked_report(tmp_path: Path) -> None:
    source = tmp_path / "reports"
    source.mkdir()
    secret = tmp_path / "ambient"
    secret.write_text("not an original report")
    (source / "qa-tests.xml").symlink_to(secret)
    with pytest.raises(QualificationSafetyError, match="symlink_forbidden"):
        export_native_reports("backend", source, tmp_path / "export")


def test_export_rejects_symlinked_execution(tmp_path: Path) -> None:
    source = tmp_path / "reports"
    base = source / "qa-browser-results"
    base.mkdir(parents=True)
    (base / ("a" * 32)).symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(QualificationSafetyError, match="symlink_forbidden"):
        export_native_reports("browser", source, tmp_path / "export")


def test_export_rejects_unknown_role_and_nested_destination(tmp_path: Path) -> None:
    source = tmp_path / "reports"
    source.mkdir()
    with pytest.raises(QualificationSafetyError, match="role_unknown"):
        export_native_reports("arbitrary", source, tmp_path / "export")
    with pytest.raises(QualificationSafetyError, match="inside_source"):
        export_native_reports("backend", source, source / "nested")


def test_export_bounds_report_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "reports"
    source.mkdir()
    (source / "qa-tests.xml").write_bytes(b"12345")
    monkeypatch.setattr("ketrika.core.qualification_reports.MAX_REPORT_BYTES", 4)
    with pytest.raises(QualificationSafetyError, match="too_large"):
        export_native_reports("backend", source, tmp_path / "export")
