"""Bronze layer storage management using S3 / MinIO (SPECS §10).

Bronze artifacts are content-addressed by SHA-256 and immutable.
No deletion API is exposed.
"""

import hashlib
import json
import mimetypes
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from ketrika.core.settings import get_settings

_s3_client: BaseClient | None = None


def get_s3_client() -> Any:
    """Return configured boto3 S3 client."""
    global _s3_client
    if _s3_client is None:
        settings = get_settings()
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
    return _s3_client


def check_s3_connection() -> bool:
    """Check connectivity to S3 / MinIO storage."""
    try:
        client = get_s3_client()
        client.list_buckets()
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class BronzeArtifact:
    """Descriptor of a stored Bronze artifact."""

    object_key: str
    content_sha256: str
    mime_type: str
    url: str
    fetched_at: datetime
    is_new: bool
    size_bytes: int


def compute_sha256(content: bytes) -> str:
    """Compute hex SHA-256 checksum of raw bytes."""
    return hashlib.sha256(content).hexdigest()


def verify_sha256(content: bytes, expected_sha256: str) -> bool:
    """Verify that content matches expected SHA-256 checksum."""
    return compute_sha256(content) == expected_sha256.lower()


def _get_extension_for_mime(mime_type: str | None, url: str | None = None) -> str:
    """Determine file extension from MIME type or URL."""
    mime_map = {
        "application/pdf": ".pdf",
        "text/csv": ".csv",
        "application/json": ".json",
        "text/html": ".html",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.ms-excel": ".xls",
        "text/plain": ".txt",
        "image/png": ".png",
        "image/jpeg": ".jpg",
    }
    if mime_type and mime_type.lower() in mime_map:
        return mime_map[mime_type.lower()]

    if url:
        path = url.split("?")[0].split("#")[0]
        if "." in path:
            ext = "." + path.rsplit(".", 1)[1].lower()
            if len(ext) <= 5:
                return ext

    if mime_type:
        guessed = mimetypes.guess_extension(mime_type)
        if guessed:
            return guessed

    return ".bin"


class BronzeStore:
    """Immutable object store for raw Bronze artifacts in S3 / MinIO."""

    def __init__(self, bucket_name: str | None = None, client: Any = None) -> None:
        settings = get_settings()
        self.bucket = bucket_name or settings.s3_bucket_bronze
        self.client = client or get_s3_client()

    def put(
        self,
        source_id: str,
        content: bytes,
        mime_type: str,
        url: str,
        retrieved_via: str = "direct",
        http_headers: dict[str, str] | None = None,
        http_status: int = 200,
        user_agent: str | None = None,
        fetched_at: datetime | None = None,
    ) -> BronzeArtifact:
        """Store raw content in Bronze bucket idempotently by content SHA-256.

        SPECS §10: s3://bronze/{source_id}/{yyyy}/{mm}/{sha256}.{ext}
        """
        now = fetched_at or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        sha = compute_sha256(content)
        ext = _get_extension_for_mime(mime_type, url)
        yyyy = now.strftime("%Y")
        mm = now.strftime("%m")

        object_key = f"{source_id}/{yyyy}/{mm}/{sha}{ext}"
        meta_key = f"{source_id}/{yyyy}/{mm}/{sha}.meta.json"

        # Check idempotence: check if object already exists
        is_new = True
        try:
            self.client.head_object(Bucket=self.bucket, Key=object_key)
            is_new = False
        except ClientError as e:
            # 404 indicates object does not exist yet
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code not in ("404", "NoSuchKey"):
                raise

        if is_new:
            # 1. Put raw content
            self.client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=content,
                ContentType=mime_type,
            )

            # 2. Put metadata sidecar JSON
            meta_payload = {
                "source_id": source_id,
                "url": url,
                "content_sha256": sha,
                "size_bytes": len(content),
                "mime_type": mime_type,
                "fetched_at": now.isoformat(),
                "http_status": http_status,
                "http_headers": http_headers or {},
                "retrieved_via": retrieved_via,
                "user_agent": user_agent or get_settings().bot_user_agent,
            }
            self.client.put_object(
                Bucket=self.bucket,
                Key=meta_key,
                Body=json.dumps(meta_payload, indent=2).encode("utf-8"),
                ContentType="application/json",
            )

        return BronzeArtifact(
            object_key=object_key,
            content_sha256=sha,
            mime_type=mime_type,
            url=url,
            fetched_at=now,
            is_new=is_new,
            size_bytes=len(content),
        )

    def get(self, object_key: str) -> bytes:
        """Retrieve raw bytes of an artifact by object key."""
        resp = self.client.get_object(Bucket=self.bucket, Key=object_key)
        content: bytes = resp["Body"].read()
        return content

    def get_metadata(self, object_key: str) -> dict[str, Any]:
        """Retrieve metadata dictionary associated with artifact."""
        base_path = object_key.rsplit(".", 1)[0]
        meta_key = f"{base_path}.meta.json"
        resp = self.client.get_object(Bucket=self.bucket, Key=meta_key)
        data: dict[str, Any] = json.loads(resp["Body"].read().decode("utf-8"))
        return data

    def get_presigned_url(self, object_key: str, expires_in: int = 3600) -> str:
        """Generate presigned S3 GET URL for the artifact."""
        url: str = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": object_key},
            ExpiresIn=expires_in,
        )
        return url
