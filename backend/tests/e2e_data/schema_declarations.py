"""Explicit synthetic declarations, isolated per test; never infer shapes from bytes."""

import os

from ketrika.core import schema_contracts
from ketrika.core.provenance_audit import POLICIES
from ketrika.core.schema_audit import SchemaContract
from ketrika.core.schema_contracts import SchemaContractBinding, SchemaContractRegistry
from ketrika.core.schema_json import JSONSchemaContract, JSONShape

# The generator emits only these code-declared observation fields as JSON strings.
SYNTHETIC_GENERATOR_CONTRACT = JSONSchemaContract(
    "synthetic-source-generator-structure-v1",
    JSONShape(
        "array",
        items=JSONShape(
            "object",
            properties=tuple(
                (name, JSONShape("string"), False)
                for name in sorted(
                    {
                        name
                        for policy in POLICIES.values()
                        for name in (*policy.values, *policy.identities)
                    }
                )
            ),
        ),
    ),
)


def declare_synthetic_contract(
    source_id: str, parser_version: str, mime_type: str, contract: SchemaContract
) -> None:
    if os.environ.get("KETRIKA_QUALIFICATION") != "1" or os.environ.get("APP_ENV") != "test":
        raise ValueError("synthetic_contract_declaration_requires_qualification")
    binding = SchemaContractBinding(source_id, parser_version, mime_type, contract)
    current = schema_contracts.get_schema_contract_registry()
    existing = current.resolve(source_id, parser_version, mime_type)
    if existing is not None:
        if existing != contract:
            raise ValueError("synthetic_contract_declaration_conflict")
        return
    schema_contracts.DEFAULT_SCHEMA_CONTRACT_REGISTRY = SchemaContractRegistry(
        (*current.bindings, binding)
    )
