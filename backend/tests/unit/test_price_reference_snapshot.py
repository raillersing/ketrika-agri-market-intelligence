"""Prepared loader binding on inert sessions; not actual snapshot use."""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from ketrika.normalize.price_loader import load_normalized_price
from ketrika.normalize.reference_snapshot import ReferenceSnapshot
from tests.unit.test_price_loader import environment, record


def test_context_evidence_replaces_untrusted_normalization_and_compares_snapshot_sha():
    session, reference, product, location, factor = environment()
    snapshot = Mock(spec=ReferenceSnapshot)
    metadata = {
        "sha256": "a" * 64,
        "object_key": "reference_manifest/2026/10/" + "a" * 64 + ".json",
        "source_verified": False,
    }
    rec = record(evidence={"normalization": {"reference_snapshot": {"sha256": "untrusted"}}})
    captured = []

    def loader(*args, **kwargs):
        captured.append(args[3](uuid4()))
        assert kwargs["evidence_fields"] == {
            ("normalization", "value_kind"): "point",
            ("normalization", "reference_snapshot", "sha256"): "a" * 64,
        }
        return "inserted", captured[0].observation_id

    with (
        patch(
            "ketrika.normalize.price_loader.reference_snapshot_evidence", return_value=metadata
        ) as validate,
        patch("ketrika.normalize.price_loader.resolve_product", return_value=product),
        patch("ketrika.normalize.price_loader.resolve_location", return_value=location),
        patch("ketrika.normalize.price_loader.unit_factor", return_value=factor),
        patch(
            "ketrika.normalize.price_loader.load_observation_with_supersession", side_effect=loader
        ),
    ):
        load_normalized_price(
            session, rec, "dummy_normalize", reference, reference_snapshot=snapshot
        )
    validate.assert_called_once_with(session, snapshot)
    assert captured[0].evidence["normalization"]["reference_snapshot"] == metadata
    assert rec.evidence["normalization"]["reference_snapshot"]["sha256"] == "untrusted"
    session.commit.assert_not_called()


def test_invalid_context_refuses_before_resolution_or_observation_load():
    session, reference, *_ = environment()
    with (
        patch(
            "ketrika.normalize.price_loader.reference_snapshot_evidence",
            side_effect=ValueError("normalization_reference_context_invalid"),
        ),
        patch("ketrika.normalize.price_loader.resolve_product") as product,
        patch("ketrika.normalize.price_loader.load_observation_with_supersession") as loader,
    ):
        with pytest.raises(ValueError, match="^normalization_reference_context_invalid$"):
            load_normalized_price(
                session,
                record(),
                "dummy_normalize",
                reference,
                reference_snapshot=Mock(spec=ReferenceSnapshot),
            )
    product.assert_not_called()
    loader.assert_not_called()
