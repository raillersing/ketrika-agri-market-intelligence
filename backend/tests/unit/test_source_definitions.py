"""Pure definition construction, no DB/network or live source qualification."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.registry import list_registered_connectors
from ketrika.core.registry import get_source
from ketrika.pipelines.factory import _cadence_to_cron, build_source_assets
from ketrika.pipelines.source_definitions import (
    SourceDefinitionsError,
    build_registered_source_definitions,
)


def connector_for(source_id):
    return type("LocalDefinitionConnector", (DummyCsvConnector,), {"source_id": source_id})


def test_actual_definitions_inventory_matches_eligible_registered_sources():
    from ketrika.pipelines.definitions import (
        all_assets,
        all_checks,
        all_schedules,
        defs,
        source_inventory,
    )

    registered = {
        key: get_source(key)
        for key in list_registered_connectors()
        if not key.startswith(("dummy_", "fixture_"))
    }
    eligible = {
        key
        for key, source in registered.items()
        if source.status in ("active", "degraded") and source.crawl_permission != "forbidden"
    }
    included = {entry.source_id for entry in source_inventory if entry.included}
    assert included == eligible
    assert len(all_assets) == 3 + 2 * len(eligible) == 15
    assert len(all_checks) == len(eligible) == 6
    assert len(all_schedules) == len(eligible) == 6
    assert {schedule.name for schedule in all_schedules} == {
        f"{source_id}__schedule" for source_id in eligible
    }
    excluded = {entry.source_id: entry.reason for entry in source_inventory if not entry.included}
    assert excluded["nasa_power"] == excluded["wfp_hdx_mdg"] == "disabled"
    assert excluded["dummy_csv"] == "fixture"
    assert all(schedule.execution_timezone == "Indian/Antananarivo" for schedule in all_schedules)
    assert defs.get_repository_def() is not None


@pytest.mark.parametrize(
    "status,permission,reason",
    [
        ("disabled", "public_open_data", "disabled"),
        ("planned", "public_open_data", "planned"),
        ("active", "forbidden", "forbidden"),
    ],
)
def test_ineligible_source_never_calls_builder(status, permission, reason):
    definition = get_source("wb_rtfp_mdg").model_copy(
        update={
            "status": status,
            "crawl_permission": permission,
        }
    )
    builder = MagicMock()
    result = build_registered_source_definitions(
        {definition.source_id: connector_for(definition.source_id)},
        resolve=lambda _: definition,
        build=builder,
    )
    builder.assert_not_called()
    assert result.assets == result.checks == result.schedules == ()
    assert result.inventory[0].reason == reason
    assert not result.inventory[0].included


@pytest.mark.parametrize("source_id", ["dummy_test", "fixture_test"])
def test_fixture_namespace_never_resolves_or_builds_automatic_definitions(source_id):
    resolve, build = MagicMock(), MagicMock()
    result = build_registered_source_definitions(
        {source_id: connector_for(source_id)},
        resolve=resolve,
        build=build,
    )
    resolve.assert_not_called()
    build.assert_not_called()
    assert result.inventory[0].reason == "fixture"
    assert result.assets == result.checks == result.schedules == ()


def test_connector_identity_mismatch_is_explicit():
    with pytest.raises(SourceDefinitionsError, match="connector_identity_mismatch"):
        build_registered_source_definitions({"wb_rtfp_mdg": DummyCsvConnector})


@pytest.mark.parametrize("missing_method", ["discover", "fetch", "parse"])
def test_incomplete_connector_class_is_explicit(missing_method):
    incomplete = type(
        "IncompleteConnector",
        (DummyCsvConnector,),
        {
            "source_id": "wb_rtfp_mdg",
            missing_method: None,
        },
    )
    with pytest.raises(SourceDefinitionsError, match="invalid_connector_definition"):
        build_registered_source_definitions({"wb_rtfp_mdg": incomplete})


def test_registered_instance_is_not_a_connector_class():
    with pytest.raises(SourceDefinitionsError, match="invalid_connector_definition"):
        build_registered_source_definitions({"wb_rtfp_mdg": connector_for("wb_rtfp_mdg")()})


def test_resolution_error_is_explicit_and_does_not_expose_registry_text():
    resolver = MagicMock(side_effect=KeyError("untrusted registry body"))
    with pytest.raises(SourceDefinitionsError, match="source_resolution_failed") as error:
        build_registered_source_definitions(
            {"unknown_real": connector_for("unknown_real")},
            resolve=resolver,
        )
    assert "KeyError" in str(error.value)
    assert "untrusted registry body" not in str(error.value)
    assert error.value.__cause__ is None


def test_resolver_identity_mismatch_is_explicit():
    with pytest.raises(SourceDefinitionsError, match="source_definition_mismatch"):
        build_registered_source_definitions(
            {"miasa_odr": connector_for("miasa_odr")},
            resolve=lambda _: get_source("wb_rtfp_mdg"),
        )


def test_builder_failure_is_explicit_without_partial_result_or_error_body():
    builder = MagicMock(side_effect=RuntimeError("untrusted builder body"))
    with pytest.raises(SourceDefinitionsError, match="source_construction_failed") as error:
        build_registered_source_definitions(
            {"wb_rtfp_mdg": connector_for("wb_rtfp_mdg")},
            build=builder,
        )
    assert "RuntimeError" in str(error.value)
    assert "untrusted builder body" not in str(error.value)


def test_invalid_bundle_is_not_silently_omitted():
    bundle = build_source_assets(connector_for("wb_rtfp_mdg"))
    with pytest.raises(SourceDefinitionsError, match="source_construction_failed"):
        build_registered_source_definitions(
            {"wb_rtfp_mdg": connector_for("wb_rtfp_mdg")},
            build=lambda _: replace(bundle, checks=[]),
        )


@pytest.mark.parametrize(
    "status,permission",
    [
        ("disabled", "public_open_data"),
        ("planned", "public_open_data"),
        ("active", "forbidden"),
    ],
)
def test_direct_factory_has_no_schedule_for_ineligible_source(status, permission):
    definition = get_source("wb_rtfp_mdg").model_copy(
        update={
            "status": status,
            "crawl_permission": permission,
        }
    )
    with patch("ketrika.pipelines.factory.get_source", return_value=definition):
        assert build_source_assets(connector_for(definition.source_id)).schedule is None


@pytest.mark.parametrize(
    "cadence,expected",
    [
        ("daily", "0 6 * * *"),
        ("weekly", "0 7 * * 1"),
        ("monthly", "0 8 1 * *"),
        ("quarterly", "0 9 1 1,4,7,10 *"),
        ("annual", "0 10 1 1 *"),
        ("event", None),
        ("static", None),
    ],
)
def test_cadence_mapping_is_explicit(cadence, expected):
    assert _cadence_to_cron(cadence) == expected


def test_unknown_cadence_never_gets_an_invented_schedule():
    with pytest.raises(ValueError, match="unsupported_source_cadence"):
        _cadence_to_cron("hourly")


def test_factory_unknown_real_source_is_explicit():
    with pytest.raises(ValueError, match="unregistered_source_definition"):
        build_source_assets(connector_for("unregistered_real"))


def test_empty_registry_is_explicitly_empty_not_source_qualification():
    result = build_registered_source_definitions({})
    assert result.assets == result.checks == result.schedules == result.inventory == ()
