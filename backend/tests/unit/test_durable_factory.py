"""Actual asset compute routing with owners mocked; no SQL claim."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.stages import BronzeBatch
from ketrika.pipelines.factory import build_source_assets


def test_bronze_asset_delegates_transaction_ownership_and_dagster_identity():
    context = MagicMock()
    context.run.run_id = str(uuid4())
    batch = BronzeBatch("dummy_csv", uuid4(), "1.0.1", ())
    bundle = build_source_assets(DummyCsvConnector)
    with (
        patch("ketrika.pipelines.factory.execute_durable_bronze", return_value=batch) as owner,
        patch("ketrika.pipelines.factory.BronzeStore"),
        patch("ketrika.pipelines.factory.PoliteHttpClient"),
    ):
        result = bundle.bronze_asset.node_def.compute_fn.decorated_fn(context)
    assert result is batch
    connector, run_context = owner.call_args.args
    assert isinstance(connector, DummyCsvConnector)
    assert run_context.source_id == "dummy_csv"
    assert run_context.metadata == {"dagster_run_id": context.run.run_id}


def test_silver_asset_delegates_exact_batch_without_a_caller_transaction():
    context = MagicMock()
    batch = BronzeBatch("dummy_csv", uuid4(), "1.0.1", ())
    bundle = build_source_assets(DummyCsvConnector)
    stats = {"n_inserted": 3}
    with (
        patch("ketrika.pipelines.factory.execute_durable_silver", return_value=stats) as owner,
        patch("ketrika.pipelines.factory.BronzeStore"),
        patch("ketrika.pipelines.factory.get_session") as old_transaction,
    ):
        result = bundle.silver_asset.node_def.compute_fn.decorated_fn(context, batch)
    assert result is stats and owner.call_args.args[2] is batch
    assert owner.call_args.args[1].source_id == "dummy_csv"
    old_transaction.assert_not_called()
