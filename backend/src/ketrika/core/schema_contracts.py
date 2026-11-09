"""Code-owned, exact source/parser/MIME declarations; never learned from Bronze."""

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from ketrika.core.schema_audit import CSVSchemaContract, SchemaContract
from ketrika.core.schema_json import JSONSchemaAlternatives, JSONSchemaContract
from ketrika.core.schema_rtfp import WB_RTFP_JSON
from ketrika.core.schema_wb_archive import WBArchiveSchemaContract


def contract_fingerprint(contract: SchemaContract) -> str:
    if isinstance(contract, (JSONSchemaContract, JSONSchemaAlternatives, WBArchiveSchemaContract)):
        return contract.sha256
    if not isinstance(contract, CSVSchemaContract):
        raise ValueError("schema_registry_invalid_contract")
    frame = [
        "csv_structure_contract_v1",
        contract.version,
        sorted(contract.required_columns),
        sorted(contract.optional_columns),
        contract.delimiter,
    ]
    return hashlib.sha256(
        json.dumps(frame, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class SchemaContractBinding:
    source_id: str
    parser_version: str
    mime_type: str
    contract: SchemaContract

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not re.fullmatch(
            r"[a-z0-9_]{1,128}", self.source_id
        ):
            raise ValueError("schema_registry_invalid_source")
        if (
            not isinstance(self.parser_version, str)
            or not self.parser_version
            or self.parser_version != self.parser_version.strip()
            or len(self.parser_version) > 128
            or any(ord(c) < 32 or ord(c) == 127 for c in self.parser_version)
        ):
            raise ValueError("schema_registry_invalid_parser")
        if not (
            isinstance(self.contract, CSVSchemaContract)
            and self.mime_type in {"text/csv", "application/csv"}
            or isinstance(self.contract, (JSONSchemaContract, JSONSchemaAlternatives))
            and self.mime_type == "application/json"
            or isinstance(self.contract, WBArchiveSchemaContract)
            and self.mime_type in {"application/zip", "application/octet-stream"}
        ):
            raise ValueError("schema_registry_invalid_format")
        contract_fingerprint(self.contract)

    @property
    def key(self) -> tuple[str, str, str]:
        return self.source_id, self.parser_version, self.mime_type


@dataclass(frozen=True)
class SchemaContractRegistry:
    bindings: tuple[SchemaContractBinding, ...] = ()
    _lookup: Mapping[tuple[str, str, str], SchemaContract] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.bindings, tuple) or len(self.bindings) > 4096:
            raise ValueError("schema_registry_outside_bounds")
        lookup: dict[tuple[str, str, str], SchemaContract] = {}
        for binding in self.bindings:
            if not isinstance(binding, SchemaContractBinding):
                raise ValueError("schema_registry_invalid_binding")
            if binding.key in lookup:
                raise ValueError("schema_registry_duplicate_binding")
            lookup[binding.key] = binding.contract
        object.__setattr__(self, "_lookup", MappingProxyType(lookup))

    def resolve(
        self, source_id: str, parser_version: str | None, mime_type: str | None
    ) -> SchemaContract | None:
        if not isinstance(parser_version, str) or not isinstance(mime_type, str):
            return None
        return self._lookup.get((source_id, parser_version, mime_type))


MIASA_ODR_CSV = CSVSchemaContract(
    version="1.0.0",
    required_columns=(
        "period_start",
        "product_raw",
        "location_raw",
        "unit_raw",
        "currency_raw",
        "price_value",
        "product_code",
    ),
    delimiter=",",
)

DOUANES_STATS_CSV = CSVSchemaContract(
    version="1.0.0",
    required_columns=(
        "period_start",
        "product_raw",
        "location_raw",
        "unit_raw",
        "currency_raw",
        "price_value",
        "product_code",
    ),
    delimiter=",",
)

# Explicit archived source/version/MIME bindings only; no inferred format or version.
DECLARED_SCHEMA_BINDINGS = (
    SchemaContractBinding("wb_rtfp_mdg", "2.0.0", "application/json", WB_RTFP_JSON),
    SchemaContractBinding("wb_rtfp_mdg", "3.0.0", "application/json", WB_RTFP_JSON.alternatives[1]),
    SchemaContractBinding("wb_rtfp_mdg", "3.0.0", "application/zip", WBArchiveSchemaContract()),
    SchemaContractBinding(
        "wb_rtfp_mdg", "3.0.0", "application/octet-stream", WBArchiveSchemaContract()
    ),
    SchemaContractBinding("wb_rtfp_mdg", "4.0.0", "application/json", WB_RTFP_JSON.alternatives[1]),
    SchemaContractBinding("wb_rtfp_mdg", "4.0.0", "application/zip", WBArchiveSchemaContract()),
    SchemaContractBinding(
        "wb_rtfp_mdg", "4.0.0", "application/octet-stream", WBArchiveSchemaContract()
    ),
    SchemaContractBinding("miasa_odr", "1.0.0", "text/csv", MIASA_ODR_CSV),
    SchemaContractBinding("miasa_odr", "1.0.0", "application/csv", MIASA_ODR_CSV),
    SchemaContractBinding("douanes_stats", "1.0.0", "text/csv", DOUANES_STATS_CSV),
    SchemaContractBinding("douanes_stats", "1.0.0", "application/csv", DOUANES_STATS_CSV),
)
DEFAULT_SCHEMA_CONTRACT_REGISTRY = SchemaContractRegistry(DECLARED_SCHEMA_BINDINGS)


def get_schema_contract_registry() -> SchemaContractRegistry:
    return DEFAULT_SCHEMA_CONTRACT_REGISTRY
