"""Explicit processing identity, not a persistent ledger or provenance proof."""

import hashlib
import json
import re
from dataclasses import dataclass
from uuid import UUID


def _token(value: str, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or value != value.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError(f"artifact_identity_invalid_{name}")
    return value


def _sha(value: str, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"artifact_identity_invalid_{name}")
    return value


def _uuid(value: UUID, name: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise ValueError(f"artifact_identity_invalid_{name}")
    return value


def _digest(parts: list[str]) -> str:
    encoded = json.dumps(parts, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ArtifactProcessingIdentity:
    source_id: str
    source_record_id: UUID
    content_sha256: str
    parser_version: str
    normalizer_version: str
    reference_manifest_sha256: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_id, str)
            or re.fullmatch(r"[a-z0-9_]{1,128}", self.source_id) is None
        ):
            raise ValueError("artifact_identity_invalid_source_id")
        _uuid(self.source_record_id, "source_record_id")
        _sha(self.content_sha256, "content_sha256")
        _token(self.parser_version, "parser_version")
        _token(self.normalizer_version, "normalizer_version")
        _sha(self.reference_manifest_sha256, "reference_manifest_sha256")

    @property
    def processing_key(self) -> str:
        return _digest(
            [
                "artifact_processing_identity_v1",
                self.source_id,
                str(self.source_record_id),
                self.content_sha256,
                self.parser_version,
                self.normalizer_version,
                self.reference_manifest_sha256,
            ]
        )

    def run_member_key(self, run_id: UUID) -> str:
        _uuid(run_id, "run_id")
        return _digest(["artifact_run_member_v1", str(run_id), self.processing_key])
