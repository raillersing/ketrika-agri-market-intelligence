"""Prepared context identity/ordering on inert sessions; not SQL qualification."""

from dataclasses import replace
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session, SessionTransaction

from ketrika.core.bronze import BronzeStore
from ketrika.core.models.db import Location, LocationAlias, Product, ProductAlias, UnitConversion
from ketrika.core.reference_archive import ArchivedReferenceManifest
from ketrika.core.reference_manifest import ReferenceRow, build_reference_manifest
from ketrika.normalize.reference_snapshot import (
    ReferenceSnapshot,
    prepare_reference_snapshot,
    reference_snapshot_evidence,
    reopen_reference_snapshot,
)


def context():
    session = Mock(spec=Session)
    session.new, session.dirty, session.deleted = [], [], []
    session.in_nested_transaction.return_value = False
    transaction = Mock(spec=SessionTransaction)
    transaction.is_active = True
    session.get_transaction.return_value = transaction
    manifest = build_reference_manifest([ReferenceRow("product", "synthetic", "{}")])
    archive = ArchivedReferenceManifest(
        manifest.sha256,
        f"reference_manifest/2026/10/{manifest.sha256}.json",
        manifest.row_count,
        manifest.counts,
    )
    return session, ReferenceSnapshot(manifest, archive, session, transaction)


def test_prepare_locks_then_archives_same_manifest_without_commit():
    session, snapshot = context()
    store = Mock(spec=BronzeStore)
    events = []

    def lock(actual):
        assert actual is session
        events.append("lock")
        return snapshot.manifest

    def archive(actual_store, actual_manifest):
        assert actual_store is store and actual_manifest is snapshot.manifest
        events.append("archive")
        return snapshot.archive

    with (
        patch("ketrika.normalize.reference_snapshot.lock_reference_manifest", side_effect=lock),
        patch(
            "ketrika.normalize.reference_snapshot.archive_reference_manifest", side_effect=archive
        ),
    ):
        assert prepare_reference_snapshot(session, store) == snapshot
    assert events == ["lock", "archive"]
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


@pytest.mark.parametrize("collection", ["new", "dirty", "deleted"])
@pytest.mark.parametrize("model", [Product, ProductAlias, Location, LocationAlias, UnitConversion])
def test_pending_reference_changes_refuse_before_lock_and_archive(collection, model):
    session, _ = context()
    setattr(session, collection, [model()])
    with patch("ketrika.normalize.reference_snapshot.lock_reference_manifest") as lock:
        with pytest.raises(ValueError, match="^normalization_reference_changes_pending$"):
            prepare_reference_snapshot(session, Mock(spec=BronzeStore))
    lock.assert_not_called()


@pytest.mark.parametrize("variant", ["nested", "absent", "inactive", "empty"])
def test_prepare_refuses_without_root_transaction_and_nonempty_snapshot(variant):
    session, snapshot = context()
    manifest = snapshot.manifest
    if variant == "nested":
        session.in_nested_transaction.return_value = True
    elif variant == "absent":
        session.get_transaction.return_value = None
    elif variant == "inactive":
        snapshot._transaction.is_active = False
    else:
        manifest = build_reference_manifest([])
    with (
        patch(
            "ketrika.normalize.reference_snapshot.lock_reference_manifest", return_value=manifest
        ),
        patch("ketrika.normalize.reference_snapshot.archive_reference_manifest") as archive,
    ):
        with pytest.raises(ValueError, match="^normalization_reference_"):
            prepare_reference_snapshot(session, Mock(spec=BronzeStore))
    archive.assert_not_called()


@pytest.mark.parametrize(
    "variant", ["other_session", "other_transaction", "inactive", "nested", "untrusted_dict"]
)
def test_context_identity_refuses_before_manifest_query(variant):
    session, snapshot = context()
    candidate = snapshot
    if variant == "other_session":
        session = context()[0]
    elif variant == "other_transaction":
        session.get_transaction.return_value = Mock(spec=SessionTransaction)
    elif variant == "inactive":
        snapshot._transaction.is_active = False
    elif variant == "nested":
        session.in_nested_transaction.return_value = True
    else:
        candidate = {"sha256": snapshot.manifest.sha256}
    with patch("ketrika.normalize.reference_snapshot.read_reference_manifest") as read:
        with pytest.raises(ValueError, match="^normalization_reference_context_invalid$"):
            reference_snapshot_evidence(session, candidate)
    read.assert_not_called()


@pytest.mark.parametrize("variant", ["changed_manifest", "mismatched_archive"])
def test_changed_catalogue_or_archive_never_returns_evidence(variant):
    session, snapshot = context()
    manifest = snapshot.manifest
    if variant == "changed_manifest":
        manifest = build_reference_manifest([ReferenceRow("product", "other", "{}")])
    else:
        snapshot = replace(snapshot, archive=replace(snapshot.archive, sha256="0" * 64))
    with patch(
        "ketrika.normalize.reference_snapshot.read_reference_manifest", return_value=manifest
    ):
        with pytest.raises(ValueError, match="^normalization_reference_"):
            reference_snapshot_evidence(session, snapshot)


def test_evidence_is_computed_from_verified_context_not_collected_fields():
    session, snapshot = context()
    with patch(
        "ketrika.normalize.reference_snapshot.read_reference_manifest",
        return_value=snapshot.manifest,
    ) as read:
        evidence = reference_snapshot_evidence(session, snapshot)
    read.assert_called_once_with(session)
    assert evidence["sha256"] == snapshot.manifest.sha256
    assert evidence["object_key"] == snapshot.archive.object_key
    assert evidence["counts"]["product"] == 1
    assert evidence["source_verified"] is False
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "variant", ["valid", "bytes", "references", "nested", "transaction", "path"]
)
def test_reopen_reads_exact_archive_without_writing(variant):
    session, snapshot = context()
    store = Mock(spec=BronzeStore)
    key = snapshot.archive.object_key
    if variant == "nested":
        session.in_nested_transaction.return_value = True
    elif variant == "transaction":
        session.get_transaction.return_value = None
    elif variant == "path":
        key = key.replace("/10/", "/13/")
    manifest = snapshot.manifest
    if variant == "references":
        manifest = build_reference_manifest([ReferenceRow("product", "different", "{}")])
    with (
        patch(
            "ketrika.normalize.reference_snapshot.lock_reference_manifest", return_value=manifest
        ),
        patch("ketrika.core.provenance_bronze.BronzeProofReader") as reader,
    ):
        reader.return_value.get.return_value = (
            b"corrupt" if variant == "bytes" else snapshot.manifest.content
        )
        if variant == "valid":
            assert (
                reopen_reference_snapshot(session, store, key, snapshot.manifest.sha256) == snapshot
            )
            reader.return_value.get.assert_called_once_with(key)
        else:
            with pytest.raises(ValueError, match="normalization_reference_"):
                reopen_reference_snapshot(session, store, key, snapshot.manifest.sha256)
    store.put.assert_not_called()
    session.commit.assert_not_called()
