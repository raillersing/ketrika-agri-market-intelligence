"""Real Dagster graph/control execution; helper simulated, not SQL evidence."""

import pytest
from dagster import AssetCheckResult, Definitions, asset, asset_check

from ketrika.pipelines.factory import build_gold_refresh_asset


@pytest.mark.parametrize("passed", [False, True])
def test_blocking_check_controls_connected_gold(passed, monkeypatch):
    calls = []

    @asset(name="dummy_gold_graph__silver")
    def silver():
        return {"scope": "inert synthetic Silver"}

    @asset_check(asset=silver, name="measured_test_condition", blocking=True)
    def check():
        return AssetCheckResult(passed=passed)

    def fake_refresh():
        calls.append("refresh_helper")
        return {"scope": "simulated; not SQL or Gold qualification"}

    monkeypatch.setattr("ketrika.pipelines.factory._refresh_gold", fake_refresh)
    gold = build_gold_refresh_asset([silver])
    assert gold.asset_deps[gold.key] == {silver.key}
    defs = Definitions(assets=[silver, gold], asset_checks=[check])
    result = defs.resolve_implicit_global_asset_job_def().execute_in_process(raise_on_error=False)
    assert result.success is passed
    assert calls == (["refresh_helper"] if passed else [])


def test_duplicate_silver_key_refused():
    @asset(name="dummy_same__silver")
    def silver():
        return None

    with pytest.raises(ValueError, match="duplicate_silver_key"):
        build_gold_refresh_asset([silver, silver])


def test_non_silver_key_refused():
    @asset(name="dummy_wrong__bronze")
    def bronze():
        return None

    with pytest.raises(ValueError, match="invalid_silver_key"):
        build_gold_refresh_asset([bronze])


def test_all_silver_dependencies_are_explicit():
    @asset(name="dummy_first__silver")
    def first():
        return None

    @asset(name="dummy_second__silver")
    def second():
        return None

    gold = build_gold_refresh_asset([first, second])
    assert gold.asset_deps[gold.key] == {first.key, second.key}
    Definitions(assets=[first, second, gold]).resolve_implicit_global_asset_job_def()


def test_actual_repository_gold_has_every_included_silver_dependency():
    from dagster import AssetKey

    from ketrika.pipelines.definitions import defs, gold_refresh_asset, source_inventory

    expected = {
        AssetKey(f"{entry.source_id}__silver") for entry in source_inventory if entry.included
    }
    assert len(expected) == 5
    assert AssetKey("instat_nipc__silver") not in expected
    assert gold_refresh_asset.asset_deps[gold_refresh_asset.key] == expected
    assert defs.get_repository_def() is not None
