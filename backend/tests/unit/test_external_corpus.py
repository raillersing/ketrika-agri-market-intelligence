"""Unit tests for the external packet boundary, not authentic replay evidence."""

import hashlib
import json
from pathlib import Path

import pytest

from ketrika.core import external_corpus
from ketrika.core.qualification import QualificationSafetyError


@pytest.fixture
def packet(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout"
    reference = checkout / external_corpus.REFERENCE
    reference.parent.mkdir(parents=True)
    allowed = tmp_path / "mount"
    base = allowed / "corpus"
    source = base / "tests/fixtures/document.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"{}")
    receipt = base / "tests/acquisition.json"
    receipt.write_text("{}")
    manifest = {
        "version": 1,
        "entries": [
            {
                "path": "tests/fixtures/document.json",
                "size_bytes": 2,
                "sha256": hashlib.sha256(b"{}").hexdigest(),
                "origin": {
                    "kind": "official_acquisition",
                    "reference": "tests/acquisition.json",
                },
            }
        ],
    }
    reference.write_text(json.dumps(manifest))
    (base / external_corpus.MANIFEST).write_text(json.dumps(manifest))
    # Simulate only the mount and corpus-validator boundaries. This fixture is
    # not a real WB packet and is never a qualification receipt.
    monkeypatch.setattr(external_corpus, "_readonly", lambda path: None)
    monkeypatch.setattr(
        external_corpus,
        "validate_manifest",
        lambda base, manifest: {
            "counts": {"authentic": 6},
            "authentic_documents": ["a", "b", "c"],
            "authentic_annotations": 3,
            "verified_annotation_cells": 664,
        },
    )
    return checkout, allowed, base


def test_packet_identity_includes_receipt(packet):
    checkout, allowed, base = packet
    first = external_corpus.inspect_packet(checkout, allowed, base)
    assert first["rebuild_qualified"] is False
    assert first["human_reviewed"] is False
    assert len(first["packet_sha256"]) == 64
    assert first == external_corpus.inspect_packet(checkout, allowed, base)
    (base / "tests/acquisition.json").write_text('{"changed": true}')
    second = external_corpus.inspect_packet(checkout, allowed, base)
    assert first["packet_sha256"] != second["packet_sha256"]


def test_unpinned_manifest_rejected(packet):
    checkout, allowed, base = packet
    (base / external_corpus.MANIFEST).write_text('{"version": 2, "entries": []}')
    with pytest.raises(QualificationSafetyError, match="external_manifest_not_pinned"):
        external_corpus.inspect_packet(checkout, allowed, base)


@pytest.mark.parametrize("kind", ["file", "directory", "extra"])
def test_unexpected_entries_rejected(packet, kind):
    checkout, allowed, base = packet
    if kind == "file":
        path = base / "tests/fixtures/document.json"
        path.unlink()
        path.symlink_to(checkout / external_corpus.REFERENCE)
    elif kind == "directory":
        path = base / "tests/fixtures"
        path.rename(base / "other")
        path.symlink_to(base / "other", target_is_directory=True)
    else:
        (base / "tests/extra.json").write_text("{}")
    with pytest.raises(QualificationSafetyError):
        external_corpus.inspect_packet(checkout, allowed, base)


def test_outside_mount_rejected(packet):
    checkout, allowed, base = packet
    with pytest.raises(QualificationSafetyError, match="external_path_outside_allowed_root"):
        external_corpus.inspect_packet(checkout, checkout, base)
    with pytest.raises(QualificationSafetyError, match="external_path_not_absolute"):
        external_corpus.inspect_packet(checkout, allowed, Path("relative"))


def test_file_size_rejected(packet):
    checkout, allowed, base = packet
    (base / "tests/fixtures/document.json").write_bytes(b"too long")
    with pytest.raises(QualificationSafetyError, match="external_file_too_large"):
        external_corpus.inspect_packet(checkout, allowed, base)


def test_mutation_during_validation_rejected(packet, monkeypatch):
    checkout, allowed, base = packet
    original = external_corpus.validate_manifest

    def altered(root, manifest):
        result = original(root, manifest)
        (root / "tests/fixtures/document.json").write_bytes(b"[]")
        return result

    monkeypatch.setattr(external_corpus, "validate_manifest", altered)
    with pytest.raises(QualificationSafetyError, match="external_packet_changed"):
        external_corpus.inspect_packet(checkout, allowed, base)


def test_readwrite_filesystem_rejected(tmp_path):
    with pytest.raises(QualificationSafetyError, match="external_mount_not_readonly"):
        external_corpus._readonly(tmp_path)
