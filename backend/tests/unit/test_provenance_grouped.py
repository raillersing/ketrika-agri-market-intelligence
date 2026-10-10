"""Grouping and retained payload regressions, no real source acquisition."""

from dataclasses import replace
from uuid import uuid4

from ketrika.core.provenance import ArtifactReference, ObservationClaim, ProvenanceVerifier
from tests.unit.test_provenance import CONTENT, SHA, MemoryReader, proof


class TrackedBytes(bytes):
    alive = 0

    def __new__(cls):
        instance = super().__new__(cls, CONTENT)
        cls.alive += 1
        return instance

    def __del__(self):
        type(self).alive -= 1


class ReleasingReader:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, key: str) -> bytes:
        assert TrackedBytes.alive == 0, "previous object bytes retained before next read"
        self.calls.append(key)
        return TrackedBytes()


def examples():
    refs = [
        ArtifactReference(uuid4(), source, f"{source}/2026/10/{SHA}.json", SHA, "application/json")
        for source in ("source_a", "source_b")
    ]
    first = ObservationClaim(uuid4(), refs[0].source_record_id, proof())
    second = ObservationClaim(uuid4(), refs[1].source_record_id, proof())
    third = replace(first, observation_id=uuid4())
    return {reference.source_record_id: reference for reference in refs}, [first, second, third]


def test_shared_nonadjacent_object_read_once_without_retaining_other_payloads() -> None:
    references, claims = examples()
    reader = ReleasingReader()
    report = ProvenanceVerifier(reader, references).verify(claims)
    assert report.total == report.valid == 3 and report.passed
    assert report.objects_read == report.object_read_attempts == 2
    assert len(reader.calls) == 2 and TrackedBytes.alive == 0
    assert [result.observation_id for result in report.results] == [
        claim.observation_id for claim in claims
    ]


def test_duplicate_uuid_uses_original_order_even_across_object_groups() -> None:
    references, claims = examples()
    claims[1] = replace(claims[1], observation_id=claims[0].observation_id)
    reader = MemoryReader({reference.object_key: CONTENT for reference in references.values()})
    report = ProvenanceVerifier(reader, references).verify(claims)
    assert report.total == 3 and report.valid == 2
    assert report.results[1].reason == "duplicate_observation"
    assert report.objects_read == report.object_read_attempts == 1
