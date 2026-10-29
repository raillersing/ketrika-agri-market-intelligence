"""Copy a verified local export into a new, dedicated, versioned MinIO bucket."""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def payload(root, descriptor):
    digest = descriptor["sha256"]
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("Invalid source object digest")
    size = descriptor["size_bytes"]
    if type(size) is not int or not 0 <= size <= 256 * 1024 * 1024:
        raise ValueError("Invalid source object size")
    path = root / (digest + ".blob")
    if root.is_symlink() or path.is_symlink() or not path.is_file():
        raise ValueError("Unsafe or missing exported object")
    with path.open("rb") as stream:
        content = stream.read(size + 1)
    if len(content) != size or hashlib.sha256(content).hexdigest() != digest:
        raise ValueError("Exported object changed")
    return content


def inventory(client, bucket):
    entries = []
    for page in client.get_paginator("list_object_versions").paginate(Bucket=bucket):
        if page.get("DeleteMarkers"):
            raise ValueError("Delete markers are not allowed in the clone")
        for version in page.get("Versions", []):
            entries.append(
                {
                    "key": version["Key"],
                    "version_id": version["VersionId"],
                    "latest": version["IsLatest"],
                    "size_bytes": version["Size"],
                }
            )
            if len(entries) > 10000:
                raise ValueError("Clone inventory budget exceeded")
    return sorted(entries, key=lambda entry: (entry["key"], entry["version_id"]))


def verify_objects(client, bucket, mapping):
    validate_budget(mapping)
    if client.get_bucket_versioning(Bucket=bucket).get("Status") != "Enabled":
        raise ValueError("Clone versioning is unavailable")
    for item in mapping:
        if not isinstance(item["clone_version_id"], str) or not item["clone_version_id"]:
            raise ValueError("Missing clone version identity")
        if (
            not isinstance(item["sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is None
        ):
            raise ValueError("Invalid clone digest")
    for item in mapping:
        response = client.get_object(
            Bucket=bucket, Key=item["key"], VersionId=item["clone_version_id"]
        )
        try:
            content = response["Body"].read(item["size_bytes"] + 1)
        finally:
            response["Body"].close()
        if (
            len(content) != item["size_bytes"]
            or hashlib.sha256(content).hexdigest() != item["sha256"]
        ):
            raise ValueError("Clone object does not match the original version")
    current = inventory(client, bucket)
    expected = sorted(
        [
            {
                "key": item["key"],
                "version_id": item["clone_version_id"],
                "latest": item["latest"],
                "size_bytes": item["size_bytes"],
            }
            for item in mapping
        ],
        key=lambda item: (item["key"], item["version_id"]),
    )
    if current != expected:
        raise ValueError("Clone version inventory mismatch")
    return current


def validate_budget(mapping):
    if len(mapping) > 10000 or any(
        type(item["size_bytes"]) is not int or item["size_bytes"] < 0 for item in mapping
    ):
        raise ValueError("Invalid clone byte/version budget")
    if sum(item["size_bytes"] for item in mapping) > 256 * 1024 * 1024:
        raise ValueError("Clone byte/version budget exceeded")


def copy(client, bucket, root, source):
    if (
        source["versioning"] != "Enabled"
        or not source["unchanged_during_audit"]
        or source["invalid_objects"]
    ):
        raise ValueError("Original object inventory is not stable and verified")
    if any(item["delete_marker"] for item in source["inventory_after"]):
        raise ValueError("Export with delete markers requires separate review")
    if len(source["objects"]) != len(source["inventory_after"]):
        raise ValueError("Original version inventory is incomplete")
    validate_budget(source["objects"])
    expected_versions = sorted(
        (item["key"], item["version_id"], item["latest"], item["size_bytes"])
        for item in source["inventory_after"]
    )
    actual_versions = sorted(
        (item["key"], item["version_id"], item["latest"], item["size_bytes"])
        for item in source["objects"]
    )
    if actual_versions != expected_versions:
        raise ValueError("Original version descriptors do not match the inventory")
    originals = sorted(
        source["objects"],
        key=lambda item: (item["key"], item["latest"], item["modified"], item["version_id"]),
    )
    contents = [(original, payload(root, original)) for original in originals]
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as error:
        if error.response["Error"]["Code"] not in {"404", "NoSuchBucket"}:
            raise
    else:
        raise ValueError("Clone bucket already exists; refusing to append or overwrite")
    client.create_bucket(Bucket=bucket)
    client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
    if client.get_bucket_versioning(Bucket=bucket).get("Status") != "Enabled":
        raise ValueError("Clone versioning is unavailable")
    mapping = []
    # Preserve every version, placing the original latest version last per key.
    for original, content in contents:
        response = client.put_object(
            Bucket=bucket,
            Key=original["key"],
            Body=content,
            Metadata={
                "original-version-id": original["version_id"],
                "original-sha256": original["sha256"],
            },
        )
        version_id = response.get("VersionId")
        if not version_id:
            raise ValueError("Clone did not return a version identity")
        mapping.append(
            {
                "key": original["key"],
                "original_version_id": original["version_id"],
                "clone_version_id": version_id,
                "sha256": original["sha256"],
                "size_bytes": original["size_bytes"],
                "latest": original["latest"],
            }
        )
    checked = verify_objects(client, bucket, mapping)
    return {
        "passed": True,
        "bucket": bucket,
        "version_mapping": mapping,
        "inventory": checked,
        "scope": "byte-identical versioned local clone; new native version identities",
        "source_qualified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("copy", "verify"))
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--objects", type=Path)
    parser.add_argument("--bucket", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"ketrika-au08-bronze-[a-z0-9-]+", args.bucket):
        parser.error("A dedicated AU08 clone bucket is required")
    if os.environ.get("KETRIKA_CLONE_COPY_CONFIRM") != args.bucket:
        parser.error("Explicit clone bucket confirmation is required")
    client = boto3.client(
        "s3",
        endpoint_url="http://clone-minio:9000",
        aws_access_key_id=os.environ["KETRIKA_CLONE_S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["KETRIKA_CLONE_S3_SECRET_KEY"],
        region_name="us-east-1",
    )
    document = json.loads(args.input.read_text())
    if args.action == "copy":
        if args.objects is None:
            parser.error("A local original export is required")
        result = copy(client, args.bucket, args.objects, document)
    else:
        if document["bucket"] != args.bucket or document["passed"] is not True:
            raise ValueError("Invalid original clone receipt")
        current = verify_objects(client, args.bucket, document["version_mapping"])
        if current != document["inventory"]:
            raise ValueError("Clone changed since its first receipt")
        result = {
            "passed": True,
            "bucket": args.bucket,
            "versions_verified": len(current),
            "inventory_unchanged": True,
            "source_qualified": False,
        }
    with args.output.open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)


if __name__ == "__main__":
    main()
