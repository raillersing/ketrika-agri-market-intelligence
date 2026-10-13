"""Exact trusted declarations and candidate/cache guards, not live source proof."""

from dataclasses import FrozenInstanceError
from typing import Any, cast
from unittest.mock import Mock
from uuid import uuid4

import pytest

from ketrika.core.models.db import SourceRecord
from ketrika.core.schema_audit import CSVSchemaContract, audit_source_schema
from ketrika.core.schema_contracts import (
    SchemaContractBinding,
    SchemaContractRegistry,
    contract_fingerprint,
    get_schema_contract_registry,
)
from tests.unit.test_schema_audit import example

CONTRACT = CSVSchemaContract("explicit-v1", ("product", "price"))
BINDING = SchemaContractBinding("dummy_schema", "parser-v1", "text/csv", CONTRACT)


def test_default_registry_never_infers_public_or_fixture_contracts():
    registry = get_schema_contract_registry()
    assert registry.bindings == ()
    assert registry.resolve("wfp_hdx_mdg", "1.0.1", "text/csv") is None
    assert registry.resolve("dummy_schema", "parser-v1", "text/csv") is None


@pytest.mark.parametrize(
    "key",
    [
        ("other", "parser-v1", "text/csv"),
        ("dummy_schema", "parser-v2", "text/csv"),
        ("dummy_schema", "parser-v1", "application/csv"),
        ("dummy_schema", None, "text/csv"),
    ],
)
def test_exact_binding_does_not_authorize_another_source_version_or_mime(key):
    registry = SchemaContractRegistry((BINDING,))
    assert registry.resolve(*BINDING.key) is CONTRACT
    assert registry.resolve(*key) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", "*"),
        ("source_id", "A"),
        ("parser_version", ""),
        ("parser_version", "v\n1"),
        ("mime_type", "application/json"),
    ],
)
def test_invalid_declaration_rejected(field, value):
    values: dict[str, Any] = {
        "source_id": BINDING.source_id,
        "parser_version": BINDING.parser_version,
        "mime_type": BINDING.mime_type,
        "contract": CONTRACT,
    }
    values[field] = value
    with pytest.raises(ValueError, match="schema_registry_invalid"):
        SchemaContractBinding(**values)


def test_duplicate_binding_and_mutation_refused():
    with pytest.raises(ValueError, match="duplicate_binding"):
        SchemaContractRegistry((BINDING, BINDING))
    registry = SchemaContractRegistry((BINDING,))
    with pytest.raises(FrozenInstanceError):
        registry.bindings = ()
    with pytest.raises(TypeError):
        cast(dict[tuple[str, str, str], Any], registry._lookup)[BINDING.key] = CONTRACT


def test_contract_version_is_part_of_fingerprint():
    assert contract_fingerprint(CONTRACT) != contract_fingerprint(
        CSVSchemaContract("explicit-v2", CONTRACT.required_columns)
    )


def test_same_bytes_with_unknown_parser_never_reuses_known_inspection():
    session, reader, record = example()
    record.parser_version = "parser-v1"
    other = SourceRecord(
        source_record_id=uuid4(),
        source_id=record.source_id,
        object_key=record.object_key,
        content_sha256=record.content_sha256,
        mime_type=record.mime_type,
        parser_version="parser-v2",
    )
    session.scalars.return_value.all.return_value = [record, other]
    receipt = audit_source_schema(
        session,
        reader,
        record.source_id,
        registry=SchemaContractRegistry((BINDING,)),
        record_ids=(record.source_record_id, other.source_record_id),
    )
    assert receipt.report.total_artifacts == 2 and receipt.report.valid_artifacts == 1
    assert receipt.report.results[1]["state"] == "unknown"
    assert receipt.report.results[1]["binding_contract_sha256"] is None
    assert session.add.call_args.args[0].details["scope"] == "publication_candidate_artifacts"
    query = str(session.scalars.call_args.args[0])
    assert "obs." not in query
    session.commit.assert_not_called()


@pytest.mark.parametrize("ids", [(), ("not-uuid",), (uuid4(), uuid4())])
def test_invalid_or_missing_candidate_references_refused(ids):
    session, reader, record = example()
    with pytest.raises(
        ValueError, match="schema_audit_(invalid_candidates|candidate_reference_missing)"
    ):
        audit_source_schema(session, reader, record.source_id, record_ids=ids)
    reader.get.assert_not_called()


def test_publication_cannot_use_unbound_override():
    session, reader = Mock(), Mock()
    with pytest.raises(ValueError, match="override_not_publication_authority"):
        audit_source_schema(session, reader, "dummy_schema", CONTRACT, record_ids=(uuid4(),))
    session.scalars.assert_not_called()
