"""Local copy and dependency wiring; no claim of real offline SQL replay."""

import hashlib
from unittest.mock import MagicMock

import pytest

from ketrika.core.bronze import BronzeStore
from ketrika.core.provenance import MAX_CONTENT_BYTES
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.rebuild_bronze import LocalBronzeClient, LocalBronzeError
from ketrika.pipelines import rebuild


@pytest.fixture
def local_copy(tmp_path):
    content = b"synthetic bronze bytes\n"
    digest = hashlib.sha256(content).hexdigest()
    path = tmp_path / (digest + ".blob")
    path.write_bytes(content)
    inventory = {"synthetic/2025/01/artifact.csv": {"sha256": digest, "size_bytes": len(content)}}
    return tmp_path, path, content, inventory


def test_local_copy_works_for_parser_and_fresh_proof_reader(local_copy):
    root, path, content, inventory = local_copy
    client = LocalBronzeClient(root, "offline-only", inventory)
    store = BronzeStore(bucket_name="offline-only", client=client)
    key = next(iter(inventory))
    assert store.get(key) == content
    assert BronzeProofReader(store).get(key) == content
    assert client.head_object(Bucket="offline-only", Key=key) == {"ContentLength": len(content)}
    assert path.read_bytes() == content
    assert not hasattr(client, "delete_object")
    with pytest.raises(LocalBronzeError, match="read_only"):
        client.put_object(Bucket="offline-only", Key=key, Body=b"changed")


@pytest.mark.parametrize("mutation", ["same_size", "truncated", "missing", "symlink"])
def test_every_get_rechecks_bytes_and_path(local_copy, mutation):
    root, path, content, inventory = local_copy
    client = LocalBronzeClient(root, "offline-only", inventory)
    key = next(iter(inventory))
    assert client.get_object(Bucket="offline-only", Key=key)["Body"].read() == content
    if mutation == "same_size":
        path.write_bytes(b"x" * len(content))
    elif mutation == "truncated":
        path.write_bytes(content[:1])
    elif mutation == "missing":
        path.unlink()  # own ephemeral fixture only, never Bronze
    else:
        alternate = root / "other"
        alternate.write_bytes(content)
        path.unlink()
        path.symlink_to(alternate)
    with pytest.raises(LocalBronzeError):
        client.get_object(Bucket="offline-only", Key=key)


@pytest.mark.parametrize(
    "bucket,key", [("other", "synthetic/2025/01/artifact.csv"), ("offline-only", "unknown")]
)
def test_closed_inventory_and_bucket(local_copy, bucket, key):
    root, _, _, inventory = local_copy
    with pytest.raises(LocalBronzeError, match="not_declared"):
        LocalBronzeClient(root, "offline-only", inventory).get_object(Bucket=bucket, Key=key)


@pytest.mark.parametrize("key", ["../escape", "/absolute", "a\\b", ""])
def test_bad_inventory_key_refused(local_copy, key):
    root, _, _, inventory = local_copy
    with pytest.raises(LocalBronzeError, match="invalid_key"):
        LocalBronzeClient(root, "offline-only", {key: next(iter(inventory.values()))})


@pytest.mark.parametrize(
    "metadata",
    [
        {"sha256": "x" * 64, "size_bytes": 1},
        {"sha256": "a" * 64, "size_bytes": True},
        {"sha256": "a" * 64, "size_bytes": -1},
        {"sha256": "a" * 64, "size_bytes": MAX_CONTENT_BYTES + 1},
        {"sha256": "a" * 64, "size_bytes": 1, "path": "arbitrary"},
    ],
)
def test_invalid_descriptor_refused(local_copy, metadata):
    root, _, _, _ = local_copy
    with pytest.raises(LocalBronzeError):
        LocalBronzeClient(root, "offline-only", {"key": metadata})


def test_empty_inventory_or_symlink_root_refused(local_copy):
    root, _, _, inventory = local_copy
    with pytest.raises(LocalBronzeError):
        LocalBronzeClient(root, "offline-only", {})
    alias = root / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(LocalBronzeError):
        LocalBronzeClient(alias, "offline-only", inventory)


def test_caller_inventory_cannot_redirect_initialized_reader(local_copy):
    root, _, content, inventory = local_copy
    client = LocalBronzeClient(root, "offline-only", inventory)
    key = next(iter(inventory))
    inventory[key]["sha256"] = "a" * 64
    assert client.get_object(Bucket="offline-only", Key=key)["Body"].read() == content


def test_rebuild_passes_same_injected_store_to_gold(local_copy, monkeypatch):
    root, _, _, inventory = local_copy
    store = BronzeStore(
        bucket_name="offline-only", client=LocalBronzeClient(root, "offline-only", inventory)
    )
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []
    readers = []

    def wipe(session, *, reader):
        readers.append(reader)
        return {"gold_tables_truncated": 0, "gold_matviews_refreshed": 0}

    def refresh(session, *, reader):
        readers.append(reader)
        return {
            "count": 12,
            "provenance_state": "empty",
            "source_observations_total": 0,
            "source_observations_valid": 0,
            "source_cell_rate": None,
            "provenance_scope": "test",
        }

    monkeypatch.setattr(
        rebuild, "BronzeStore", lambda: pytest.fail("Default S3 must not be constructed")
    )
    monkeypatch.setattr(rebuild, "wipe_silver_gold_tables", wipe)
    monkeypatch.setattr(rebuild, "refresh_gold_views", refresh)
    result = rebuild.rebuild_database(session=session, bronze_store=store)
    assert result["source_records_total"] == 0  # empty test is not a successful R0.8 reception
    assert len(readers) == 2 and readers[0] is readers[1]
    assert readers[0].store is store


def test_wipe_keeps_injected_reader_for_initial_gold_refresh(local_copy, monkeypatch):
    root, _, _, inventory = local_copy
    store = BronzeStore(
        bucket_name="offline-only", client=LocalBronzeClient(root, "offline-only", inventory)
    )
    reader = BronzeProofReader(store)
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []
    refresh = MagicMock(return_value={"count": 12})
    monkeypatch.setattr(rebuild, "refresh_gold_views", refresh)
    rebuild.wipe_silver_gold_tables(session, reader=reader)
    refresh.assert_called_once_with(session, reader=reader)
