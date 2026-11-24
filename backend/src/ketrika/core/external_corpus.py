"""Read the pinned R0.8 packet without importing it into the checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from ketrika.core.corpus import MAX_TOTAL_BYTES, load_manifest, validate_manifest
from ketrika.core.qualification import QualificationSafetyError

REFERENCE = "docs/evidence/R0.8_WB_ARCHIVE_20261104_PACKET_MANIFEST.json"
MANIFEST = "tests/corpus-manifest.json"
MAX_METADATA_BYTES = 1024 * 1024


def _directory(path: Path) -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise QualificationSafetyError("external_path_not_absolute")
    for part in reversed((path, *path.parents)):
        if part.is_symlink():
            raise QualificationSafetyError("external_symlink_forbidden")
    if not path.is_dir():
        raise QualificationSafetyError("external_directory_missing")
    return path.resolve(strict=True)


def _readonly(path: Path) -> None:
    if not os.statvfs(path).f_flag & os.ST_RDONLY:
        raise QualificationSafetyError("external_mount_not_readonly")


def _read(path: Path, maximum: int) -> bytes:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise QualificationSafetyError("external_nonregular_file")
    _readonly(path)
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise QualificationSafetyError("external_file_too_large")
    return data


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _inventory(base: Path, expected: set[str]) -> None:
    directories = {Path(".")}
    for name in expected:
        directories.update(Path(name).parents)
    for relative in sorted(directories, key=lambda path: (len(path.parts), str(path))):
        directory = base / relative
        if directory.is_symlink() or not directory.is_dir():
            raise QualificationSafetyError("external_directory_invalid")
        _readonly(directory)
        for item in directory.iterdir():
            relative_item = item.relative_to(base)
            if item.is_symlink() or (
                relative_item not in directories and relative_item.as_posix() not in expected
            ):
                raise QualificationSafetyError("external_inventory_invalid")


def inspect_packet(root: Path, allowed_root: Path, base: Path) -> dict[str, Any]:
    """Validate the exact historical WB packet; this is not replay evidence."""
    checkout = root.resolve(strict=True)
    allowed = _directory(allowed_root)
    packet = _directory(base)
    if (
        not packet.is_relative_to(allowed)
        or allowed.is_relative_to(checkout)
        or checkout.is_relative_to(allowed)
    ):
        raise QualificationSafetyError("external_path_outside_allowed_root")
    _readonly(allowed)
    _readonly(packet)

    reference = json.loads((checkout / REFERENCE).read_text(encoding="utf-8"))
    expected = {MANIFEST}
    limits = {MANIFEST: MAX_METADATA_BYTES}
    for entry in reference["entries"]:
        name = entry["path"]
        expected.add(name)
        limits[name] = entry["size_bytes"]
        if entry["origin"]["kind"] == "official_acquisition":
            receipt = entry["origin"]["reference"]
            expected.add(receipt)
            limits[receipt] = MAX_METADATA_BYTES
    if (packet / "validation.json").exists():
        expected.add("validation.json")
        limits["validation.json"] = MAX_METADATA_BYTES
    _inventory(packet, expected)

    def identity() -> dict[str, str]:
        total = 0
        hashes = {}
        for name in sorted(expected):
            data = _read(packet / name, limits[name])
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise QualificationSafetyError("external_packet_too_large")
            hashes[name] = hashlib.sha256(data).hexdigest()
        return hashes

    hashes = identity()
    manifest = load_manifest(packet)
    if _canonical(manifest) != _canonical(reference):
        raise QualificationSafetyError("external_manifest_not_pinned")
    measured = validate_manifest(packet, manifest)
    if (
        measured["counts"] != {"authentic": 6}
        or len(measured["authentic_documents"]) != 3
        or measured["authentic_annotations"] != 3
        or measured["verified_annotation_cells"] != 664
    ):
        raise QualificationSafetyError("external_packet_scope_mismatch")
    if identity() != hashes:
        raise QualificationSafetyError("external_packet_changed")
    return {
        **measured,
        "packet_sha256": hashlib.sha256(_canonical(hashes)).hexdigest(),
        "reference": REFERENCE,
        "file_sha256": hashes,
        "rebuild_qualified": False,
        "human_reviewed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--external-root", required=True, type=Path)
    parser.add_argument("--external-corpus", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = inspect_packet(args.root, args.external_root, args.external_corpus)
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "external_corpus_invalid\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
