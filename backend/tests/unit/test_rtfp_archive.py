"""Synthetic deterministic parsing regressions, not a publisher benchmark."""

import hashlib
from dataclasses import replace

import pytest

from ketrika.connectors.base import RawArtifact
from ketrika.connectors.rtfp_archive import parse_close_estimates
from ketrika.core.provenance import ProofError
from ketrika.core.schema_wb_archive import COLUMNS, WBArchiveSchemaContract, inspect_archive_schema
from tests.unit.test_provenance_wb_archive import proof_example_data
from tests.unit.test_wb_archive import HEADERS, ROW, packet


@pytest.fixture
def original():
    claim, references, objects, reader = proof_example_data()

    def make(changes=None, headers=COLUMNS, additional=None):
        values = dict.fromkeys(headers, "")
        values.update(dict(zip(HEADERS, ROW, strict=True)))
        values.update(changes or {})
        data_rows = [[values.get(column, "") for column in headers]]
        if additional:
            extra = values | additional
            data_rows.append([extra.get(column, "") for column in headers])
        content = packet(rows=data_rows, headers=headers)
        digest = hashlib.sha256(content).hexdigest()
        key = f"wb_rtfp_mdg/2026/11/{digest}.zip"
        ref = replace(references[claim.source_record_id], content_sha256=digest, object_key=key)
        objects[key] = content
        primary = RawArtifact(
            str(ref.source_record_id),
            key,
            digest,
            ref.mime_type,
            "https://microdata.worldbank.org/api/downloads/download/MDG_2021_RTFP_v02_M/360780?filename=MDG_RTFP_mkt_2007_2026-10-05.zip",
            True,
        )
        context = next(
            item for item in references.values() if item.source_record_id != claim.source_record_id
        )
        metadata = RawArtifact(
            str(context.source_record_id),
            context.object_key,
            context.content_sha256,
            context.mime_type,
            "https://microdata.worldbank.org/metadata/export/8240/json",
            True,
        )
        return primary, metadata, reader, content

    return make


def test_original_close_estimate_preserves_raw_scope_and_semantics(original):
    primary, context, reader, _ = original()
    result = parse_close_estimates(primary, context, reader)
    assert result.parser_version == "3.0.0" and len(result.records) == 1
    row = result.records[0]
    assert row.price_raw == "1234.567890" and row.price_value == 1234.5679
    assert row.product_raw == "Rice (local)" and row.unit_raw == "KG"
    assert row.location_raw == "Market Average" and row.actor_level == "unknown"
    assert row.observed_or_imputed == "imputed" and row.value_kind == "point"
    assert row.evidence["provenance"]["format"] == "rtfp_zip_csv_v1"


@pytest.mark.parametrize(
    "changes",
    [
        {"c_rice": "NaN"},
        {"c_rice": "Infinity"},
        {"c_rice": "-1"},
        {"c_rice": "0"},
        {"c_rice": "1e-20"},
        {"currency": "USD"},
        {"adm1_name": "Region"},
        {"lat": "-20"},
    ],
)
def test_unsupported_values_and_national_identity_refused(original, changes):
    primary, context, reader, _ = original(changes)
    with pytest.raises(ProofError):
        parse_close_estimates(primary, context, reader)


def test_other_markets_are_outside_scope_and_missing_values_are_not_zero(original):
    primary, context, reader, _ = original(additional={"geo_id": "region1", "mkt_name": "Other"})
    assert len(parse_close_estimates(primary, context, reader).records) == 1
    for changes in ({"c_rice": ""}, {"price_date": "2019-12-01"}, {"price_date": "2026-11-01"}):
        primary, context, reader, _ = original(changes)
        with pytest.raises(ProofError, match="scope_empty"):
            parse_close_estimates(primary, context, reader)


def test_new_column_is_schema_drift_not_a_successful_empty_parse(original):
    primary, context, reader, content = original(headers=(*COLUMNS, "unexpected"))
    with pytest.raises(ProofError, match="schema_drift"):
        parse_close_estimates(primary, context, reader)
    assert not inspect_archive_schema(content, WBArchiveSchemaContract()).passed


def test_declared_structure_checks_all_rows(original):
    _, _, _, content = original()
    inspection = inspect_archive_schema(content, WBArchiveSchemaContract())
    assert inspection.passed and inspection.rows == 1 and inspection.columns == 46


def test_wrong_source_url_and_wrong_context_units_refused(original):
    primary, context, reader, _ = original()
    with pytest.raises(ProofError, match="source_url_invalid"):
        parse_close_estimates(
            replace(primary, url="https://example.org/test-only"), context, reader
        )
    with pytest.raises(ProofError):
        parse_close_estimates(
            primary, replace(context, url="https://example.org/test-only"), reader
        )
