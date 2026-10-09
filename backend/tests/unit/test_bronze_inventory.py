"""Read-only inventory retains every object version and reports no content."""

import io
import json
import runpy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def inventory(monkeypatch, content=b"private body", failure=False):
    client = MagicMock()
    client.get_paginator.return_value.paginate.return_value = [
        {
            "Versions": [{"Key": "hidden/key", "VersionId": "v1", "IsLatest": True}],
            "DeleteMarkers": [{"Key": "hidden/deleted", "VersionId": "v0", "IsLatest": True}],
        }
    ]
    body = io.BytesIO(content)
    if failure:
        client.get_object.side_effect = RuntimeError("inaccessible version")
    else:
        client.get_object.return_value = {"Body": body}
    monkeypatch.setattr("ketrika.core.bronze.get_s3_client", lambda: client)
    monkeypatch.setattr(
        "ketrika.core.settings.get_settings", lambda: SimpleNamespace(s3_bucket_bronze="fixture")
    )
    code = runpy.run_path("/workspace/scripts/bronze-fingerprint-readonly.py")
    return client, body, code["main"]


def test_inventory_is_read_only_and_does_not_emit_payload(monkeypatch, capsys):
    client, body, main = inventory(monkeypatch)
    main()
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["version_count"] == result["current_objects"] == 1
    assert result["delete_markers"] == 1
    assert result["total_version_bytes"] == len(b"private body")
    assert len(result["sha256"]) == 64
    assert "private" not in output and "hidden" not in output
    assert body.closed
    assert {call[0] for call in client.method_calls} == {"get_paginator", "get_object"}


def test_unreadable_version_cannot_produce_success(monkeypatch, capsys):
    _, _, main = inventory(monkeypatch, failure=True)
    with pytest.raises(RuntimeError):
        main()
    assert capsys.readouterr().out == ""
