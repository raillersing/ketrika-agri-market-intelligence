"""Fresh source-scoped structure measurement; not a wired publication gate."""

import hashlib
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any
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
from ketrika.core.schema_json import JSONSchemaContract, inspect_json_schema

MAX_ARTIFACTS = 100_000


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


SchemaContract = CSVSchemaContract | JSONSchemaContract


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
    contract: SchemaContract | None,
) -> SourceSchemaReceipt:
    """Measure every referenced source artifact, no network discovery or commit."""
    if contract is not None and not isinstance(contract, (CSVSchemaContract, JSONSchemaContract)):
        raise ValueError("schema_audit_invalid_contract")
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("schema_audit_invalid_source")
    referenced_ids = union_all(
        *(select(policy.model.source_record_id) for policy in POLICIES.values())
    )
    records = session.scalars(
        select(SourceRecord)
        .where(
            SourceRecord.source_id == source_id,
            SourceRecord.source_record_id.in_(referenced_ids),
        )
        .order_by(SourceRecord.source_record_id)
    ).all()
    if len(records) > MAX_ARTIFACTS:
        raise ValueError("schema_audit_artifacts_outside_bounds")
    results: list[dict[str, Any]] = []
    cache: dict[tuple[str, str, str], dict[str, Any]] = {}
    read_attempts = objects_read = valid = 0
    for reference in records:
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
            key = reference.object_key, digest, reference.mime_type or ""
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
                        elif contract is None:
                            result.update(state="unknown", reasons=["schema_contract_absent"])
                        elif isinstance(contract, CSVSchemaContract) and reference.mime_type in {
                            "text/csv",
                            "application/csv",
                        }:
                            inspection = inspect_csv_schema(
                                content,
                                required_columns=contract.required_columns,
                                optional_columns=contract.optional_columns,
                                delimiter=contract.delimiter,
                            )
                            result = asdict(inspection)
                            result["contract_version"] = contract.version
                        elif (
                            isinstance(contract, JSONSchemaContract)
                            and reference.mime_type == "application/json"
                        ):
                            json_inspection = inspect_json_schema(content, contract)
                            result = asdict(json_inspection)
                            result["contract_version"] = contract.version
                        else:
                            result.update(state="unknown", reasons=["schema_format_unsupported"])
                cache[key] = dict(result)
        result = dict(result) | {"source_record_id": str(reference.source_record_id)}
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
                "scope": "all_referenced_source_artifacts_not_parsing_or_authenticity",
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
