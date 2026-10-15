"""Acquired official bytes and partial independent annotations, not a collector gate."""

import json
from decimal import Decimal

from ketrika.core.corpus import load_manifest, validate_annotation, validate_manifest
from ketrika.core.registry import find_repo_root


def test_official_bounded_madagascar_sample_and_partial_scope():
    base = find_repo_root() / "backend"
    path = "tests/fixtures/authentic/world_bank_rtfp/mdg_prices_20261015.json"
    manifest = load_manifest(base)
    assert path in validate_manifest(base, manifest)["authentic_documents"]
    payload = json.loads((base / path).read_bytes(), parse_float=Decimal)
    rows = payload["data"]
    assert len(rows) == payload["rows_count"] == 15
    assert all(row["ISO3"] == "MDG" and row["currency"] == "MGA" for row in rows)
    assert all(
        Decimal(str(row["rice"])).is_finite() and Decimal(str(row["rice"])) > 0 for row in rows
    )
    golden = json.loads(
        (
            base / "tests/golden/authentic/world_bank_rtfp/mdg_prices_20261015.expected.json"
        ).read_bytes()
    )
    assert golden["metadata"]["records_annotated"] == 3 < len(rows)
    assert golden["metadata"]["human_reviewed"] is False
    assert golden["metadata"]["publication_time"] is None


def test_independent_price_and_context_annotations_are_checked_against_raw_bytes():
    base = find_repo_root() / "backend"
    entries = {entry["path"]: entry for entry in load_manifest(base)["entries"]}
    prices = "tests/golden/authentic/world_bank_rtfp/mdg_prices_20261015.expected.json"
    context = "tests/golden/authentic/world_bank_rtfp/mdg_study_20261005.expected.json"
    assert validate_annotation(base, entries[prices], entries) == 18
    assert validate_annotation(base, entries[context], entries) == 10
    assert entries[prices]["rights"] == entries[context]["rights"]


def test_context_units_remain_separate_and_do_not_invent_observed_prices():
    base = find_repo_root() / "backend"
    prices = json.loads(
        (base / "tests/fixtures/authentic/world_bank_rtfp/mdg_prices_20261015.json").read_bytes()
    )
    study = json.loads(
        (base / "tests/fixtures/authentic/world_bank_rtfp/mdg_study_20261005.json").read_bytes()
    )
    assert study["study_desc"]["version_statement"]["version_date"] == "2026/10/05"
    assert study["additional"]["ticker_info"][2]["ticker"] == "rice"
    assert study["additional"]["ticker_info"][2]["units"] == "KG"
    assert all("unit" not in row and "observed_or_imputed" not in row for row in prices["data"])
    # These are verified source facts, not a license to inject defaults into Silver.
