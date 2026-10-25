"""Counterexamples: isolated auth module, intercepted SMTP, temporary fake dump."""

import json
import subprocess
import sys
import tempfile
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4


def main() -> None:
    # Bypass ASGI package initialization, not auth validation; unchanged auth.py is loaded.
    api_package = types.ModuleType("ketrika.api")
    api_package.__dict__["__path__"] = ["/workspace/backend/src/ketrika/api"]
    sys.modules["ketrika.api"] = api_package
    from ketrika.alerts.notifier import send_pipeline_failure_email, send_smtp_alert
    from ketrika.api.auth import create_access_token, decode_access_token, revoke_token
    from ketrika.core.models.db import Alert, UserAccount
    from ketrika.core.settings import Settings
    from ketrika.ops.backup_restore import verify_backup_integrity

    result: dict[str, Any] = {
        "scope": "isolated Python process; no actual SMTP, database or restore"
    }
    settings = Settings(smtp_host="smtp.invalid", external_send_enabled=0)
    alert = Alert(
        alert_id=uuid4(),
        severity="low",
        title="audit",
        rule_code="AUDIT",
        dedupe_key="audit",
        state="open",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        evidence={},
    )
    with patch(
        "ketrika.alerts.notifier.smtplib.SMTP",
        side_effect=RuntimeError("audit_transport_intercepted"),
    ) as smtp:
        send_smtp_alert(alert, settings=settings)
        result["smtp_alert_transport_attempted_with_gate_off"] = smtp.called
    with patch(
        "ketrika.alerts.notifier.smtplib.SMTP",
        side_effect=RuntimeError("audit_transport_intercepted"),
    ) as smtp:
        send_pipeline_failure_email("audit", "audit-run", "audit", settings=settings)
        result["smtp_failure_transport_attempted_with_gate_off"] = smtp.called
    with tempfile.TemporaryDirectory() as folder:
        dump = Path(folder) / "not-a-dump.dump"
        dump.write_bytes(b"this is not a PostgreSQL dump")
        with patch("ketrika.ops.backup_restore.shutil.which", return_value=None):
            result["invalid_dump_without_manifest_or_tool_accepted"] = verify_backup_integrity(
                dump
            )[0]
    user = UserAccount(
        user_id=uuid4(), email="audit@example.invalid", role="client", disabled=False
    )
    token = create_access_token(user)
    revoke_token(token)
    try:
        decode_access_token(token)
        result["revoked_token_accepted_same_process"] = True
    except Exception:
        result["revoked_token_accepted_same_process"] = False
    # Token goes only over stdin, never to a receipt or a command line.
    child_code = "import sys,types; p=types.ModuleType('ketrika.api'); p.__path__=['/workspace/backend/src/ketrika/api']; sys.modules['ketrika.api']=p; from ketrika.api.auth import decode_access_token; decode_access_token(sys.stdin.read()); print('accepted')"
    child = subprocess.run(
        [sys.executable, "-c", child_code],
        input=token,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    result["revoked_token_accepted_other_process"] = (
        child.returncode == 0 and child.stdout.strip() == "accepted"
    )
    Path(sys.argv[1]).write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
