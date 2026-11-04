"""Invented receipts exercise validation; none proves authentic acquisition."""

import hashlib
import json
import zipfile

import pytest

from ketrika.core import corpus
from tests.unit.test_wb_archive import MEMBER, packet


@pytest.fixture
def archive_corpus(tmp_path):
    folder = tmp_path / "tests/fixtures"
    folder.mkdir(parents=True)
    original = folder / "original.zip"
    original.write_bytes(packet())
    rights = {
        "status": "verified",
        "licence": "test-only",
        "evidence": "https://example.org/test-rights",
    }
    source = {
        "path": "tests/fixtures/original.zip",
        "artifact_type": "wb_zip_csv_v1",
        "authenticity": "authentic",
        "archive_member": MEMBER,
        "origin": {"kind": "official_acquisition", "reference": "tests/acquisition.json"},
        "rights": rights,
        "annotator": "agent",
        "human_reviewed": False,
    }
    receipt = {
        "source_id": "wb_rtfp_mdg",
        "source_url": "https://example.org/test-data",
        "catalogue_url": "https://example.org/test-catalogue",
        "mime_type": "application/zip",
        "access_method": "public_download",
        "discovered_at": "2026-11-04T00:00:00Z",
        "fetched_at": "2026-11-04T00:00:01Z",
        "published_at": None,
        "http_status": 200,
        "redirect_chain": ["https://example.org/test-data"],
        "allowed_hosts": ["example.org"],
        "bronze_object_key": None,
        "rights": rights,
    }
    golden = {
        "metadata": {
            "document_path": source["path"],
            "annotator": "agent",
            "human_reviewed": False,
            "method": "independent_transcription",
            "annotated_at": "2026-11-04T00:01:00Z",
            "scope": "synthetic validator example only",
            "format": "wb_zip_csv_v1",
        },
        "cells": [
            {"path": [MEMBER, 0, "c_rice"], "value_type": "number", "expected": "1234.567890"},
            {"path": [MEMBER, 0, "currency"], "value_type": "text", "expected": "MGA"},
        ],
    }
    annotation = {
        "path": "tests/fixtures/annotation.json",
        "artifact_type": "golden",
        "authenticity": "authentic",
        "origin": {"kind": "independent_annotation", "reference": source["path"]},
        "rights": rights,
        "annotator": "agent",
        "human_reviewed": False,
    }

    def save():
        for entry in (source,):
            path = tmp_path / entry["path"]
            entry.update(
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), size_bytes=path.stat().st_size
            )
        receipt.update(sha256=source["sha256"], size_bytes=source["size_bytes"])
        golden["metadata"]["document_sha256"] = source["sha256"]
        (tmp_path / "tests/acquisition.json").write_text(json.dumps(receipt))
        path = tmp_path / annotation["path"]
        path.write_text(json.dumps(golden))
        annotation.update(
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), size_bytes=path.stat().st_size
        )
        return corpus.validate_manifest(tmp_path, {"version": 1, "entries": [source, annotation]})

    return source, receipt, golden, save


def test_archive_annotation_reads_original_lexemes(archive_corpus):
    *_, save = archive_corpus
    result = save()
    assert result["verified_annotation_cells"] == 2
    assert result["authentic_documents"] == ["tests/fixtures/original.zip"]


@pytest.mark.parametrize("expected", ["1234.56789", "1234.5679", "NaN", ""])
def test_numeric_lexeme_cannot_be_rounded_or_invented(archive_corpus, expected):
    _, _, golden, save = archive_corpus
    golden["cells"][0]["expected"] = expected
    with pytest.raises(corpus.CorpusError, match="Numeric annotation mismatch"):
        save()


@pytest.mark.parametrize("change", ["format", "member", "path", "human_reviewed", "source"])
def test_archive_identity_and_review_cannot_be_substituted(archive_corpus, change):
    source, receipt, golden, save = archive_corpus
    if change == "format":
        golden["metadata"]["format"] = "json"
    elif change == "member":
        source["archive_member"] = "other.csv"
    elif change == "path":
        golden["cells"][0]["path"] = [MEMBER, True, "c_rice"]
    elif change == "human_reviewed":
        golden["metadata"]["human_reviewed"] = True
    else:
        receipt["source_id"] = "other"
    with pytest.raises(corpus.CorpusError):
        save()


def test_larger_cap_is_not_general(archive_corpus, monkeypatch, tmp_path):
    source, _, _, save = archive_corpus
    with zipfile.ZipFile(tmp_path / source["path"], "a") as archive:
        archive.comment = b"synthetic padding" * 200
    monkeypatch.setattr(corpus, "MAX_FILE_BYTES", 1024)
    # The archive exceeds this reduced generic cap; its dedicated bound applies.
    assert save()["verified_annotation_cells"] == 2
    source["artifact_type"] = "json"
    with pytest.raises(corpus.CorpusError, match="File size"):
        save()
