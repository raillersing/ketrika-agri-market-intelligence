"""Standalone prepared structural check; not automatically attached to sources."""

from dagster import AssetCheckResult, AssetChecksDefinition, AssetCheckSeverity, asset_check

from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.schema_audit import SchemaContract, audit_source_schema


def build_source_schema_check(
    source_id: str, contract: SchemaContract | None
) -> AssetChecksDefinition:
    @asset_check(asset=f"{source_id}__silver", name=f"{source_id}__schema_drift", blocking=True)
    def check_schema(context) -> AssetCheckResult:
        with get_session() as session:
            receipt = audit_source_schema(
                session, BronzeProofReader(BronzeStore()), source_id, contract
            )
        report = receipt.report
        return AssetCheckResult(
            passed=report.passed,
            severity=AssetCheckSeverity.ERROR,
            metadata={
                "source_id": source_id,
                "dq_id": str(receipt.dq_id),
                "total_artifacts": report.total_artifacts,
                "valid_schema_artifacts": report.valid_artifacts,
                "objects_read": report.objects_read,
                "object_read_attempts": report.read_attempts,
                "state": report.state,
                "scope": "structure_not_parsing_authenticity_or_conversions",
            },
        )

    return check_schema
