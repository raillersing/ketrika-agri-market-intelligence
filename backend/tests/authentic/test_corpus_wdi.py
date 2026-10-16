"""Official archived bytes and independent annotation; no network or market claims."""

import copy
import json

import pytest

from ketrika.core.corpus import CorpusError, load_manifest, validate_annotation, validate_manifest
from ketrika.core.registry import find_repo_root


def test_authentic_document_and_annotation() -> None:
    base = find_repo_root() / "backend"
    report = validate_manifest(base, load_manifest(base))
    assert set(report["authentic_documents"]) == {
        "tests/fixtures/authentic/world_bank_rtfp/mdg_close_estimates_20261015.json",
        "tests/fixtures/authentic/world_bank_rtfp/mdg_prices_20261015.json",
        "tests/fixtures/authentic/world_bank_rtfp/mdg_study_20261005.json",
        "tests/fixtures/authentic/world_bank_wdi/wdi_mdg_gdp_2022_2023.json",
    }
    assert report["authentic_annotations"] == 4
    assert report["verified_annotation_cells"] == 53


def test_golden_is_independent_and_bounded() -> None:
    base = find_repo_root() / "backend"
    golden = json.loads(
        (
            base / "tests/golden/authentic/world_bank_wdi/wdi_mdg_gdp_2022_2023.expected.json"
        ).read_text()
    )
    assert golden["metadata"]["method"] == "independent_transcription"
    assert golden["metadata"]["human_reviewed"] is False
    assert golden["metadata"]["records_annotated"] == golden["metadata"]["records_in_document"] == 2
    assert golden["metadata"]["publication_time"] is None
    original = json.loads((base / golden["metadata"]["document_path"]).read_text())
    assert len(original[1]) == golden["metadata"]["records_in_document"]
    assert {cell["path"][1] for cell in golden["cells"]} == {0, 1}


def test_unverified_sources_excluded() -> None:
    base = find_repo_root() / "backend"
    manifest = load_manifest(base)
    report = validate_manifest(base, manifest)
    authentic = set(report["authentic_documents"])
    for entry in manifest["entries"]:
        if entry["authenticity"] != "authentic":
            assert entry["path"] not in authentic


def test_authentic_annotation_refuses_generated_source() -> None:
    base = find_repo_root() / "backend"
    manifest = load_manifest(base)
    entries = {entry["path"]: entry for entry in manifest["entries"]}
    golden = copy.deepcopy(
        entries["tests/golden/authentic/world_bank_wdi/wdi_mdg_gdp_2022_2023.expected.json"]
    )
    golden["origin"]["reference"] = "tests/fixtures/miasa_odr/odr_bulletin_520.pdf"
    with pytest.raises(CorpusError):
        validate_annotation(base, golden, entries)
