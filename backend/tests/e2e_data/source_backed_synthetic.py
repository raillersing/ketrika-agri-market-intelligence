"""Create NEW synthetic source bytes before inserting a test observation.

Never retrofit a persisted observation or certify market/source authenticity.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from ketrika.core.bronze import BronzeStore
from ketrika.core.models.db import SourceRecord
from ketrika.core.provenance import verify_cells
from ketrika.core.provenance_audit import POLICIES, bind_observation
from ketrika.core.qualification import require_synthetic_test_database
from tests.e2e_data.schema_declarations import (
    SYNTHETIC_GENERATOR_CONTRACT,
    declare_synthetic_contract,
)


def attach_new_synthetic_proof(
    session: Session, observation: Any, reader: BronzeStore | None = None
) -> None:
    """Synthetic generator only, protected by environment AND actual DB destination."""
    target = session.get_bind().engine.url
    require_synthetic_test_database(target.host, target.database)
    if not inspect(observation).transient:
        raise ValueError("synthetic_proof_requires_new_transient_observation")
    policy = POLICIES.get(observation.__tablename__)
    if policy is None:
        raise ValueError("unsupported_synthetic_observation")
    reference = session.get(SourceRecord, observation.source_record_id)
    if reference is None:
        raise ValueError("synthetic_source_reference_missing")
    if reader is None:
        reader = BronzeStore()
    if reader.bucket != "ketrika-qa-bronze":
        raise ValueError("synthetic_bronze_destination_refused")
    declare_synthetic_contract(
        reference.source_id,
        "synthetic-source-generator-v1",
        "application/json",
        SYNTHETIC_GENERATOR_CONTRACT,
    )
    fields: dict[str, str] = {}
    supplied_raw: dict[str, str] = {}
    cells = []
    for field in (*policy.values, *policy.identities):
        value = getattr(observation, field)
        if value is None:
            continue
        raw_field = policy.raw_fields.get(field)
        raw = getattr(observation, raw_field) if raw_field else None
        if raw_field and raw is None:
            # These are generator inputs, not recovered historical raw values.
            raw = str(value)
        if raw_field:
            if not isinstance(raw, str):
                raise ValueError("synthetic_raw_must_be_text")
            supplied_raw[raw_field] = raw
            rendered = raw
        elif isinstance(value, date):
            rendered = value.isoformat()
        else:
            rendered = str(value)
        fields[field] = rendered
        cells.append(
            {
                "field": field,
                "path": [0, field],
                "role": "value" if field in policy.values else "identity",
                "kind": "text"
                if field not in policy.values or field == "stock_status"
                else "number",
                "expected": "untrusted",
            }
        )
    content = json.dumps([fields], ensure_ascii=False, sort_keys=True).encode()
    evidence = {
        "provenance": {"version": 1, "format": "json", "scope_path": [0], "cells": cells},
        "authenticity": "synthetic",
        "verified": False,
    }
    candidate = policy.model(
        observation_id=observation.observation_id,
        source_record_id=observation.source_record_id,
        extraction_method="deterministic",
        evidence=evidence,
        **{field: getattr(observation, field) for field in (*policy.values, *policy.identities)},
        **supplied_raw,
    )
    verify_cells(
        content, "application/json", bind_observation(observation.__tablename__, candidate).proof
    )
    artifact = reader.put(
        source_id=reference.source_id,
        content=content,
        mime_type="application/json",
        url="https://example.invalid/synthetic-gold-generator",
        retrieved_via="manual_upload",
        fetched_at=datetime(2024, 3, 1, tzinfo=UTC),
        http_status=0,
        http_headers={"x-ketrika-dataset": "synthetic; verified=false"},
    )
    identifier = uuid5(
        NAMESPACE_URL,
        "ketrika-synthetic-gold:" + reference.source_id + ":" + artifact.content_sha256,
    )
    with session.no_autoflush:
        existing = session.get(SourceRecord, identifier)
    if existing is None:
        session.add(
            SourceRecord(
                source_record_id=identifier,
                source_id=reference.source_id,
                object_key=artifact.object_key,
                content_sha256=artifact.content_sha256,
                mime_type="application/json",
                source_url="https://example.invalid/synthetic-gold-generator",
                retrieved_via="manual_upload",
                fetched_at=datetime(2024, 3, 1, tzinfo=UTC),
                extraction_status="parsed",
                parser_version="synthetic-source-generator-v1",
            )
        )
        session.flush()
    elif (
        existing.object_key != artifact.object_key
        or existing.content_sha256 != artifact.content_sha256
    ):
        raise ValueError("synthetic_source_reference_conflict")
    observation.source_record_id = identifier
    for field, raw in supplied_raw.items():
        setattr(observation, field, raw)
    observation.extraction_method = "deterministic"
    observation.evidence = evidence
