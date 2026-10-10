"""Bounded SDK-body simulations only; no oversized real Bronze objects."""

from unittest.mock import MagicMock

import pytest

from ketrika.core.bronze import BronzeStore
from ketrika.core.provenance import MAX_CONTENT_BYTES, ProofError
from ketrika.core.provenance_bronze import BronzeProofReader


def reader(content=b"source", declared=6):
    store, body = MagicMock(spec=BronzeStore), MagicMock()
    store.bucket, store.client = "test-bucket", MagicMock()
    body.read.return_value = content
    response = {"Body": body}
    if declared is not None:
        response["ContentLength"] = declared
    store.client.get_object.return_value = response
    return BronzeProofReader(store), store, body


@pytest.mark.parametrize("declared", [6, None])
def test_original_bytes_are_read_with_limit_and_stream_closed(declared) -> None:
    instance, store, body = reader(declared=declared)
    assert instance.get("existing-key") == b"source"
    body.read.assert_called_once_with(MAX_CONTENT_BYTES + 1)
    body.close.assert_called_once()
    store.client.get_object.assert_called_once_with(Bucket="test-bucket", Key="existing-key")
    store.client.put_object.assert_not_called()
    store.client.delete_object.assert_not_called()


@pytest.mark.parametrize(
    "declared,reason",
    [
        (MAX_CONTENT_BYTES + 1, "content_too_large"),
        (-1, "invalid_object_size"),
        (True, "invalid_object_size"),
        ("6", "invalid_object_size"),
    ],
)
def test_bad_declared_size_refused_without_reading_body(declared, reason) -> None:
    instance, _, body = reader(declared=declared)
    with pytest.raises(ProofError, match=reason):
        instance.get("existing-key")
    body.read.assert_not_called()
    body.close.assert_called_once()


@pytest.mark.parametrize(
    "content,declared,reason",
    [
        (b"source", 7, "object_size_mismatch"),
        ("source", 6, "invalid_document"),
        (b"x" * (MAX_CONTENT_BYTES + 1), 0, "content_too_large"),
    ],
)
def test_body_is_not_certified_from_header_only(content, declared, reason) -> None:
    instance, _, body = reader(content, declared)
    with pytest.raises(ProofError, match=reason):
        instance.get("existing-key")
    body.close.assert_called_once()


def test_transport_failure_still_closes_body() -> None:
    instance, _, body = reader()
    body.read.side_effect = RuntimeError("simulated transport failure")
    with pytest.raises(RuntimeError, match="simulated transport failure"):
        instance.get("existing-key")
    body.close.assert_called_once()
