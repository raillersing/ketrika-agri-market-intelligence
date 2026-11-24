"""Native replay receipt tests; archived evidence remains historical, not current."""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ketrika.core.external_replay import (
    PRICE,
    _claims,
    _native,
    _native_report,
    _typed,
)
from ketrika.core.qualification import QualificationSafetyError

EVIDENCE = Path("/workspace/docs/evidence")


@pytest.fixture(scope="module")
def historical():
    files = (
        "R0.8_WB_ARCHIVE_20261104_REAL_REPLAY.json.gz",
        "R0.8_WB_ARCHIVE_20261104_FALSE_PARSER.json.gz",
    )
    documents = []
    for name in files:
        with gzip.open(EVIDENCE / name, "rt") as stream:
            documents.append(json.load(stream))
    return documents


def test_historical_native_manifest_and_counterproof(historical):
    positive, negative = historical
    assert _native(positive, negative=False)["content_identical"] is True
    assert _native(negative, negative=True)["content_identical"] is False
    assert len(_claims(positive["before"])) == 163


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("uid", 0, "external_replay_uid"),
        ("database", "ketrika", "external_replay_db"),
        ("network_before", {"interfaces": ["lo", "eth0"]}, "external_replay_network"),
        ("replay_passed", False, "external_replay_result"),
    ],
)
def test_reject_unconfined_native_receipt(historical, field, value, reason):
    positive = dict(historical[0], **{field: value})
    with pytest.raises(QualificationSafetyError, match=reason):
        _native(positive, negative=False)


def test_reject_forged_counterproof(historical):
    negative = dict(historical[1], counterproof_passed=False)
    with pytest.raises(QualificationSafetyError, match="external_counterproof_missing"):
        _native(negative, negative=True)


def test_reject_wrong_observation_identity(historical):
    snapshot = copy.deepcopy(historical[0]["before"])
    snapshot["tables"][PRICE]["rows"][0]["observation_id"][2] = "0" * 64
    with pytest.raises(QualificationSafetyError, match="external_observation_identity"):
        _claims(snapshot)


def test_typed_roundtrip():
    assert _typed(["object", [["x", ["array", [["int", "1"], ["null"]]]]]]) == {
        "x": [1, None]
    }
    with pytest.raises(QualificationSafetyError, match="external_unknown_manifest_type"):
        _typed(["unknown", 0])


def test_native_receipt_bound_to_exact_bytes_and_identity(tmp_path):
    captured = datetime.now(UTC).isoformat()
    document = {
        "commit": "a" * 40,
        "source_fingerprint": "b" * 64,
        "packet_sha256": "c" * 64,
        "environment": {"producer": "test"},
        "captured_at": captured,
    }
    native = {
        "commit": document["commit"],
        "source_fingerprint": document["source_fingerprint"],
        "packet_sha256": document["packet_sha256"],
        "producer_environment": document["environment"],
        "role": "positive",
        "captured_at": captured,
    }
    path = tmp_path / "positive.json"

    def write():
        raw = json.dumps(native).encode()
        path.write_bytes(raw)
        document["positive"] = {
            "path": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    write()
    assert _native_report(tmp_path, document, "positive") == native
    path.write_bytes(b"{}")
    with pytest.raises(QualificationSafetyError, match="external_native_hash"):
        _native_report(tmp_path, document, "positive")
    native["commit"] = "d" * 40
    write()
    with pytest.raises(QualificationSafetyError, match="external_native_binding"):
        _native_report(tmp_path, document, "positive")
