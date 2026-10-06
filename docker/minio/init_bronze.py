"""Initialize bronze bucket with versioning on MinIO storage."""

import os
import sys
import time

import boto3
from botocore.exceptions import ClientError


def main() -> None:
    """Ensure bronze bucket exists and has versioning enabled."""
    endpoint = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
    access_key = os.getenv("S3_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("S3_SECRET_KEY", "minioadmin")
    bucket = os.getenv("S3_BUCKET_BRONZE", "bronze")
    region = os.getenv("S3_REGION", "auto")
    if region == "auto":
        region = "us-east-1"

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )

    max_retries = 15
    for attempt in range(1, max_retries + 1):
        try:
            try:
                s3.head_bucket(Bucket=bucket)
                print(f"[minio-init] Bucket '{bucket}' already exists.")
            except ClientError:
                s3.create_bucket(Bucket=bucket)
                print(f"[minio-init] Bucket '{bucket}' successfully created.")

            s3.put_bucket_versioning(
                Bucket=bucket,
                VersioningConfiguration={"Status": "Enabled"},
            )
            print(f"[minio-init] Versioning enabled on bucket '{bucket}'.")
            return
        except Exception as exc:
            print(f"[minio-init] Attempt {attempt}/{max_retries} failed: {exc}. Retrying in 2s...")
            time.sleep(2)

    sys.exit(1)


if __name__ == "__main__":
    main()
