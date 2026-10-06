"""Bronze layer storage management using S3 / MinIO."""

from typing import Any

import boto3
from botocore.client import BaseClient

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
