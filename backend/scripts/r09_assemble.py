"""Assemble unchanged native QA and WB receipts outside the source checkout."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ketrika.core.external_corpus import inspect_packet
from ketrika.core.external_replay import MAX_NATIVE_BYTES, PRODUCER
from ketrika.core.qualification_reports import (
    MAX_REPORT_BYTES,
    capture_binding,
    load_json_report,
)
from ketrika.core.qualify import utc, verify_binding
from ketrika.pipelines.rebuild_qualification import require_network_none

ROOT = Path("/workspace")
OUT = Path("/out")
PACKET = Path("/packet/corpus")


def copy_receipt(source: Path, destination: Path, maximum: int) -> dict[str, str]:
    if source.is_symlink() or not source.is_file():
        raise ValueError("r09_receipt_missing")
    with source.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("r09_receipt_oversized")
    with destination.open("xb") as output:
        output.write(raw)
    return {"path": destination.name, "sha256": hashlib.sha256(raw).hexdigest()}


def write_json(path: Path, document: dict[str, Any]) -> dict[str, str]:
    raw = json.dumps(document, separators=(",", ":")).encode()
    with path.open("xb") as output:
        output.write(raw)
    return {"path": path.name, "sha256": hashlib.sha256(raw).hexdigest()}


def assemble() -> None:
    require_network_none()
    if os.getuid() != 1000:
        raise ValueError("r09_nonroot_assembler_required")
    commit = os.environ["KETRIKA_SOURCE_COMMIT"]
    binding = capture_binding(ROOT, commit, dataset="authentic")
    if binding["source_fingerprint"] != os.environ["KETRIKA_SOURCE_FINGERPRINT"]:
        raise ValueError("r09_assembler_source_changed")
    now = datetime.now(UTC)
    packet = inspect_packet(ROOT, PACKET.parent, PACKET)

    def verify(document: dict[str, Any]) -> None:
        verify_binding(document, commit, binding["source_fingerprint"], binding["environment"], now)
        if document["dataset"] not in ("mixed", "synthetic"):
            raise ValueError("r09_software_dataset_invalid")

    backend = Path("/qa-backend")
    frontend = Path("/qa-frontend") / ".qa-results"
    browser = Path("/qa-browser") / "qa-browser-results"
    verify(load_json_report(backend / "qa-inventory.json"))
    execution = load_json_report(frontend / "latest.json")["execution_id"]
    if not isinstance(execution, str) or not re.fullmatch(r"[0-9a-f-]{36}", execution):
        raise ValueError("r09_frontend_execution_invalid")
    frontend_run = frontend / execution
    verify(load_json_report(frontend_run / "receipt.json"))
    candidates = []
    for directory in browser.iterdir():
        if directory.is_symlink() or not re.fullmatch(r"[0-9a-f]{32}", directory.name):
            continue
        try:
            receipt = load_json_report(directory / "receipt.json")
            verify(receipt)
            if receipt["passed"] is True:
                candidates.append((utc(receipt["captured_at"]), directory))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    if not candidates:
        raise ValueError("r09_browser_receipt_missing")
    browser_run = max(candidates)[1]
    bundle = OUT / "bundle"
    bundle.mkdir(exist_ok=False)
    evidence = {}
    for name, path, filename in (
        ("backend_junit", backend / "qa-tests.xml", "backend.xml"),
        ("backend_inventory", backend / "qa-inventory.json", "backend.json"),
        ("frontend_receipt", frontend_run / "receipt.json", "frontend.json"),
        ("frontend_vitest", frontend_run / "vitest.json", "vitest.json"),
        ("e2e_receipt", browser_run / "receipt.json", "e2e.json"),
    ):
        evidence[name] = copy_receipt(path, bundle / filename, MAX_REPORT_BYTES)
    copy_receipt(browser_run / "trace.zip", bundle / "trace.zip", MAX_REPORT_BYTES)
    native = {
        **binding,
        "environment": {
            "producer": PRODUCER,
            "backend_image_id": binding["environment"]["backend_image_id"],
        },
        "packet_sha256": packet["packet_sha256"],
        "positive": copy_receipt(OUT / "positive.json", bundle / "positive.json", MAX_NATIVE_BYTES),
        "negative": copy_receipt(OUT / "negative.json", bundle / "negative.json", MAX_NATIVE_BYTES),
    }
    reference = write_json(bundle / "native.json", native)
    for key in ("corpus", "provenance", "rebuild"):
        evidence[key] = reference
    write_json(bundle / "bundle.json", {**binding, "evidence": evidence})
    print(json.dumps({"bundle": str(bundle), "packet_sha256": packet["packet_sha256"]}))


if __name__ == "__main__":
    assemble()
