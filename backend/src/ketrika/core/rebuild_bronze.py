"""Closed, read-only local Bronze copy for a network-isolated replay worker."""

from __future__ import annotations

import hashlib
import io
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from ketrika.core.provenance import MAX_CONTENT_BYTES


class LocalBronzeError(ValueError):
    """Stable failure, no arbitrary fallback or source content in messages."""


class LocalBronzeClient:
    """Subset used by BronzeStore and BronzeProofReader; never creates an S3 client.

    Objects are pre-exported as <SHA>.blob. The original S3 inventory/version
    evidence is separate: this copy must never claim to be the whole bucket.
    """

    def __init__(self, root: Path, bucket: str, objects: Mapping[str, Mapping[str, Any]]) -> None:
        if root.is_symlink() or not root.is_dir() or not bucket or not objects:
            raise LocalBronzeError("local_bronze_invalid_inventory")
        self.root = root.resolve()
        self.bucket = bucket
        self.objects: dict[str, tuple[str, int]] = {}
        if len(objects) > 100_000:
            raise LocalBronzeError("local_bronze_inventory_too_large")
        for key, metadata in objects.items():
            if not isinstance(key, str):
                raise LocalBronzeError("local_bronze_invalid_key")
            path = PurePosixPath(key)
            if not key or path.is_absolute() or ".." in path.parts or "\\" in key:
                raise LocalBronzeError("local_bronze_invalid_key")
            if not isinstance(metadata, Mapping) or set(metadata) != {"sha256", "size_bytes"}:
                raise LocalBronzeError("local_bronze_invalid_inventory")
            digest, size = metadata["sha256"], metadata["size_bytes"]
            if (
                not isinstance(digest, str)
                or re.fullmatch("[0-9a-f]{64}", digest) is None
                or type(size) is not int
                or not 0 <= size <= MAX_CONTENT_BYTES
            ):
                raise LocalBronzeError("local_bronze_invalid_descriptor")
            self.objects[key] = digest, size

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        """Fresh bounded read with hash; keyword names match boto3's GET API."""
        if Bucket != self.bucket or Key not in self.objects:
            raise LocalBronzeError("local_bronze_object_not_declared")
        digest, size = self.objects[Key]
        path = self.root / (digest + ".blob")
        if path.is_symlink() or not path.is_file() or path.resolve().parent != self.root:
            raise LocalBronzeError("local_bronze_object_missing_or_unsafe")
        try:
            with path.open("rb") as stream:
                content = stream.read(MAX_CONTENT_BYTES + 1)
        except OSError:
            raise LocalBronzeError("local_bronze_object_unreadable") from None
        if len(content) != size or hashlib.sha256(content).hexdigest() != digest:
            raise LocalBronzeError("local_bronze_object_integrity_failed")
        return {"Body": io.BytesIO(content), "ContentLength": size}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, int]:
        response = self.get_object(Bucket=Bucket, Key=Key)
        response["Body"].close()
        return {"ContentLength": response["ContentLength"]}

    def put_object(self, **kwargs: Any) -> None:
        raise LocalBronzeError("local_bronze_read_only")
