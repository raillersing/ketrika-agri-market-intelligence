"""Pure closed JSON shapes, not a wired publication or numerical gate."""

import hashlib
import json
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Any

from ketrika.core.provenance import (
    MAX_CONTENT_BYTES,
    JsonNumberToken,
    ProofError,
    _at,
    _check_json_depth,
    _reject_constant,
    _unique_json_object,
)

MAX_SHAPE_DEPTH = 32
MAX_SHAPE_NODES = 4096
MAX_DATA_NODES = 100_000


@dataclass(frozen=True)
class JSONShape:
    kind: str
    properties: tuple[tuple[str, "JSONShape", bool], ...] = ()
    items: "JSONShape | None" = None
    prefix: tuple["JSONShape", ...] = ()
    nullable: bool = False


def _canonical_shape(root: JSONShape) -> Any:
    visited = 0

    def visit(node: JSONShape, depth: int) -> Any:
        nonlocal visited
        visited += 1
        if depth > MAX_SHAPE_DEPTH or visited > MAX_SHAPE_NODES:
            raise ValueError("json_contract_outside_bounds")
        if (
            not isinstance(node, JSONShape)
            or not isinstance(node.kind, str)
            or node.kind
            not in {"object", "array", "tuple", "string", "number", "decimal", "boolean", "null"}
            or type(node.nullable) is not bool
            or not isinstance(node.properties, tuple)
            or not isinstance(node.prefix, tuple)
        ):
            raise ValueError("json_contract_invalid_shape")
        properties = []
        names = set()
        for item in node.properties:
            if not isinstance(item, tuple) or len(item) != 3:
                raise ValueError("json_contract_invalid_property")
            name, child, required = item
            if (
                not isinstance(name, str)
                or not name
                or len(name) > 256
                or any(ord(c) < 32 or ord(c) == 127 for c in name)
                or name in names
                or type(required) is not bool
            ):
                raise ValueError("json_contract_invalid_property")
            names.add(name)
            properties.append([name, visit(child, depth + 1), required])
        if (
            (node.kind != "object" and node.properties)
            or (node.kind == "array" and node.items is None)
            or (node.kind != "array" and node.items is not None)
            or (node.kind != "tuple" and node.prefix)
        ):
            raise ValueError("json_contract_invalid_shape")
        return [
            node.kind,
            node.nullable,
            sorted(properties, key=lambda item: item[0]),
            visit(node.items, depth + 1) if node.items is not None else None,
            [visit(child, depth + 1) for child in node.prefix],
        ]

    return visit(root, 0)


@dataclass(frozen=True)
class JSONSchemaContract:
    version: str
    root: JSONShape
    scope: tuple[str | int, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.version, str)
            or not self.version
            or self.version != self.version.strip()
            or len(self.version) > 128
            or any(ord(c) < 32 or ord(c) == 127 for c in self.version)
        ):
            raise ValueError("json_contract_invalid_version")
        _canonical_shape(self.root)
        if (
            not isinstance(self.scope, tuple)
            or len(self.scope) > MAX_SHAPE_DEPTH
            or any(
                type(key) not in (str, int)
                or (type(key) is int and key < 0)
                or (isinstance(key, str) and (not key or len(key) > 256))
                for key in self.scope
            )
        ):
            raise ValueError("json_contract_invalid_scope")

    @property
    def sha256(self) -> str:
        frame = ["json_structure_contract_v1", self.version, _canonical_shape(self.root)]
        if self.scope:
            frame = [
                "json_structure_contract_v2",
                self.version,
                list(self.scope),
                _canonical_shape(self.root),
            ]
        return hashlib.sha256(
            json.dumps(
                frame,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class JSONSchemaAlternatives:
    version: str
    alternatives: tuple[JSONSchemaContract, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.version, str)
            or not self.version
            or len(self.version) > 128
            or self.version != self.version.strip()
            or any(ord(c) < 32 or ord(c) == 127 for c in self.version)
        ):
            raise ValueError("json_contract_invalid_version")
        if (
            not isinstance(self.alternatives, tuple)
            or not 1 <= len(self.alternatives) <= 8
            or any(not isinstance(contract, JSONSchemaContract) for contract in self.alternatives)
        ):
            raise ValueError("json_contract_invalid_alternatives")
        if len({contract.sha256 for contract in self.alternatives}) != len(self.alternatives):
            raise ValueError("json_contract_duplicate_alternative")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(
            json.dumps(
                [
                    "json_structure_alternatives_v1",
                    self.version,
                    [item.sha256 for item in self.alternatives],
                ],
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()


@dataclass(frozen=True)
class JSONSchemaInspection:
    state: str
    content_sha256: str
    contract_sha256: str | None
    nodes_visited: int
    objects: int
    arrays: int
    missing_fields: int
    unexpected_fields: int
    invalid_types: int
    reasons: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.state == "verified" and not self.reasons


def inspect_json_schema(
    content: bytes, contract: JSONSchemaContract | JSONSchemaAlternatives | None
) -> JSONSchemaInspection:
    if not isinstance(content, bytes):
        raise ValueError("schema_content_requires_bytes")
    if isinstance(contract, JSONSchemaAlternatives):
        inspections = [inspect_json_schema(content, item) for item in contract.alternatives]
        valid = [item for item in inspections if item.passed]
        if len(valid) == 1:
            return replace(valid[0], contract_sha256=contract.sha256)
        return JSONSchemaInspection(
            "drift",
            hashlib.sha256(content).hexdigest(),
            contract.sha256,
            sum(item.nodes_visited for item in inspections),
            sum(item.objects for item in inspections),
            sum(item.arrays for item in inspections),
            sum(item.missing_fields for item in inspections),
            sum(item.unexpected_fields for item in inspections),
            sum(item.invalid_types for item in inspections),
            ("schema_ambiguous_variant" if valid else "schema_no_variant",),
        )
    if contract is not None and not isinstance(contract, JSONSchemaContract):
        raise ValueError("json_contract_invalid_type")
    digest = hashlib.sha256(content).hexdigest()
    contract_sha = contract.sha256 if contract is not None else None
    counts = {
        "nodes_visited": 0,
        "objects": 0,
        "arrays": 0,
        "missing_fields": 0,
        "unexpected_fields": 0,
        "invalid_types": 0,
    }

    def result(reasons: tuple[str, ...], *, unknown: bool = False) -> JSONSchemaInspection:
        state = "unknown" if unknown else "drift" if reasons else "verified"
        return JSONSchemaInspection(state, digest, contract_sha, **counts, reasons=reasons)

    if len(content) > MAX_CONTENT_BYTES:
        return result(("schema_document_too_large",))
    if contract is None:
        return result(("schema_contract_absent",), unknown=True)
    try:
        document = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return result(("schema_invalid_utf8",))
    try:
        _check_json_depth(document)
        payload = json.loads(
            document,
            parse_int=JsonNumberToken,
            parse_float=JsonNumberToken,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_json_object,
        )
    except (ProofError, ValueError, RecursionError):
        return result(("schema_invalid_json",))
    if contract.scope:
        try:
            payload = _at(payload, contract.scope)
        except ProofError:
            return result(("schema_scope_missing",))

    def visit(value: Any, node: JSONShape) -> None:
        counts["nodes_visited"] += 1
        if counts["nodes_visited"] > MAX_DATA_NODES:
            raise ValueError("schema_nodes_outside_bounds")
        if value is None and (node.nullable or node.kind == "null"):
            return
        if node.kind == "object" and isinstance(value, dict):
            counts["objects"] += 1
            allowed = {name for name, _, _ in node.properties}
            counts["unexpected_fields"] += len(set(value) - allowed)
            for name, child, required in node.properties:
                if name in value:
                    visit(value[name], child)
                else:
                    counts["missing_fields"] += int(required)
        elif node.kind in {"array", "tuple"} and isinstance(value, list):
            counts["arrays"] += 1
            if node.kind == "array":
                assert node.items is not None  # validated code-owned contract
                for item in value:
                    visit(item, node.items)
            else:
                counts["invalid_types"] += int(len(value) != len(node.prefix))
                for item, child in zip(value, node.prefix, strict=False):
                    visit(item, child)
        elif node.kind == "decimal":
            raw = value.raw if isinstance(value, JsonNumberToken) else value
            try:
                valid = isinstance(raw, str) and len(raw) <= 128 and Decimal(raw).is_finite()
            except InvalidOperation:
                valid = False
            counts["invalid_types"] += int(not valid)
        elif (
            (node.kind == "string" and isinstance(value, str))
            or (node.kind == "number" and isinstance(value, JsonNumberToken))
            or (node.kind == "boolean" and type(value) is bool)
        ):
            return
        else:
            counts["invalid_types"] += 1

    try:
        visit(payload, contract.root)
    except ValueError:
        return result(("schema_nodes_outside_bounds",))
    return result(
        tuple(
            reason
            for reason, key in (
                ("schema_missing_fields", "missing_fields"),
                ("schema_unexpected_fields", "unexpected_fields"),
                ("schema_invalid_types", "invalid_types"),
            )
            if counts[key]
        )
    )
