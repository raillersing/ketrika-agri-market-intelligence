"""Resolve exact recorded reference identities without depending on old Silver rows."""

import re
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.core.artifact_identity import ArtifactProcessingIdentity
from ketrika.core.bronze import BronzeStore
from ketrika.core.models.db import SourceRecord
from ketrika.core.rebuild_bronze import LocalBronzeClient


def resolve_snapshot_keys(
    session: Session, records: Sequence[SourceRecord], store: BronzeStore
) -> dict[UUID, tuple[str, str]]:
    """One supported successful processing identity per native price document."""
    identities: dict[UUID, str] = {}
    for record in records:
        if record.source_id != "wb_rtfp_mdg" or record.parser_version != "2.0.0":
            continue
        rows = (
            session.execute(
                text(
                    "SELECT DISTINCT m.processing_key,m.normalizer_version,m.reference_manifest_sha256 "
                    "FROM meta.silver_attempt_member m "
                    "JOIN meta.silver_attempt_result r USING(attempt_id) "
                    "JOIN meta.silver_attempt a USING(attempt_id) "
                    "JOIN meta.ingestion_run i ON i.run_id=a.run_id "
                    "WHERE m.source_record_id=:record AND r.status='success' AND i.status='success' "
                    "AND m.processing_key IS NOT NULL LIMIT 2"
                ),
                {"record": record.source_record_id},
            )
            .mappings()
            .all()
        )
        if not rows:
            continue
        if len(rows) != 1 or rows[0]["normalizer_version"] != "price_normalizer_v2":
            raise ValueError("rebuild_reference_identity_ambiguous_or_unknown")
        row = rows[0]
        identity = ArtifactProcessingIdentity(
            record.source_id,
            record.source_record_id,
            record.content_sha256,
            record.parser_version,
            row["normalizer_version"],
            row["reference_manifest_sha256"],
        )
        if identity.processing_key != row["processing_key"]:
            raise ValueError("rebuild_reference_processing_key_mismatch")
        identities[record.source_record_id] = identity.reference_manifest_sha256
    if not identities:
        return {}
    if isinstance(store.client, LocalBronzeClient):
        keys = list(store.client.objects)
    else:
        keys = []
        pages = store.client.get_paginator("list_objects_v2").paginate(
            Bucket=store.bucket,
            Prefix="reference_manifest/",
            PaginationConfig={"MaxItems": 100001, "PageSize": 1000},
        )
        for page in pages:
            keys.extend(item["Key"] for item in page.get("Contents", []))
            if len(keys) > 100000:
                raise ValueError("rebuild_reference_inventory_too_large")
    resolved: dict[UUID, tuple[str, str]] = {}
    for identifier, digest in identities.items():
        matches = [
            key
            for key in keys
            if re.fullmatch(rf"reference_manifest/\d{{4}}/(?:0[1-9]|1[0-2])/{digest}\.json", key)
        ]
        if len(matches) != 1:
            raise ValueError("rebuild_reference_archive_missing_or_ambiguous")
        resolved[identifier] = (matches[0], digest)
    return resolved
