"""Revalidate native WB replay receipts against the actual read-only corpus and Bronze."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from ketrika.core.bronze import BronzeStore
from ketrika.core.corpus import load_manifest
from ketrika.core.external_corpus import _directory, _readonly
from ketrika.core.models.db import PriceObservation
from ketrika.core.provenance import ArtifactReference, ProvenanceVerifier
from ketrika.core.provenance_audit import bind_observation
from ketrika.core.qualification import QualificationSafetyError
from ketrika.core.qualification_reports import load_json_report
from ketrika.core.rebuild_bronze import LocalBronzeClient
from ketrika.core.rebuild_manifest import OBS_COLUMNS, _digest, compare_manifests
from ketrika.pipelines.rebuild_qualification import bronze_inventory_fingerprint

PRODUCER = "wb-offline-replay-v1"
SOURCE = "wb_rtfp_mdg"
PRICE = "obs.price_observation"
GOLD = "gold.price_obs_current"
NETWORK = {"interfaces": ["lo"], "external_ipv4_routes": 0}


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise QualificationSafetyError(reason)


def _typed(value: list[Any]) -> Any:
    tag = value[0]
    if tag == "null":
        return None
    item = value[1]
    if tag in ("text", "bool"):
        return item
    if tag == "int":
        return int(item)
    if tag == "decimal":
        return Decimal(item)
    if tag == "float":
        return float(item)
    if tag == "uuid":
        return UUID(item)
    if tag == "date":
        return date.fromisoformat(item)
    if tag == "datetime":
        return datetime.fromisoformat(item)
    if tag == "array":
        return [_typed(part) for part in item]
    if tag == "object":
        return {key: _typed(part) for key, part in item}
    raise QualificationSafetyError("external_unknown_manifest_type")


def _protected(receipt: dict[str, Any]) -> dict[str, Any]:
    first, second = receipt["protected_before"], receipt["protected_after"]
    tables = first["tables"]
    _require(first == second, "external_protected_changed")
    _require(first["sha256"] == _digest(tables), "external_protected_hash_mismatch")
    for table in tables.values():
        _require(
            table["count"] == len(table["rows"]),
            "external_protected_count_mismatch",
        )
    return first


def _native(receipt: dict[str, Any], *, negative: bool) -> dict[str, Any]:
    _require(receipt["version"] == 2, "external_replay_version")
    _require(receipt["database"] == "ketrika_rebuild_qualification", "external_replay_db")
    _require(receipt["uid"] == 1000, "external_replay_uid")
    _require(
        receipt["network_before"] == receipt["network_after"] == NETWORK,
        "external_replay_network",
    )
    _require(receipt["replay_passed"] is not negative, "external_replay_result")
    stats = receipt["replay_stats"]
    _require(
        stats["source_records_total"] == stats["source_records_replayed"] == 3
        and stats["source_records_skipped"] == stats["records_rejected"] == 0,
        "external_replay_incomplete",
    )
    _protected(receipt)
    _require(
        receipt["bronze_inventory_before"] == receipt["bronze_inventory_after"]
        and receipt["bronze_inventory_verified"] is True,
        "external_bronze_changed",
    )
    before, after = receipt["before"], receipt["after"]
    diff = compare_manifests(before, after)
    _require(diff == receipt["diff"], "external_diff_mismatch")
    _require(diff["content_identical"] is not negative, "external_content_identity")
    for snapshot in (before, after):
        tables = snapshot["tables"]
        _require(
            tables[PRICE]["count"] == 163
            and tables[GOLD]["count"] == 82
            and all(tables[name]["count"] == 0 for name in OBS_COLUMNS if name != PRICE),
            "external_replay_scope",
        )
    if negative:
        _require(
            receipt["counterproof_passed"] is True
            and receipt["deliberately_changed_values"] == 1
            and set(diff["changed_tables"]) == {PRICE},
            "external_counterproof_missing",
        )
        old = before["tables"][PRICE]["rows"]
        new = after["tables"][PRICE]["rows"]
        removed = [row for row in old if row not in new]
        added = [row for row in new if row not in old]
        _require(
            len(removed) == len(added) == 1
            and removed[0]["superseded_by"] != ["null"]
            and added[0]["superseded_by"] == removed[0]["superseded_by"]
            and added[0]["source_record_id"] == removed[0]["source_record_id"]
            and added[0]["period_start"] == removed[0]["period_start"]
            and added[0]["price_raw"] != removed[0]["price_raw"],
            "external_counterproof_scope",
        )
    return diff


def _references(
    packet: Path, positive: dict[str, Any], client: LocalBronzeClient
) -> dict[UUID, ArtifactReference]:
    entries = load_manifest(packet)["entries"]
    originals = {
        item["sha256"]: item
        for item in entries
        if item["origin"]["kind"] == "official_acquisition"
    }
    records = [
        json.loads(raw)
        for raw in positive["protected_before"]["tables"]["meta.source_record"]["rows"]
    ]
    _require(
        len(records) == len(originals) == 3
        and {row["content_sha256"] for row in records} == set(originals),
        "external_source_record_inventory",
    )
    references = {}
    for row in records:
        digest = row["content_sha256"]
        entry = originals[digest]
        acquisition = load_json_report(packet / entry["origin"]["reference"])
        mime = acquisition["mime_type"].split(";")[0].strip().lower()
        _require(
            row["source_id"] == acquisition["source_id"] == SOURCE
            and row["source_url"] == acquisition["source_url"]
            and row["retrieved_via"] == "direct"
            and row["http_status"] == acquisition["http_status"] == 200
            and row["mime_type"] == mime
            and datetime.fromisoformat(row["fetched_at"])
            == datetime.fromisoformat(acquisition["fetched_at"])
            and client.objects.get(row["object_key"]) == (digest, entry["size_bytes"]),
            "external_source_record_mismatch",
        )
        identity = UUID(row["source_record_id"])
        references[identity] = ArtifactReference(
            identity, SOURCE, row["object_key"], digest, mime
        )
    _require(len(references) == 3, "external_duplicate_source_record")
    return references


def _claims(snapshot: dict[str, Any]) -> list[Any]:
    rows = snapshot["tables"][PRICE]["rows"]
    claims = []
    stable = set()
    current = set()
    superseded = []
    for row in rows:
        identity = row["observation_id"]
        business = {
            key: val for key, val in row.items() if key not in {"observation_id", "superseded_by"}
        }
        _require(
            identity == ["observation", PRICE, _digest(business)],
            "external_observation_identity",
        )
        digest = identity[2]
        _require(digest not in stable, "external_duplicate_observation")
        stable.add(digest)
        if row["superseded_by"] == ["null"]:
            current.add(digest)
        else:
            superseded.append(row["superseded_by"])
        values = {key: _typed(val) for key, val in business.items()}
        value = PriceObservation(observation_id=UUID(digest[:32]), **values)
        claims.append(bind_observation("price_observation", value))
    _require(
        len(current) == 82
        and len(superseded) == 81
        and all(link[:2] == ["observation", PRICE] and link[2] in current for link in superseded),
        "external_revision_lineage",
    )
    gold = snapshot["tables"][GOLD]["rows"]
    _require(
        {row["observation_id"][2] for row in gold} == current
        and all(row["observation_id"][:2] == ["observation", PRICE] for row in gold),
        "external_gold_lineage",
    )
    return claims


def verify_external_replay(
    document: dict[str, Any], packet: Path, bronze: Path, packet_sha256: str
) -> dict[str, Any]:
    """Compute native manifest equality and cell provenance, not a report flag."""
    _require(document["packet_sha256"] == packet_sha256, "external_replay_packet_mismatch")
    positive, negative = document["positive"], document["negative"]
    diff = _native(positive, negative=False)
    _native(negative, negative=True)
    _require(
        positive["before"] == negative["before"]
        and positive["protected_before"] == negative["protected_before"]
        and positive["bronze_inventory_before"] == negative["bronze_inventory_before"],
        "external_counterproof_baseline_mismatch",
    )
    base = _directory(bronze)
    _readonly(base)
    inventory_path = base / "inventory.json"
    _require(not inventory_path.is_symlink(), "external_bronze_symlink")
    _readonly(inventory_path)
    inventory = load_json_report(inventory_path)["objects"]
    client = LocalBronzeClient(base, "wb-replay-original-copy", inventory)
    store = BronzeStore(bucket_name=client.bucket, client=client)
    actual = bronze_inventory_fingerprint(store)
    _require(
        actual == positive["bronze_inventory_before"] and actual["count"] == 4,
        "external_bronze_inventory_mismatch",
    )
    for digest, _ in client.objects.values():
        _readonly(base / (digest + ".blob"))
    references = _references(packet, positive, client)
    reference_keys = set(client.objects) - {ref.object_key for ref in references.values()}
    _require(
        len(reference_keys) == 1 and next(iter(reference_keys)).startswith("reference_manifest/"),
        "external_reference_snapshot_missing",
    )
    claims = _claims(positive["before"])
    report = ProvenanceVerifier(store, references).verify(claims)
    _require(report.passed and report.valid == report.total == 163, "external_cell_audit_failed")
    return {
        "observations": report.total,
        "valid": report.valid,
        "objects_read": report.objects_read,
        "before_sha256": diff["before_sha256"],
        "after_sha256": diff["after_sha256"],
        "content_identical": True,
        "network_requests": 0,
        "counterproof_detected": True,
        "packet_sha256": packet_sha256,
    }
