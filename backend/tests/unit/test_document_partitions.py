"""Document-version identity and real job definitions; not SQL proof."""

from dataclasses import replace
from uuid import uuid4

import pytest

from ketrika.connectors.base import RawArtifact
from ketrika.connectors.document_partitions import document_key, document_keys
from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.stages import BronzeBatch
from ketrika.pipelines.factory import build_document_replay_job


def batch():
    artifact = RawArtifact(
        str(uuid4()),
        "dummy_document/2026/10/" + "a" * 64 + ".csv",
        "a" * 64,
        "text/csv",
        "https://example.invalid/unverified",
        True,
    )
    return BronzeBatch("dummy_document", uuid4(), "fixture-v1", (artifact,))


def test_identity_independent_of_run_and_is_new_but_not_document_or_version():
    original = batch()
    key = document_key(original, original.artifacts[0])
    assert document_keys(original) == (key,)
    retried = replace(
        original,
        ingestion_run_id=uuid4(),
        artifacts=(replace(original.artifacts[0], is_new=False),),
    )
    assert document_key(retried, retried.artifacts[0]) == key
    assert (
        document_key(replace(original, parser_version="fixture-v2"), original.artifacts[0]) != key
    )
    revised = replace(
        original, artifacts=(replace(original.artifacts[0], content_sha256="b" * 64),)
    )
    assert document_key(revised, revised.artifacts[0]) != key
    different_parent = replace(
        original, artifacts=(replace(original.artifacts[0], source_record_id=str(uuid4())),)
    )
    assert document_key(different_parent, different_parent.artifacts[0]) != key


def test_unknown_member_refused():
    original = batch()
    with pytest.raises(ValueError, match="document_partition_outside_batch"):
        document_key(original, replace(original.artifacts[0], source_record_id=str(uuid4())))


def test_actual_document_job_has_no_bronze_step():
    job = build_document_replay_job(DummyCsvConnector)
    assert job.name == "dummy_csv__document_replay"
    assert job.partitions_def.name == "dummy_csv__document_versions"
    assert {node.name for node in job.graph.node_defs} == {"dummy_csv__replay_recorded_document"}


def test_actual_registered_jobs_match_eligible_sources_without_new_assets():
    from ketrika.pipelines.definitions import document_replay_jobs, source_inventory

    assert {job.name for job in document_replay_jobs} == {
        f"{entry.source_id}__document_replay" for entry in source_inventory if entry.included
    }
    assert len(document_replay_jobs) == 5
    assert "instat_nipc__document_replay" not in {job.name for job in document_replay_jobs}
