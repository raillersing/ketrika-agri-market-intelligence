"""Bounded proof reads; no mutation and no implicit source/model qualification."""

from __future__ import annotations

from ketrika.core.bronze import BronzeStore
from ketrika.core.provenance import MAX_CONTENT_BYTES, ProofError


class BronzeProofReader:
    def __init__(self, store: BronzeStore) -> None:
        self.store = store

    def get(self, object_key: str) -> bytes:
        response = self.store.client.get_object(Bucket=self.store.bucket, Key=object_key)
        body = response["Body"]
        try:
            declared = response.get("ContentLength")
            if declared is not None:
                if type(declared) is not int or declared < 0:
                    raise ProofError("invalid_object_size")
                if declared > MAX_CONTENT_BYTES:
                    raise ProofError("content_too_large")
            content = body.read(MAX_CONTENT_BYTES + 1)
            if not isinstance(content, bytes):
                raise ProofError("invalid_document")
            if len(content) > MAX_CONTENT_BYTES:
                raise ProofError("content_too_large")
            if declared is not None and declared != len(content):
                raise ProofError("object_size_mismatch")
            return content
        finally:
            body.close()
