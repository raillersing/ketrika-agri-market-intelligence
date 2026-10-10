"""Whole generator with simulated SQL/store; NOT a SQL publication qualification."""

import hashlib
from typing import Any
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from ketrika.core.bronze import BronzeArtifact
from ketrika.core.models.db import SourceRecord
from ketrika.core.provenance import verify_cells
from ketrika.core.provenance_audit import POLICIES, bind_observation
from tests.e2e_data.synthetic_gold_dataset import seed_synthetic_gold_data


def test_all_new_synthetic_observations_have_matching_source_cells() -> None:
    session, reader = MagicMock(spec=Session), MagicMock()
    reader.bucket = "ketrika-qa-bronze"
    rows: list[Any] = []
    references: dict[object, SourceRecord] = {}
    contents: dict[str, bytes] = {}

    def add(row):
        rows.append(row)
        if isinstance(row, SourceRecord):
            references[row.source_record_id] = row

    def get(model, identifier):
        return references.get(identifier) if model is SourceRecord else None

    def put(**kwargs):
        content = kwargs["content"]
        sha = hashlib.sha256(content).hexdigest()
        key = kwargs["source_id"] + "/2024/03/" + sha + ".json"
        contents[key] = content
        return BronzeArtifact(
            key, sha, kwargs["mime_type"], kwargs["url"], kwargs["fetched_at"], True, len(content)
        )

    session.add.side_effect, session.get.side_effect = add, get
    reader.put.side_effect = put
    with (
        patch("tests.e2e_data.synthetic_gold_dataset.require_synthetic_test_database"),
        patch("tests.e2e_data.source_backed_synthetic.require_synthetic_test_database"),
        patch("tests.e2e_data.synthetic_gold_dataset.BronzeStore", return_value=reader),
    ):
        counts = seed_synthetic_gold_data(session)
    observations = [row for row in rows if getattr(row, "__tablename__", None) in POLICIES]
    assert len(observations) == sum(
        counts[k] for k in ("price", "stock", "trade", "production", "weather", "cpi")
    )
    assert {row.__tablename__ for row in observations} == set(POLICIES)
    for row in observations:
        reference = references[row.source_record_id]
        content = contents[reference.object_key]
        assert hashlib.sha256(content).hexdigest() == reference.content_sha256
        assert reference.retrieved_via == "manual_upload"
        assert reference.mime_type == "application/json"
        assert row.evidence["authenticity"] == "synthetic" and row.evidence["verified"] is False
        verify_cells(content, reference.mime_type, bind_observation(row.__tablename__, row).proof)
    session.commit.assert_not_called()
