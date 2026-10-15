"""Prepared transaction-bound configured references; not institutional provenance."""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session, SessionTransaction

from ketrika.core.bronze import BronzeStore
from ketrika.core.models.db import Location, LocationAlias, Product, ProductAlias, UnitConversion
from ketrika.core.reference_archive import ArchivedReferenceManifest, archive_reference_manifest
from ketrika.core.reference_lock import lock_reference_manifest
from ketrika.core.reference_manifest import ReferenceManifest, read_reference_manifest

_REFERENCE_MODELS = (Product, ProductAlias, Location, LocationAlias, UnitConversion)


@dataclass(frozen=True)
class ReferenceSnapshot:
    manifest: ReferenceManifest = field(repr=False)
    archive: ArchivedReferenceManifest
    _session: Session = field(repr=False)
    _transaction: SessionTransaction = field(repr=False)


def require_clean_reference_state(session: Session) -> None:
    if any(
        isinstance(row, _REFERENCE_MODELS)
        for collection in (session.new, session.dirty, session.deleted)
        for row in collection
    ):
        raise ValueError("normalization_reference_changes_pending")


def prepare_reference_snapshot(session: Session, store: BronzeStore) -> ReferenceSnapshot:
    """Caller retains reference locks and owns commit/rollback."""
    require_clean_reference_state(session)
    if session.in_nested_transaction():
        raise ValueError("normalization_reference_nested_transaction")
    manifest = lock_reference_manifest(session)
    transaction = session.get_transaction()
    if transaction is None or not transaction.is_active:
        raise ValueError("normalization_reference_transaction_required")
    if not manifest.row_count:
        raise ValueError("normalization_reference_manifest_empty")
    archive = archive_reference_manifest(store, manifest)
    return ReferenceSnapshot(manifest, archive, session, transaction)


def reference_snapshot_evidence(session: Session, snapshot: ReferenceSnapshot) -> dict[str, Any]:
    if (
        not isinstance(snapshot, ReferenceSnapshot)
        or snapshot._session is not session
        or session.get_transaction() is not snapshot._transaction
        or not snapshot._transaction.is_active
        or session.in_nested_transaction()
    ):
        raise ValueError("normalization_reference_context_invalid")
    require_clean_reference_state(session)
    if read_reference_manifest(session) != snapshot.manifest:
        raise ValueError("normalization_reference_manifest_changed")
    if (
        snapshot.archive.sha256,
        snapshot.archive.row_count,
        snapshot.archive.counts,
    ) != (snapshot.manifest.sha256, snapshot.manifest.row_count, snapshot.manifest.counts):
        raise ValueError("normalization_reference_archive_mismatch")
    return {
        "version": "reference_manifest_v1",
        "sha256": snapshot.archive.sha256,
        "object_key": snapshot.archive.object_key,
        "row_count": snapshot.archive.row_count,
        "counts": dict(snapshot.archive.counts),
        "scope": "transaction_bound_configured_references_not_institutional_provenance",
        "source_verified": False,
    }


def reopen_reference_snapshot(
    session: Session, store: BronzeStore, object_key: str, expected_sha256: str
) -> ReferenceSnapshot:
    """Read an existing archive against locked references; never PUT during replay."""
    from ketrika.core.provenance_bronze import BronzeProofReader

    require_clean_reference_state(session)
    if session.in_nested_transaction():
        raise ValueError("normalization_reference_nested_transaction")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or not re.fullmatch(
        rf"reference_manifest/\d{{4}}/(?:0[1-9]|1[0-2])/{expected_sha256}\.json", object_key
    ):
        raise ValueError("normalization_reference_archive_invalid")
    manifest = lock_reference_manifest(session)
    transaction = session.get_transaction()
    if transaction is None or not transaction.is_active or not manifest.row_count:
        raise ValueError("normalization_reference_transaction_required")
    if manifest.sha256 != expected_sha256:
        raise ValueError("normalization_reference_manifest_changed")
    content = BronzeProofReader(store).get(object_key)
    if content != manifest.content or hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError("normalization_reference_archive_mismatch")
    archive = ArchivedReferenceManifest(
        manifest.sha256, object_key, manifest.row_count, manifest.counts
    )
    return ReferenceSnapshot(manifest, archive, session, transaction)
