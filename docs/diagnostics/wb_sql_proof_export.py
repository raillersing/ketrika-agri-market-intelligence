"""Read-only export of actual WB SQL inputs, not a qualification bundle.

Producer identity is explicit. These original inputs must not be relabelled as
having been collected or replayed in the synthetic software-test environment.
"""

import hashlib
import json
import os
import runpy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ketrika.core.models.db import PriceObservation, SourceRecord
from ketrika.core.provenance import ArtifactReference, ProvenanceVerifier
from ketrika.core.provenance_audit import bind_observation
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification_reports import source_fingerprint
from ketrika.core.settings import get_settings
from ketrika.pipelines.rebuild_qualification import require_destination, require_network_none
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

assert os.getuid() == 1000
fingerprint = source_fingerprint(Path("/workspace"))
assert fingerprint == "7d81deb9b8846d9a3bd1e64f843e493134cff2100ec859f6e0188158b66f68eb"
network = require_network_none()
store = runpy.run_path("/workspace/backend/scripts/wb_archive_qualification.py")["store"]()
engine = create_engine(get_settings().database_url)
with Session(engine) as session:
    session.execute(text("SET TRANSACTION READ ONLY"))
    require_destination(session)
    rows = list(
        session.scalars(
            select(PriceObservation).order_by(
                PriceObservation.natural_key, PriceObservation.source_record_id
            )
        )
    )
    references = list(session.scalars(select(SourceRecord).order_by(SourceRecord.fetched_at)))
    assert len(rows) == 163 and len(references) == 3
    descriptors = {}
    for item in references:
        if not isinstance(item.mime_type, str):
            raise ValueError("source_mime_required")
        descriptors[item.source_record_id] = ArtifactReference(
            item.source_record_id,
            item.source_id,
            item.object_key,
            item.content_sha256,
            item.mime_type,
        )
    report = ProvenanceVerifier(BronzeProofReader(store), descriptors).verify(
        [bind_observation("price_observation", row) for row in rows]
    )
    assert report.passed and report.valid == 163
    payload = {
        "version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "producer_source_fingerprint": fingerprint,
        "producer_environment": {
            "database": session.get_bind().engine.url.database,
            "connection": "dedicated_unix_socket",
            "network": network,
            "uid": os.getuid(),
        },
        "dataset_origin": "authentic two WB editions; bounded national c_rice since2020",
        "read_only_transaction": session.scalar(text("SHOW transaction_read_only")),
        "references": [
            {
                "source_record_id": str(item.source_record_id),
                "source_id": item.source_id,
                "object_key": item.object_key,
                "content_sha256": item.content_sha256,
                "mime_type": item.mime_type,
                "source_url": item.source_url,
                "fetched_at": item.fetched_at,
                "published_at": item.published_at,
                "http_status": item.http_status,
            }
            for item in references
        ],
        "observations": [
            {
                "table": "price_observation",
                "values": {
                    column.name: getattr(row, column.name)
                    for column in PriceObservation.__table__.columns
                },
            }
            for row in rows
        ],
        "fresh_verification": {
            "total": report.total,
            "valid": report.valid,
            "objects_read": report.objects_read,
            "object_read_attempts": report.object_read_attempts,
        },
        "human_reviewed": False,
        "model_qualified": False,
        "scope": "original SQL export and fresh cell audit, not a gate or deployment",
        "wrapper_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    assert payload["read_only_transaction"] == "on"
    assert source_fingerprint(Path("/workspace")) == fingerprint
    output = Path("/out") / ("sql-inputs-" + uuid4().hex + ".json")
    with output.open("x") as stream:
        json.dump(payload, stream, indent=2, default=str)
    session.rollback()
    print(json.dumps({"report": str(output), "verified": report.valid, "read_only": True}))
engine.dispose()
