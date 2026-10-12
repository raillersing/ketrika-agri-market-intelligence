"""Internal reference snapshot archive; not source provenance or a ledger."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from ketrika.core.bronze import BronzeArtifact, BronzeStore
from ketrika.core.provenance import ArtifactReader
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.reference_manifest import (
    MAX_BYTES,
    ReferenceManifest,
    ReferenceRow,
    build_reference_manifest,
)

INTERNAL_SOURCE = "reference_manifest"


@dataclass(frozen=True)
class ArchivedReferenceManifest:
    sha256: str
    object_key: str
    row_count: int
    counts: tuple[tuple[str, int], ...]


def _validate(manifest: ReferenceManifest) -> None:
    try:
        if (
            not isinstance(manifest, ReferenceManifest)
            or not isinstance(manifest.content, bytes)
            or len(manifest.content) > MAX_BYTES
        ):
            raise ValueError
        document = json.loads(manifest.content.decode("ascii"))
        if (
            not isinstance(document, list)
            or len(document) != 2
            or document[0] != "reference_manifest_v1"
            or not isinstance(document[1], list)
        ):
            raise ValueError
        rows = []
        for member in document[1]:
            if (
                not isinstance(member, list)
                or len(member) != 3
                or any(not isinstance(value, str) for value in member)
            ):
                raise ValueError
            rows.append(ReferenceRow(*member))
        rebuilt = build_reference_manifest(rows)
        if (
            rebuilt != manifest
            or type(manifest.row_count) is not int
            or any(type(value) is not int for _, value in manifest.counts)
        ):
            raise ValueError
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ValueError("reference_archive_invalid_manifest") from None


def archive_reference_manifest(
    store: BronzeStore,
    manifest: ReferenceManifest,
    *,
    captured_at: datetime | None = None,
    reader: ArtifactReader | None = None,
) -> ArchivedReferenceManifest:
    _validate(manifest)
    when = captured_at if captured_at is not None else datetime.now(UTC)
    if not isinstance(when, datetime) or when.utcoffset() is None:
        raise ValueError("reference_archive_invalid_timestamp")
    when = when.astimezone(UTC)
    expected_key = f"{INTERNAL_SOURCE}/{when:%Y/%m}/{manifest.sha256}.json"
    artifact = store.put(
        source_id=INTERNAL_SOURCE,
        content=manifest.content,
        mime_type="application/json",
        url="",
        retrieved_via="manual_upload",
        http_status=0,
        http_headers={"x-ketrika-dataset": "internal-snapshot;source_verified=false"},
        fetched_at=when,
    )
    if not isinstance(artifact, BronzeArtifact) or (
        artifact.object_key,
        artifact.content_sha256,
        artifact.mime_type,
        artifact.url,
        artifact.size_bytes,
    ) != (expected_key, manifest.sha256, "application/json", "", len(manifest.content)):
        raise ValueError("reference_archive_descriptor_mismatch")
    bounded_reader = reader if reader is not None else BronzeProofReader(store)
    content = bounded_reader.get(expected_key)
    if (
        not isinstance(content, bytes)
        or content != manifest.content
        or hashlib.sha256(content).hexdigest() != manifest.sha256
    ):
        raise ValueError("reference_archive_content_mismatch")
    return ArchivedReferenceManifest(
        manifest.sha256, expected_key, manifest.row_count, manifest.counts
    )
