"""Pure version identity tests; no database, Bronze, or market qualification."""

import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from uuid import UUID

import pytest

from ketrika.core.artifact_identity import ArtifactProcessingIdentity


def example():
    return ArtifactProcessingIdentity(
        "fixture_identity",
        UUID("11111111-1111-1111-1111-111111111111"),
        "a" * 64,
        "1.0.0",
        "1.0.0",
        "b" * 64,
    )


def test_versioned_identity_has_exact_canonical_encoding():
    expected = [
        "artifact_processing_identity_v1",
        "fixture_identity",
        "11111111-1111-1111-1111-111111111111",
        "a" * 64,
        "1.0.0",
        "1.0.0",
        "b" * 64,
    ]
    digest = hashlib.sha256(
        json.dumps(expected, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    assert example().processing_key == digest
    assert example().processing_key == example().processing_key


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", "fixture_other"),
        ("source_record_id", UUID("22222222-2222-2222-2222-222222222222")),
        ("content_sha256", "c" * 64),
        ("parser_version", "2.0.0"),
        ("normalizer_version", "2.0.0"),
        ("reference_manifest_sha256", "d" * 64),
    ],
)
def test_every_declared_version_dimension_changes_processing_key(field, value):
    original = example()
    assert replace(original, **{field: value}).processing_key != original.processing_key


def test_run_membership_is_separate_from_processing_identity():
    identity = example()
    first = UUID("33333333-3333-3333-3333-333333333333")
    second = UUID("44444444-4444-4444-4444-444444444444")
    assert identity.run_member_key(first) == identity.run_member_key(first)
    assert identity.run_member_key(first) != identity.run_member_key(second)
    assert identity.run_member_key(first) != identity.processing_key
    with pytest.raises(FrozenInstanceError):
        identity.parser_version = "2.0.0"


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", ""),
        ("source_id", "browser-id"),
        ("source_id", "x" * 129),
        ("source_id", None),
        ("source_record_id", UUID(int=0)),
        ("source_record_id", "not-uuid"),
        ("content_sha256", "A" * 64),
        ("content_sha256", "a" * 63),
        ("content_sha256", None),
        ("reference_manifest_sha256", "g" * 64),
        ("parser_version", ""),
        ("parser_version", " 1.0.0"),
        ("parser_version", "1.0.0\n"),
        ("parser_version", "a" * 129),
        ("parser_version", "v\u0000one"),
        ("normalizer_version", None),
    ],
)
def test_malformed_identity_is_refused_without_coercion(field, value):
    with pytest.raises(ValueError, match=f"artifact_identity_invalid_{field}"):
        replace(example(), **{field: value})


@pytest.mark.parametrize("run_id", [None, "not-uuid", UUID(int=0)])
def test_run_membership_requires_explicit_non_nil_uuid(run_id):
    with pytest.raises(ValueError, match="artifact_identity_invalid_run_id"):
        example().run_member_key(run_id)
