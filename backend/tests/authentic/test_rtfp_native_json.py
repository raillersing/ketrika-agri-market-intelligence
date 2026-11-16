"""Archived packet parsing/shape checks, not current market or human qualification."""

import hashlib
import json
from uuid import uuid4

import pytest

from ketrika.connectors.base import RawArtifact
from ketrika.connectors.rtfp_json import parse_close_estimates
from ketrika.core.corpus import load_manifest, validate_annotation
from ketrika.core.registry import find_repo_root
from ketrika.core.schema_json import inspect_json_schema
from ketrika.core.schema_rtfp import WB_RTFP_JSON

DIRECTORY = "tests/fixtures/authentic/world_bank_rtfp/"


def packet():
    base = find_repo_root() / "backend"
    return tuple(
        (base / DIRECTORY / filename).read_bytes()
        for filename in (
            "mdg_close_estimates_20261015.json",
            "mdg_study_20261005.json",
        )
    )


def test_both_official_artifacts_match_exact_declared_variants():
    for content in packet():
        result = inspect_json_schema(content, WB_RTFP_JSON)
        assert result.passed, result.reasons
        assert result.content_sha256 == hashlib.sha256(content).hexdigest()


def test_official_estimates_parse_with_separate_context_and_independent_cells():
    data, study = packet()
    artifacts, objects = [], {}
    for content in (data, study):
        sha = hashlib.sha256(content).hexdigest()
        key = f"wb_rtfp_mdg/2026/10/{sha}.json"
        objects[key] = content
        artifacts.append(RawArtifact(str(uuid4()), key, sha, "application/json", "", True))

    class Reader:
        def get(self, key):
            return objects[key]

    result = parse_close_estimates(*artifacts, Reader())
    assert len(result.records) == 15
    assert [record.price_raw for record in result.records[:3]] == ["1082.69", "1046.47", "1113.51"]
    assert all(
        record.observed_or_imputed == "imputed" and record.actor_level == "unknown"
        for record in result.records
    )
    assert all(
        record.unit_raw == "KG" and record.product_raw == "Rice (local)"
        for record in result.records
    )
    base = find_repo_root() / "backend"
    entries = {entry["path"]: entry for entry in load_manifest(base)["entries"]}
    annotation = entries[
        "tests/golden/authentic/world_bank_rtfp/mdg_close_estimates_20261015.expected.json"
    ]
    assert validate_annotation(base, annotation, entries) == 15


@pytest.mark.parametrize(
    "change",
    [
        "extra_data",
        "boolean_price",
        "nonfinite_price",
        "numeric_unit",
        "extra_context",
        "ambiguous",
    ],
)
def test_unknown_structure_and_ambiguous_variants_are_refused(change):
    data, study = (json.loads(content) for content in packet())
    document = data
    if change == "extra_data":
        data["data"][0]["unknown"] = "not authorized"
    elif change == "boolean_price":
        data["data"][0]["c_rice"] = True
    elif change == "nonfinite_price":
        data["data"][0]["c_rice"] = "NaN"
    elif change == "numeric_unit":
        document = study
        study["additional"]["ticker_info"][2]["units"] = 1
    elif change == "extra_context":
        document = study
        study["additional"]["ticker_info"][2]["unknown"] = "not authorized"
    elif change == "ambiguous":
        data["additional"] = study["additional"]
    assert not inspect_json_schema(json.dumps(document).encode(), WB_RTFP_JSON).passed


def test_spatially_interpolated_accepts_both_numeric_and_string_decimal():
    """Non-regression test for Contabo production fix (ADR-166).

    World Bank RTFP API v2 may return spatially_interpolated as '0' (quoted string)
    or 0 (integer). Both must be verified by the DECIMAL shape without schema drift.
    """
    data, _ = (json.loads(content) for content in packet())
    # 1. Numeric 0 (as in static fixture)
    data["data"][0]["spatially_interpolated"] = 0
    inspection = inspect_json_schema(json.dumps(data).encode(), WB_RTFP_JSON)
    assert inspection.passed, f"Numeric 0 failed: {inspection.reasons}"

    # 2. String '0' (as returned by live WB RTFP API endpoint on Contabo VPS)
    data["data"][0]["spatially_interpolated"] = "0"
    inspection_str = inspect_json_schema(json.dumps(data).encode(), WB_RTFP_JSON)
    assert inspection_str.passed, f"String '0' failed: {inspection_str.reasons}"

    # 3. String '1'
    data["data"][0]["spatially_interpolated"] = "1"
    inspection_one = inspect_json_schema(json.dumps(data).encode(), WB_RTFP_JSON)
    assert inspection_one.passed, f"String '1' failed: {inspection_one.reasons}"

    # 4. Invalid non-decimal string must be rejected
    data["data"][0]["spatially_interpolated"] = "not_a_number"
    inspection_invalid = inspect_json_schema(json.dumps(data).encode(), WB_RTFP_JSON)
    assert not inspection_invalid.passed

