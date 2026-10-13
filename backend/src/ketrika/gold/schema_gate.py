"""Fresh exact-candidate structure gate, under the provenance gate's held locks."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.core.models.db import SourceRecord
from ketrika.core.provenance import ArtifactReader
from ketrika.core.schema_audit import MAX_ARTIFACTS, SourceSchemaReceipt, audit_source_schema
from ketrika.core.schema_contracts import SchemaContractRegistry, get_schema_contract_registry
from ketrika.gold.provenance_gate import PublicationCheck


class GoldSchemaRejected(ValueError):
    def __init__(self, receipts: tuple[SourceSchemaReceipt, ...]) -> None:
        self.receipts = receipts
        self.replay_stats: dict[str, object] | None = None
        super().__init__("gold_schema_rejected")


@dataclass(frozen=True)
class StructurePublicationCheck:
    state: str
    receipts: tuple[SourceSchemaReceipt, ...] = ()

    @property
    def total(self) -> int:
        return sum(receipt.report.total_artifacts for receipt in self.receipts)

    @property
    def valid(self) -> int:
        return sum(receipt.report.valid_artifacts for receipt in self.receipts)


def require_gold_structure(
    session: Session,
    reader: ArtifactReader,
    publication: PublicationCheck,
    registry: SchemaContractRegistry | None = None,
) -> StructurePublicationCheck:
    if publication.state in {"metadata_only", "empty"}:
        if publication.candidate_record_ids:
            raise ValueError("gold_structure_candidate_scope_invalid")
        return StructurePublicationCheck(publication.state)
    if publication.state != "cells_verified" or not publication.candidate_record_ids:
        raise ValueError("gold_structure_candidate_scope_missing")
    if (
        len(publication.candidate_record_ids) > MAX_ARTIFACTS
        or any(
            not isinstance(identifier, UUID) or identifier.int == 0
            for identifier in publication.candidate_record_ids
        )
        or len(set(publication.candidate_record_ids)) != len(publication.candidate_record_ids)
    ):
        raise ValueError("gold_structure_candidate_scope_invalid")
    selected_registry = registry if registry is not None else get_schema_contract_registry()
    if not isinstance(selected_registry, SchemaContractRegistry):
        raise ValueError("gold_structure_invalid_registry")
    records = session.scalars(
        select(SourceRecord)
        .where(SourceRecord.source_record_id.in_(publication.candidate_record_ids))
        .order_by(SourceRecord.source_id, SourceRecord.source_record_id)
    ).all()
    if {record.source_record_id for record in records} != set(publication.candidate_record_ids):
        raise ValueError("gold_structure_candidate_reference_missing")
    grouped: dict[str, list[UUID]] = {}
    for record in records:
        grouped.setdefault(record.source_id, []).append(record.source_record_id)
    receipts = tuple(
        audit_source_schema(
            session, reader, source_id, registry=selected_registry, record_ids=tuple(ids)
        )
        for source_id, ids in sorted(grouped.items())
    )
    if not all(receipt.report.passed for receipt in receipts):
        raise GoldSchemaRejected(receipts)
    return StructurePublicationCheck("structure_verified", receipts)
