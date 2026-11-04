"""Offline authenticity checks for the R0.4 corpus, not market certification."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
CORPUS_ROOTS = ("tests/fixtures", "tests/golden", "tests/e2e_data")


class CorpusError(ValueError):
    """A corpus receipt is missing, inconsistent, or unsafe."""


def safe_path(base: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or "\\" in relative:
        raise CorpusError("Expected a relative POSIX path")
    parts = PurePosixPath(relative)
    if parts.is_absolute() or ".." in parts.parts or not parts.parts:
        raise CorpusError("Path escapes corpus")
    path = base / relative
    if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):
        raise CorpusError("Path escapes corpus or is a symlink")
    return path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def corpus_files(base: Path) -> set[str]:
    paths = set(base.glob("scripts/generate_*_fixtures.py"))
    for folder in CORPUS_ROOTS:
        paths.update(p for p in (base / folder).rglob("*") if p.is_file())
    return {
        p.relative_to(base).as_posix()
        for p in paths
        if "__pycache__" not in p.parts and p.suffix != ".pyc"
    }


def _utc(value: Any) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CorpusError("Acquisition needs a UTC timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CorpusError("Invalid acquisition timestamp") from exc


def _https(value: Any) -> None:
    if not isinstance(value, str):
        raise CorpusError("Missing HTTPS evidence URL")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise CorpusError("Unsafe evidence URL")


def validate_acquisition(base: Path, entry: dict[str, Any]) -> dict[str, Any]:
    reference = entry["origin"].get("reference")
    path = safe_path(base, reference)
    if not path.is_file():
        raise CorpusError("Missing acquisition evidence")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        raise CorpusError("Invalid acquisition evidence")
    for key in ("source_id", "source_url", "catalogue_url", "mime_type", "access_method"):
        if not receipt.get(key):
            raise CorpusError(f"Missing acquisition {key}")
    _https(receipt["source_url"])
    _https(receipt["catalogue_url"])
    _utc(receipt.get("discovered_at"))
    _utc(receipt.get("fetched_at"))
    if receipt.get("http_status") != 200 or receipt.get("published_at") is not None:
        raise CorpusError("HTTP must be 200; historical publication is unproved in this corpus")
    if receipt.get("sha256") != entry["sha256"] or receipt.get("size_bytes") != entry["size_bytes"]:
        raise CorpusError("Acquisition bytes do not match artifact")
    chain = receipt.get("redirect_chain")
    if not isinstance(chain, list) or not chain or chain[0] != receipt["source_url"]:
        raise CorpusError("Missing redirect chain")
    for url in chain:
        _https(url)
        if urlsplit(url).hostname not in receipt.get("allowed_hosts", []):
            raise CorpusError("Unapproved redirect host")
    if receipt.get("bronze_object_key", "missing") is not None:
        raise CorpusError("Local corpus must not claim Bronze ingestion")
    rights = entry["rights"]
    if rights.get("status") != "verified" or not rights.get("licence"):
        raise CorpusError("Authentic qualification requires verified rights")
    _https(rights.get("evidence"))
    if receipt.get("rights") != rights:
        raise CorpusError("Rights receipt mismatch")
    return receipt


def validate_annotation(base: Path, entry: dict[str, Any], entries: dict[str, Any]) -> int:
    document = entry["origin"].get("reference")
    source = entries.get(document)
    if (
        not source
        or source.get("authenticity") != "authentic"
        or source["origin"].get("kind") != "official_acquisition"
    ):
        raise CorpusError("Golden must reference an authentic acquired document")
    validate_acquisition(base, source)
    original_path = safe_path(base, document)
    maximum = 8 * 1024 * 1024 if source.get("artifact_type") == "wb_zip_csv_v1" else MAX_FILE_BYTES
    if original_path.stat().st_size > maximum:
        raise CorpusError("Annotated original exceeds size limit")
    original = original_path.read_bytes()
    if len(original) != source.get("size_bytes") or hashlib.sha256(
        original
    ).hexdigest() != source.get("sha256"):
        raise CorpusError("Annotated original bytes mismatch")
    golden = json.loads(safe_path(base, entry["path"]).read_text())
    metadata = golden.get("metadata", {})
    if (
        metadata.get("document_sha256") != source["sha256"]
        or metadata.get("document_path") != document
    ):
        raise CorpusError("Golden document identity mismatch")
    if (
        metadata.get("annotator") != "agent"
        or metadata.get("human_reviewed") is not False
        or metadata.get("method") != "independent_transcription"
    ):
        raise CorpusError("Independent annotation metadata required")
    _utc(metadata.get("annotated_at"))
    if (
        not metadata.get("scope")
        or not isinstance(golden.get("cells"), list)
        or not golden["cells"]
    ):
        raise CorpusError("Annotation must declare scope and cells")
    if entry["rights"] != source["rights"]:
        raise CorpusError("Annotation rights must follow original document")
    archive_cells = None
    if source.get("artifact_type") == "wb_zip_csv_v1":
        from ketrika.core.wb_archive import ArchiveError, cells

        if metadata.get("format") != "wb_zip_csv_v1":
            raise CorpusError("ZIP annotation format required")
        coordinates = [cell.get("path") for cell in golden["cells"]]
        if any(not isinstance(path, list) for path in coordinates):
            raise CorpusError("Invalid ZIP annotation coordinates")
        try:
            archive_cells = cells(original, coordinates)
        except ArchiveError as exc:
            raise CorpusError(str(exc)) from None
        payload = None
    else:
        payload = json.loads(original.decode("utf-8"), parse_float=Decimal)
    seen: set[tuple[Any, ...]] = set()
    for cell in golden["cells"]:
        keys = cell.get("path")
        if (
            not isinstance(keys, list)
            or not keys
            or any(type(key) not in (int, str) for key in keys)
        ):
            raise CorpusError("Cell path must be a nonempty key/index list")
        identity = tuple(keys)
        if identity in seen:
            raise CorpusError("Duplicate annotation cell")
        seen.add(identity)
        value: Any
        if archive_cells is not None:
            value = archive_cells[tuple(keys)]
        else:
            value = payload
            try:
                for key in keys:
                    if isinstance(key, int) and key < 0:
                        raise CorpusError("Negative cell indices forbidden")
                    value = value[key]
            except (IndexError, KeyError, TypeError) as exc:
                raise CorpusError("Annotation cell is absent in source") from exc
        expected = cell.get("expected")
        if cell.get("value_type") == "number":
            if archive_cells is not None:
                from decimal import InvalidOperation

                try:
                    numeric = Decimal(value)
                except (InvalidOperation, TypeError):
                    raise CorpusError("Numeric annotation mismatch") from None
                if not numeric.is_finite() or value != expected:
                    raise CorpusError("Numeric annotation mismatch")
                continue
            if (
                type(value) not in (Decimal, int)
                or not isinstance(expected, str)
                or str(value) != expected
            ):
                raise CorpusError("Numeric annotation mismatch")
        elif cell.get("value_type") == "text":
            if not isinstance(value, str) or value != expected:
                raise CorpusError("Text annotation mismatch")
        else:
            raise CorpusError("Unsupported annotation type")
    return len(seen)


def validate_manifest(base: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("version") != 1 or not isinstance(manifest.get("entries"), list):
        raise CorpusError("Unsupported corpus manifest")
    files = corpus_files(base)
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    total = 0
    authentic: list[str] = []
    annotations: list[dict[str, Any]] = []
    for entry in manifest["entries"]:
        path = safe_path(base, entry.get("path"))
        relative = entry["path"]
        if relative in seen or relative not in files:
            raise CorpusError("Duplicate or non-corpus file")
        seen.add(relative)
        size = path.stat().st_size
        is_wb_archive = entry.get("artifact_type") == "wb_zip_csv_v1"
        maximum = 8 * 1024 * 1024 if is_wb_archive else MAX_FILE_BYTES
        if size > maximum or entry.get("size_bytes") != size:
            raise CorpusError("File size limit or receipt mismatch")
        total += size
        if entry.get("sha256") != sha256(path):
            raise CorpusError("Artifact hash mismatch")
        kind = entry.get("authenticity")
        if kind not in ("authentic", "synthetic", "unverified"):
            raise CorpusError("Unknown authenticity")
        if not entry.get("artifact_type") or not isinstance(entry.get("origin"), dict):
            raise CorpusError("Missing artifact type/origin")
        if not entry["origin"].get("kind") or not isinstance(entry.get("rights"), dict):
            raise CorpusError("Missing origin/rights")
        if is_wb_archive and (
            kind != "authentic" or entry["origin"].get("kind") != "official_acquisition"
        ):
            raise CorpusError("WB archive requires official acquisition")
        if entry.get("annotator") != "agent" or entry.get("human_reviewed") is not False:
            raise CorpusError("Human review is not proved by this corpus")
        if kind == "synthetic":
            proof = safe_path(base, entry["origin"].get("reference"))
            if not proof.is_file():
                raise CorpusError("Missing generator proof")
        if kind == "authentic":
            if entry["origin"].get("kind") == "independent_annotation":
                annotations.append(entry)
            elif entry["origin"].get("kind") == "official_acquisition":
                receipt = validate_acquisition(base, entry)
                if is_wb_archive:
                    from ketrika.core.wb_archive import ArchiveError, rows

                    if receipt["source_id"] != "wb_rtfp_mdg" or receipt["mime_type"].split(";")[
                        0
                    ].strip().lower() not in ("application/zip", "application/octet-stream"):
                        raise CorpusError("WB archive acquisition required")
                    try:
                        for _ in rows(path.read_bytes(), entry.get("archive_member")):
                            pass
                    except ArchiveError as exc:
                        raise CorpusError(str(exc)) from None
                authentic.append(relative)
            else:
                raise CorpusError("Unsupported authentic origin")
        counts[kind] += 1
    if seen != files:
        raise CorpusError(f"Incomplete inventory: {sorted(files - seen)}")
    if total > MAX_TOTAL_BYTES:
        raise CorpusError("Corpus total size exceeds limit")
    index = {entry["path"]: entry for entry in manifest["entries"]}
    cells = sum(validate_annotation(base, entry, index) for entry in annotations)
    return {
        "files": len(seen),
        "size_bytes": total,
        "counts": dict(counts),
        "authentic_documents": authentic,
        "authentic_annotations": len(annotations),
        "verified_annotation_cells": cells,
        "scope": "offline artifact integrity only; not live collection or market performance",
    }


def load_manifest(base: Path) -> dict[str, Any]:
    result: dict[str, Any] = json.loads((base / "tests/corpus-manifest.json").read_text())
    return result
