"""Unit tests for BronzeStore (SPECS §10)."""

import io
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from ketrika.core.bronze import (
    BronzeStore,
    _get_extension_for_mime,
    compute_sha256,
    verify_sha256,
)


def test_bronze_store_has_no_delete_method():
    """Verify Bronze layer is strictly immutable and exposes no delete API (AGENTS §4.2)."""
    store = BronzeStore()
    assert not hasattr(store, "delete")
    assert not hasattr(store, "remove")
    assert not hasattr(store, "drop")


def test_sha256_computation_and_verification():
    """Verify SHA-256 calculation and verification on byte payloads."""
    payload = b"Ketrika Market Data Test Payload 12345"
    sha = compute_sha256(payload)
    assert len(sha) == 64
    assert verify_sha256(payload, sha) is True
    assert verify_sha256(payload, "invalid_sha") is False


def test_bronze_store_put_and_idempotence():
    """Verify BronzeStore put is idempotent: duplicate put does not re-upload and returns is_new=False."""
    mock_s3 = MagicMock()
    # First put: object does not exist yet -> head_object raises 404
    from botocore.exceptions import ClientError

    mock_s3.head_object.side_effect = [
        ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"),
        {"ContentLength": 10},  # Second put: object exists
    ]

    store = BronzeStore(bucket_name="test-bronze", client=mock_s3)
    content = b"sample csv content: product,price\nriz,2500\n"

    # 1. First put
    artifact1 = store.put(
        source_id="wfp_hdx_mdg",
        content=content,
        mime_type="text/csv",
        url="https://example.com/prices.csv",
    )
    assert artifact1.is_new is True
    assert artifact1.content_sha256 == compute_sha256(content)
    assert artifact1.object_key.endswith(".csv")
    assert "wfp_hdx_mdg/" in artifact1.object_key
    assert mock_s3.put_object.call_count == 2  # data + metadata JSON

    # 2. Second put of identical content
    artifact2 = store.put(
        source_id="wfp_hdx_mdg",
        content=content,
        mime_type="text/csv",
        url="https://example.com/prices.csv",
    )
    assert artifact2.is_new is False
    assert artifact2.object_key == artifact1.object_key
    assert artifact2.content_sha256 == artifact1.content_sha256
    # put_object count should still be 2 (no additional upload performed)
    assert mock_s3.put_object.call_count == 2


def test_bronze_store_get_and_metadata():
    """Verify BronzeStore get retrieves content and metadata sidecar."""
    mock_s3 = MagicMock()
    content_bytes = b"sample raw file"
    meta_json_bytes = b'{"source_id": "test_src", "content_sha256": "abc"}'

    def mock_get_object(Bucket, Key):
        if Key.endswith(".meta.json"):
            return {"Body": io.BytesIO(meta_json_bytes)}
        return {"Body": io.BytesIO(content_bytes)}

    mock_s3.get_object.side_effect = mock_get_object
    mock_s3.generate_presigned_url.return_value = "https://s3.example.com/presigned-url"

    store = BronzeStore(bucket_name="test-bronze", client=mock_s3)

    retrieved = store.get("test_src/2026/01/abc.csv")
    assert retrieved == content_bytes

    meta = store.get_metadata("test_src/2026/01/abc.csv")
    assert meta["source_id"] == "test_src"
    assert meta["content_sha256"] == "abc"

    url = store.get_presigned_url("test_src/2026/01/abc.csv")
    assert url == "https://s3.example.com/presigned-url"


def test_bronze_extension_guessing():
    """Verify MIME and URL fallback extension guessing."""
    assert _get_extension_for_mime("application/pdf", "http://example.com/doc") == ".pdf"
    assert _get_extension_for_mime("unknown/type", "http://example.com/doc.xlsx") == ".xlsx"
    assert _get_extension_for_mime("text/markdown", "") == ".md"
    assert _get_extension_for_mime("unknown/bogus", "http://example.com/noext") == ".bin"


def test_bronze_client_error_reraised():
    """Verify unexpected ClientError is re-raised."""
    mock_s3 = MagicMock()
    mock_s3.head_object.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "Internal"}}, "HeadObject"
    )
    store = BronzeStore(bucket_name="test-bronze", client=mock_s3)

    with pytest.raises(ClientError):
        store.put(source_id="test", content=b"123", mime_type="text/plain", url="http://x.com")
