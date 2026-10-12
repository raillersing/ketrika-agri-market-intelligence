"""Prepared batch routing and stale-write safeguards; no SQL/S3 qualification."""

from datetime import date
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from ketrika.connectors.base import ParseResult
from ketrika.connectors.records import PriceRecord
from ketrika.connectors.stages import consume_connector_silver
from ketrika.core.models.db import Product
from ketrika.normalize.price_loader import NormalizedLoad
from ketrika.normalize.price_references import resolve_location, resolve_product, unit_factor
from tests.unit.test_connector_stages import fixture


@pytest.mark.parametrize("resolver", ["product", "location", "unit"])
def test_fresh_reads_refuse_pending_reference_without_overwriting_it(resolver):
    session = Mock(spec=Session)
    row = Product(canonical_name_fr="Keep this pending value")
    session.new, session.dirty, session.deleted = [], [row], []
    with pytest.raises(ValueError, match="^normalization_reference_changes_pending$"):
        if resolver == "product":
            resolve_product(session, "Synthetic commodity", "dummy_snapshot")
        elif resolver == "location":
            resolve_location(session, "Synthetic place", "dummy_snapshot")
        else:
            unit_factor(session, "kg", uuid4())
    assert row.canonical_name_fr == "Keep this pending value"
    session.execute.assert_not_called()
    session.scalars.assert_not_called()


def prices():
    return [
        PriceRecord(
            product_raw=f"Synthetic {index}",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 1),
            price_raw="2850",
            unit_raw="kg",
        )
        for index in range(2)
    ]


def test_batch_prices_share_one_context_and_keep_http_offline():
    connector, ctx, session, batch, *_ = fixture()
    records = prices()
    connector.parse.return_value = ParseResult(parser_version=batch.parser_version, records=records)
    with (
        patch("ketrika.normalize.reference_snapshot.prepare_reference_snapshot") as prepare,
        patch(
            "ketrika.normalize.price_loader.load_normalized_price",
            return_value=NormalizedLoad("inserted", uuid4(), 0),
        ) as normalize,
    ):
        stats = consume_connector_silver(connector, ctx, session, batch)
    prepare.assert_called_once_with(session, ctx.bronze_store)
    assert normalize.call_count == stats["n_inserted"] == 2
    assert all(
        call.kwargs["reference_snapshot"] is prepare.return_value
        for call in normalize.call_args_list
    )
    connector.fetch.assert_not_called()
    connector.discover.assert_not_called()
    session.commit.assert_not_called()


def test_failed_snapshot_prepare_never_calls_normalizer_or_reports_success():
    connector, ctx, session, batch, *_ = fixture()
    connector.parse.return_value = ParseResult(
        parser_version=batch.parser_version, records=prices()
    )
    with (
        patch(
            "ketrika.normalize.reference_snapshot.prepare_reference_snapshot",
            side_effect=ValueError("normalization_reference_manifest_changed"),
        ),
        patch("ketrika.normalize.price_loader.load_normalized_price") as normalize,
    ):
        with pytest.raises(ValueError, match="^normalization_reference_manifest_changed$"):
            consume_connector_silver(connector, ctx, session, batch)
    normalize.assert_not_called()
    session.commit.assert_not_called()
