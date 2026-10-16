"""Fresh historical and exact-candidate structure receipts for publication guards."""

import hashlib
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import select, union_all
from sqlalchemy.orm import Session

from ketrika.core.models.db import DqResult, SourceRecord
from ketrika.core.provenance import (
    ArtifactReader,
    ArtifactReference,
    ProofError,
    _validate_reference,
)
from ketrika.core.provenance_audit import POLICIES
from ketrika.core.schema_drift import MAX_BYTES, inspect_csv_schema
from ketrika.core.schema_json import JSONSchemaAlternatives, JSONSchemaContract, inspect_json_schema

MAX_ARTIFACTS = 100_000

if TYPE_CHECKING:
    from ketrika.core.schema_contracts import SchemaContractRegistry


@dataclass(frozen=True)
class CSVSchemaContract:
    version: str
    required_columns: tuple[str, ...]
    optional_columns: tuple[str, ...] = ()
    delimiter: str = ","

    def __post_init__(self) -> None:
        if (
            not isinstance(self.version, str)
            or not self.version
            or len(self.version) > 128
            or self.version != self.version.strip()
            or any(ord(c) < 32 or ord(c) == 127 for c in self.version)
            or self.required_columns is None
        ):
            raise ValueError("schema_contract_invalid_version_or_columns")
        # Reuse the helper's full baseline validation without a source sample.
        inspect_csv_schema(
            b"",
            required_columns=self.required_columns,
            optional_columns=self.optional_columns,
            delimiter=self.delimiter,
        )


SchemaContract = CSVSchemaContract | JSONSchemaContract | JSONSchemaAlternatives


@dataclass(frozen=True)
class SourceSchemaReport:
    total_artifacts: int
    valid_artifacts: int
    objects_read: int
    read_attempts: int
    results: tuple[dict[str, Any], ...]

    @property
    def passed(self) -> bool:
        return self.total_artifacts > 0 and self.valid_artifacts == self.total_artifacts

    @property
    def state(self) -> str:
        return "empty" if not self.total_artifacts else "verified" if self.passed else "failed"


@dataclass(frozen=True)
class SourceSchemaReceipt:
    report: SourceSchemaReport
    dq_id: UUID


def audit_source_schema(
    session: Session,
    reader: ArtifactReader,
    source_id: str,
    contract: SchemaContract | None = None,
    *,
    registry: "SchemaContractRegistry | None" = None,
    record_ids: tuple[UUID, ...] | None = None,
) -> SourceSchemaReceipt:
    """Fresh historical or exact candidate measurement, without commit or discovery."""
    from ketrika.core.schema_contracts import (
        SchemaContractRegistry,
        contract_fingerprint,
        get_schema_contract_registry,
    )

    if contract is not None and not isinstance(
        contract, (CSVSchemaContract, JSONSchemaContract, JSONSchemaAlternatives)
    ):
        raise ValueError("schema_audit_invalid_contract")
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("schema_audit_invalid_source")
    if registry is not None and not isinstance(registry, SchemaContractRegistry):
        raise ValueError("schema_audit_invalid_registry")
    if contract is not None and (registry is not None or record_ids is not None):
        raise ValueError("schema_audit_override_not_publication_authority")
    if record_ids is not None and (
        not isinstance(record_ids, tuple)
        or not record_ids
        or len(record_ids) > MAX_ARTIFACTS
        or any(not isinstance(identifier, UUID) or identifier.int == 0 for identifier in record_ids)
        or len(set(record_ids)) != len(record_ids)
    ):
        raise ValueError("schema_audit_invalid_candidates")
    resolved_registry = registry if registry is not None else get_schema_contract_registry()
    referenced_ids = union_all(
        *(select(policy.model.source_record_id) for policy in POLICIES.values())
    )
    records = session.scalars(
        select(SourceRecord)
        .where(
            SourceRecord.source_id == source_id,
            SourceRecord.source_record_id.in_(referenced_ids if record_ids is None else record_ids),
        )
        .order_by(SourceRecord.source_record_id)
    ).all()
    if len(records) > MAX_ARTIFACTS:
        raise ValueError("schema_audit_artifacts_outside_bounds")
    if record_ids is not None and {r.source_record_id for r in records} != set(record_ids):
        raise ValueError("schema_audit_candidate_reference_missing")
    results: list[dict[str, Any]] = []
    cache: dict[tuple[str, str, str, str | None, str | None], dict[str, Any]] = {}
    read_attempts = objects_read = valid = 0
    for reference in records:
        selected_contract = (
            contract
            if contract is not None
            else resolved_registry.resolve(
                reference.source_id, reference.parser_version, reference.mime_type
            )
        )
        contract_sha = contract_fingerprint(selected_contract) if selected_contract else None
        result: dict[str, Any] = {"state": "failed", "reasons": []}
        try:
            digest = _validate_reference(
                ArtifactReference(
                    reference.source_record_id,
                    reference.source_id,
                    reference.object_key,
                    reference.content_sha256,
                    reference.mime_type or "",
                )
            )
        except ProofError as exc:
            result["reasons"] = [str(exc)]
        else:
            key = (
                reference.object_key,
                digest,
                reference.mime_type or "",
                reference.parser_version,
                contract_sha,
            )
            cached = cache.get(key)
            if cached is not None:
                result = dict(cached)
            else:
                read_attempts += 1
                try:
                    content = reader.get(reference.object_key)
                except Exception:
                    result["reasons"] = ["schema_artifact_unreadable"]
                else:
                    if not isinstance(content, bytes):
                        result["reasons"] = ["schema_artifact_not_bytes"]
                    else:
                        objects_read += 1
                        if len(content) > MAX_BYTES:
                            result["reasons"] = ["schema_artifact_outside_bounds"]
                        elif hashlib.sha256(content).hexdigest() != digest:
                            result["reasons"] = ["schema_content_sha_mismatch"]
                        elif selected_contract is None:
                            result.update(state="unknown", reasons=["schema_contract_absent"])
                        elif isinstance(
                            selected_contract, CSVSchemaContract
                        ) and reference.mime_type in {
                            "text/csv",
                            "application/csv",
                        }:
                            inspection = inspect_csv_schema(
                                content,
                                required_columns=selected_contract.required_columns,
                                optional_columns=selected_contract.optional_columns,
                                delimiter=selected_contract.delimiter,
                            )
                            result = asdict(inspection)
                            result["contract_version"] = selected_contract.version
                        elif (
                            isinstance(
                                selected_contract, (JSONSchemaContract, JSONSchemaAlternatives)
                            )
                            and reference.mime_type == "application/json"
                        ):
                            json_inspection = inspect_json_schema(content, selected_contract)
                            result = asdict(json_inspection)
                            result["contract_version"] = selected_contract.version
                        else:
                            result.update(state="unknown", reasons=["schema_format_unsupported"])
                cache[key] = dict(result)
        result = dict(result) | {
            "source_record_id": str(reference.source_record_id),
            "parser_version": reference.parser_version,
            "binding_contract_sha256": contract_sha,
        }
        valid += int(result["state"] == "verified")
        results.append(result)
    report = SourceSchemaReport(len(records), valid, objects_read, read_attempts, tuple(results))
    dq_id = uuid4()
    session.add(
        DqResult(
            dq_id=dq_id,
            check_name="schema_drift",
            source_id=source_id,
            asset_key=f"{source_id}__silver",
            passed=report.passed,
            metric=Decimal(report.total_artifacts - report.valid_artifacts)
            if report.total_artifacts
            else None,
            threshold=Decimal(0),
            details={
                "state": report.state,
                "scope": "publication_candidate_artifacts"
                if record_ids is not None
                else "all_referenced_source_artifacts_not_parsing_or_authenticity",
                "total_artifacts": report.total_artifacts,
                "valid_schema_artifacts": report.valid_artifacts,
                "objects_read": report.objects_read,
                "object_read_attempts": report.read_attempts,
                "results": list(report.results),
            },
        )
    )
    session.flush()
    return SourceSchemaReceipt(report, dq_id)
