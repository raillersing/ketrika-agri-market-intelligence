"""Run in the existing API container; list/GET only, never mutate objects.

Reads settings without emitting credentials. Fingerprints all retained versions
and delete markers. Object payloads, keys and personal content are not printed.
Use: docker exec -i aiagent-api-1 python - < scripts/bronze-fingerprint-readonly.py
"""

import hashlib
import json

from ketrika.core.bronze import get_s3_client
from ketrika.core.settings import get_settings


def main() -> None:
    client = get_s3_client()
    bucket = get_settings().s3_bucket_bronze
    rows = []
    markers = []
    for page in client.get_paginator("list_object_versions").paginate(Bucket=bucket):
        for version in page.get("Versions", []):
            response = client.get_object(
                Bucket=bucket, Key=version["Key"], VersionId=version["VersionId"]
            )
            digest = hashlib.sha256()
            size = 0
            try:
                for chunk in iter(lambda: response["Body"].read(1048576), b""):
                    digest.update(chunk)
                    size += len(chunk)
            finally:
                response["Body"].close()
            rows.append(
                [
                    version["Key"],
                    version["VersionId"],
                    version["IsLatest"],
                    size,
                    digest.hexdigest(),
                ]
            )
        for marker in page.get("DeleteMarkers", []):
            markers.append([marker["Key"], marker["VersionId"], marker["IsLatest"]])
    payload = {"versions": sorted(rows), "delete_markers": sorted(markers)}
    result = {
        "bucket": bucket,
        "version_count": len(rows),
        "current_objects": sum(row[2] for row in rows),
        "delete_markers": len(markers),
        "total_version_bytes": sum(row[3] for row in rows),
        "sha256": hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
