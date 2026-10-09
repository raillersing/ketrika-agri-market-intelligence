"""Corpus integrity regressions. Temporary examples never prove live acquisition."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from ketrika.core import corpus
from ketrika.core.registry import find_repo_root


@pytest.fixture
def example(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    path = tmp_path / "tests/fixtures/example.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b'{"test": true}\n')
    entry = {
        "path": "tests/fixtures/example.json",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": path.stat().st_size,
        "artifact_type": "json",
        "authenticity": "unverified",
        "origin": {"kind": "unknown_legacy", "reference": None},
        "rights": {"status": "unknown", "licence": None, "evidence": None},
        "annotator": "agent",
        "human_reviewed": False,
    }
    return tmp_path, {"version": 1, "entries": [entry]}


def authenticated_example(base: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Invented receipt used only for negative validator tests, never repository corpus."""
    entry = manifest["entries"][0]
    entry["authenticity"] = "authentic"
    entry["origin"] = {"kind": "official_acquisition", "reference": "tests/acquisition.json"}
    entry["rights"] = {
        "status": "verified",
        "licence": "test-only",
        "evidence": "https://example.org/rights",
    }
    receipt = {
        "source_id": "test_only",
        "source_url": "https://example.org/data",
        "catalogue_url": "https://example.org/catalogue",
        "discovered_at": "2026-10-09T00:00:00Z",
        "fetched_at": "2026-10-09T00:00:01Z",
        "published_at": None,
        "http_status": 200,
        "mime_type": "application/json",
        "access_method": "api",
        "sha256": entry["sha256"],
        "size_bytes": entry["size_bytes"],
        "redirect_chain": ["https://example.org/data"],
        "allowed_hosts": ["example.org"],
        "bronze_object_key": None,
        "rights": entry["rights"],
    }
    (base / "tests/acquisition.json").write_text(json.dumps(receipt))
    return receipt


def test_repository_inventory_complete() -> None:
    base = find_repo_root() / "backend"
    report = corpus.validate_manifest(base, corpus.load_manifest(base))
    assert report["files"] >= 63
    assert report["counts"]["synthetic"] >= 30
    assert report["counts"]["unverified"] > 0
    assert "not live collection" in report["scope"]


def test_unverified_is_excluded(example: tuple[Path, dict[str, Any]]) -> None:
    base, manifest = example
    report = corpus.validate_manifest(base, manifest)
    assert report["authentic_documents"] == []
    assert report["counts"] == {"unverified": 1}


def test_valid_receipt_validation_only(example: tuple[Path, dict[str, Any]]) -> None:
    base, manifest = example
    authenticated_example(base, manifest)
    assert corpus.validate_manifest(base, manifest)["authentic_documents"] == [
        "tests/fixtures/example.json"
    ]


@pytest.mark.parametrize(
    "path", ["../escape", "/tmp/escape", "tests/../../escape", "a\\b", None, ""]
)
def test_unsafe_path(path: Any, tmp_path: Path) -> None:
    with pytest.raises(corpus.CorpusError):
        corpus.safe_path(tmp_path, path)


def test_symlink_refused(example: tuple[Path, dict[str, Any]]) -> None:
    base, _ = example
    (base / "link").symlink_to(base / "tests/fixtures/example.json")
    with pytest.raises(corpus.CorpusError):
        corpus.safe_path(base, "link")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sha256", "0" * 64),
        ("size_bytes", 0),
        ("artifact_type", ""),
        ("authenticity", "official_looking"),
        ("origin", None),
        ("rights", None),
        ("annotator", None),
        ("human_reviewed", True),
    ],
)
def test_invalid_entry(example: tuple[Path, dict[str, Any]], field: str, value: Any) -> None:
    base, manifest = example
    manifest["entries"][0][field] = value
    with pytest.raises(corpus.CorpusError):
        corpus.validate_manifest(base, manifest)


def test_missing_origin_kind(example: tuple[Path, dict[str, Any]]) -> None:
    base, manifest = example
    manifest["entries"][0]["origin"] = {}
    with pytest.raises(corpus.CorpusError):
        corpus.validate_manifest(base, manifest)


def test_duplicates(example: tuple[Path, dict[str, Any]]) -> None:
    base, manifest = example
    manifest["entries"].append(copy.deepcopy(manifest["entries"][0]))
    with pytest.raises(corpus.CorpusError):
        corpus.validate_manifest(base, manifest)


def test_missing_inventory_item(example: tuple[Path, dict[str, Any]]) -> None:
    base, manifest = example
    manifest["entries"] = []
    with pytest.raises(corpus.CorpusError):
        corpus.validate_manifest(base, manifest)


@pytest.mark.parametrize(
    "manifest", [{"version": 2, "entries": []}, {"version": 1, "entries": None}]
)
def test_invalid_manifest(tmp_path: Path, manifest: dict[str, Any]) -> None:
    with pytest.raises(corpus.CorpusError):
        corpus.validate_manifest(tmp_path, manifest)


@pytest.mark.parametrize("limit", ["MAX_FILE_BYTES", "MAX_TOTAL_BYTES"])
def test_size_limits(
    example: tuple[Path, dict[str, Any]], monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    base, manifest = example
    monkeypatch.setattr(corpus, limit, 1)
    with pytest.raises(corpus.CorpusError):
        corpus.validate_manifest(base, manifest)


def test_modified_bytes(example: tuple[Path, dict[str, Any]]) -> None:
    base, manifest = example
    (base / "tests/fixtures/example.json").write_bytes(b'{"test": null}\n')
    with pytest.raises(corpus.CorpusError, match="hash"):
        corpus.validate_manifest(base, manifest)


def test_synthetic_generator_required(example: tuple[Path, dict[str, Any]]) -> None:
    base, manifest = example
    entry = manifest["entries"][0]
    entry["authenticity"] = "synthetic"
    entry["origin"]["reference"] = "scripts/missing.py"
    with pytest.raises(corpus.CorpusError, match="generator"):
        corpus.validate_manifest(base, manifest)
    entry["origin"]["reference"] = entry["path"]
    assert corpus.validate_manifest(base, manifest)["authentic_documents"] == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_id", None),
        ("source_url", None),
        ("catalogue_url", "http://example.org"),
        ("source_url", "https://user:password@example.org"),
        ("discovered_at", "2026-10-09"),
        ("fetched_at", "invalidZ"),
        ("http_status", 403),
        ("published_at", "2024-01-01"),
        ("sha256", "0" * 64),
        ("size_bytes", 0),
        ("redirect_chain", []),
        ("redirect_chain", ["https://other.example/data"]),
        ("allowed_hosts", []),
        ("bronze_object_key", "invented/key"),
        ("rights", {}),
    ],
)
def test_invalid_acquisition(example: tuple[Path, dict[str, Any]], field: str, value: Any) -> None:
    base, manifest = example
    receipt = authenticated_example(base, manifest)
    receipt[field] = value
    (base / "tests/acquisition.json").write_text(json.dumps(receipt))
    with pytest.raises(corpus.CorpusError):
        corpus.validate_manifest(base, manifest)


def test_missing_acquisition(example: tuple[Path, dict[str, Any]]) -> None:
    base, manifest = example
    manifest["entries"][0]["authenticity"] = "authentic"
    manifest["entries"][0]["origin"]["kind"] = "official_acquisition"
    manifest["entries"][0]["origin"]["reference"] = "tests/missing.json"
    with pytest.raises(corpus.CorpusError, match="Missing acquisition"):
        corpus.validate_manifest(base, manifest)


def test_no_rights_proof(example: tuple[Path, dict[str, Any]]) -> None:
    base, manifest = example
    authenticated_example(base, manifest)
    manifest["entries"][0]["rights"]["status"] = "unknown"
    with pytest.raises(corpus.CorpusError, match="rights"):
        corpus.validate_manifest(base, manifest)


def test_invalid_receipt_shape(example: tuple[Path, dict[str, Any]]) -> None:
    base, manifest = example
    authenticated_example(base, manifest)
    (base / "tests/acquisition.json").write_text("[]")
    with pytest.raises(corpus.CorpusError):
        corpus.validate_manifest(base, manifest)


def annotation_example(
    base: Path, manifest: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    authenticated_example(base, manifest)
    source = manifest["entries"][0]
    entry = {
        "path": "tests/annotation.json",
        "origin": {"kind": "independent_annotation", "reference": source["path"]},
        "rights": copy.deepcopy(source["rights"]),
    }
    golden = {
        "metadata": {
            "document_path": source["path"],
            "document_sha256": source["sha256"],
            "annotator": "agent",
            "human_reviewed": False,
            "method": "independent_transcription",
            "annotated_at": "2026-10-09T00:00:00Z",
            "scope": "one test-only cell, not market data",
        },
        "cells": [{"path": ["test"], "expected": "true", "value_type": "text"}],
    }
    (base / entry["path"]).write_text(json.dumps(golden))
    return entry, golden


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("document_path", "wrong"),
        ("document_sha256", "0" * 64),
        ("annotator", None),
        ("human_reviewed", True),
        ("method", "tested_parser"),
        ("annotated_at", "badZ"),
        ("scope", ""),
    ],
)
def test_invalid_annotation_metadata(
    example: tuple[Path, dict[str, Any]], field: str, value: Any
) -> None:
    base, manifest = example
    entry, golden = annotation_example(base, manifest)
    golden["metadata"][field] = value
    (base / entry["path"]).write_text(json.dumps(golden))
    with pytest.raises(corpus.CorpusError):
        corpus.validate_annotation(
            base, entry, {manifest["entries"][0]["path"]: manifest["entries"][0]}
        )


@pytest.mark.parametrize(
    "cell",
    [
        {"path": []},
        {"path": [None]},
        {"path": [-1]},
        {"path": ["absent"]},
        {"path": ["test", "nested"]},
        {"path": ["test"], "expected": "true", "value_type": "number"},
        {"path": ["test"], "expected": True, "value_type": "unknown"},
        {"path": ["test"], "expected": "true", "value_type": "text"},
    ],
)
def test_invalid_annotation_cell(
    example: tuple[Path, dict[str, Any]], cell: dict[str, Any]
) -> None:
    base, manifest = example
    entry, golden = annotation_example(base, manifest)
    golden["cells"] = [cell]
    (base / entry["path"]).write_text(json.dumps(golden))
    with pytest.raises(corpus.CorpusError):
        corpus.validate_annotation(
            base, entry, {manifest["entries"][0]["path"]: manifest["entries"][0]}
        )


@pytest.mark.parametrize("cells", [[], None, [{"path": ["test"]}, {"path": ["test"]}]])
def test_empty_or_duplicate_annotation(example: tuple[Path, dict[str, Any]], cells: Any) -> None:
    base, manifest = example
    entry, golden = annotation_example(base, manifest)
    golden["cells"] = cells
    # Use a real text value so duplicate-path rejection is reached before comparison.
    (base / "tests/fixtures/example.json").write_text('{"test":"true"}')
    source = manifest["entries"][0]
    source["sha256"] = corpus.sha256(base / source["path"])
    source["size_bytes"] = (base / source["path"]).stat().st_size
    authenticated_example(base, manifest)
    golden["metadata"]["document_sha256"] = source["sha256"]
    if isinstance(cells, list):
        for cell in cells:
            cell.update({"expected": "true", "value_type": "text"})
    (base / entry["path"]).write_text(json.dumps(golden))
    with pytest.raises(corpus.CorpusError):
        corpus.validate_annotation(base, entry, {source["path"]: source})


@pytest.mark.parametrize("kind", ["synthetic", "unverified"])
def test_annotation_non_authentic_source(example: tuple[Path, dict[str, Any]], kind: str) -> None:
    base, manifest = example
    entry, _ = annotation_example(base, manifest)
    source = manifest["entries"][0]
    source["authenticity"] = kind
    with pytest.raises(corpus.CorpusError):
        corpus.validate_annotation(base, entry, {source["path"]: source})


def test_annotation_rights_mismatch(example: tuple[Path, dict[str, Any]]) -> None:
    base, manifest = example
    entry, _ = annotation_example(base, manifest)
    entry["rights"] = {}
    source = manifest["entries"][0]
    with pytest.raises(corpus.CorpusError):
        corpus.validate_annotation(base, entry, {source["path"]: source})


def test_authentic_origin_refused(example: tuple[Path, dict[str, Any]]) -> None:
    base, manifest = example
    manifest["entries"][0]["authenticity"] = "authentic"
    with pytest.raises(corpus.CorpusError, match="Unsupported authentic origin"):
        corpus.validate_manifest(base, manifest)
