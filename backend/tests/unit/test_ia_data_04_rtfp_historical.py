"""Unit tests for IA-DATA-04: Full historical RTFP archive parser for markets & multi-commodity PPN."""

import hashlib
import json
from datetime import date
from uuid import uuid4

import pytest

from ketrika.connectors.base import RawArtifact
from ketrika.connectors.rtfp_archive import parse_close_estimates as parse_close_estimates_v3
from ketrika.connectors.rtfp_market_archive import (
    PARSER_VERSION,
    parse_market_estimates,
)
from ketrika.core.provenance import ProofError
from ketrika.core.provenance_wb_market import FORMAT
from ketrika.core.schema_contracts import (
    DECLARED_SCHEMA_BINDINGS,
    SchemaContractRegistry,
)
from ketrika.core.schema_wb_archive import COLUMNS
from tests.unit.test_wb_archive import packet


def full_study_metadata():
    return {
        "study_desc": {
            "title_statement": {
                "idno": "MDG_2021_RTFP_v02_M",
                "title": "Monthly food price estimates by product and market",
            }
        },
        "additional": {
            "ticker_info": [
                {
                    "iso3": "MDG",
                    "ticker": "exchange_rate_unofficial",
                    "full_name": "Unofficial exchange rate",
                    "units": "USD/LCU",
                },
                {
                    "iso3": "MDG",
                    "ticker": "food_price_index",
                    "full_name": "Food Price Index",
                    "units": "LCU, Indexed",
                },
                {
                    "iso3": "MDG",
                    "ticker": "rice",
                    "full_name": "Rice (local)",
                    "units": "KG",
                },
                {
                    "iso3": "MDG",
                    "ticker": "sugar",
                    "full_name": "Sugar",
                    "units": "KG",
                },
                {
                    "iso3": "MDG",
                    "ticker": "wheat_flour",
                    "full_name": "Wheat flour",
                    "units": "KG",
                },
            ]
        },
    }


def make_market_fixtures(rows_data=None):
    primary_id, context_id = uuid4(), uuid4()

    default_rows = []
    if rows_data is None:
        # Row 0: National 2026-09-01 observed
        r0 = dict.fromkeys(COLUMNS, "")
        r0.update(
            {
                "ISO3": "MDG",
                "country": "Madagascar",
                "adm1_name": "Market Average",
                "adm2_name": "Market Average",
                "mkt_name": "Market Average",
                "geo_id": "gid_mdg_national_average",
                "price_date": "2026-09-01",
                "currency": "MGA",
                "spatially_interpolated": "0",
                "c_rice": "3500.00",
                "c_sugar": "4200.50",
                "c_wheat_flour": "3800.25",
            }
        )
        # Row 1: Subnational market 2007-01-01 historical interpolated
        r1 = dict.fromkeys(COLUMNS, "")
        r1.update(
            {
                "ISO3": "MDG",
                "country": "Madagascar",
                "adm1_name": "Analamanga",
                "adm2_name": "Antananarivo Renivohitra",
                "mkt_name": "Analakely",
                "geo_id": "mkt_mdg_analakely",
                "price_date": "2007-01-01",
                "currency": "MGA",
                "spatially_interpolated": "1",
                "c_rice": "1100.00",
                "c_sugar": "1800.00",
                "c_wheat_flour": "1500.00",
            }
        )
        default_rows = [
            [r0[col] for col in COLUMNS],
            [r1[col] for col in COLUMNS],
        ]
    else:
        for r_dict in rows_data:
            base = dict.fromkeys(COLUMNS, "")
            base.update(r_dict)
            default_rows.append([base[col] for col in COLUMNS])

    zip_bytes = packet(rows=default_rows, headers=COLUMNS)
    zip_digest = hashlib.sha256(zip_bytes).hexdigest()
    zip_key = f"wb_rtfp_mdg/2026/11/{zip_digest}.zip"

    json_bytes = json.dumps(full_study_metadata()).encode()
    json_digest = hashlib.sha256(json_bytes).hexdigest()
    json_key = f"wb_rtfp_mdg/2026/11/{json_digest}.json"

    objects = {
        zip_key: zip_bytes,
        json_key: json_bytes,
    }

    class Reader:
        def get(self, key):
            return objects[key]

    reader = Reader()

    primary = RawArtifact(
        str(primary_id),
        zip_key,
        zip_digest,
        "application/zip",
        "https://microdata.worldbank.org/api/downloads/download/MDG_2021_RTFP_v02_M/360780?filename=MDG_RTFP_mkt_2007_2026-10-05.zip",
        True,
    )
    context = RawArtifact(
        str(context_id),
        json_key,
        json_digest,
        "application/json",
        "https://microdata.worldbank.org/metadata/export/8240/json",
        True,
    )

    return primary, context, reader, objects


def test_multi_commodity_and_market_extraction():
    primary, context, reader, _ = make_market_fixtures()
    result = parse_market_estimates(primary, context, reader)

    assert result.parser_version == PARSER_VERSION
    # 2 rows * 3 commodities = 6 records
    assert len(result.records) == 6

    # Verify commodity types
    commodities = {r.product_raw for r in result.records}
    assert commodities == {"Rice (local)", "Sugar", "Wheat flour"}

    # Verify market locations
    locations = {r.location_raw for r in result.records}
    assert locations == {"Market Average", "Analakely"}

    # Verify unit and currency
    for rec in result.records:
        assert rec.unit_raw == "KG"
        assert rec.currency_raw == "MGA"
        assert rec.evidence["provenance"]["format"] == FORMAT
        assert rec.evidence["provenance"]["version"] == 2


def test_spatial_interpolation_distinction():
    primary, context, reader, _ = make_market_fixtures()
    result = parse_market_estimates(primary, context, reader)

    market_avg_records = [r for r in result.records if r.location_raw == "Market Average"]
    analakely_records = [r for r in result.records if r.location_raw == "Analakely"]

    # Market average has spatially_interpolated="0" -> observed / point
    for rec in market_avg_records:
        assert rec.observed_or_imputed == "observed"
        assert rec.value_kind == "point"

    # Analakely has spatially_interpolated="1" -> imputed / imputed
    for rec in analakely_records:
        assert rec.observed_or_imputed == "imputed"
        assert rec.value_kind == "imputed"


def test_historical_depth_back_to_2007():
    r_2007 = {
        "ISO3": "MDG",
        "country": "Madagascar",
        "adm1_name": "Diana",
        "adm2_name": "Antsiranana I",
        "mkt_name": "Antsiranana Bazar",
        "geo_id": "mkt_mdg_antsiranana",
        "price_date": "2007-01-01",
        "currency": "MGA",
        "spatially_interpolated": "0",
        "c_rice": "950.00",
        "c_sugar": "",
        "c_wheat_flour": "",
    }
    r_too_old = {
        "ISO3": "MDG",
        "country": "Madagascar",
        "adm1_name": "Diana",
        "adm2_name": "Antsiranana I",
        "mkt_name": "Antsiranana Bazar",
        "geo_id": "mkt_mdg_antsiranana",
        "price_date": "2006-12-01",
        "currency": "MGA",
        "spatially_interpolated": "0",
        "c_rice": "900.00",
        "c_sugar": "",
        "c_wheat_flour": "",
    }
    primary, context, reader, _ = make_market_fixtures([r_2007, r_too_old])
    result = parse_market_estimates(primary, context, reader)

    # Only 2007-01-01 should be kept; 2006-12-01 is out of range
    assert len(result.records) == 1
    assert result.records[0].period_start == date(2007, 1, 1)
    assert result.records[0].price_value == 950.00


def test_schema_contract_bindings_include_v4():
    registry = SchemaContractRegistry(DECLARED_SCHEMA_BINDINGS)
    binding_json = registry.resolve("wb_rtfp_mdg", "4.0.0", "application/json")
    assert binding_json is not None

    binding_zip = registry.resolve("wb_rtfp_mdg", "4.0.0", "application/zip")
    assert binding_zip is not None

    binding_stream = registry.resolve("wb_rtfp_mdg", "4.0.0", "application/octet-stream")
    assert binding_stream is not None


def test_provenance_verification_passes_and_detects_tampering():
    primary, context, reader, objects = make_market_fixtures()
    result = parse_market_estimates(primary, context, reader)
    assert len(result.records) == 6

    # Test tampering: if raw archive is modified, verification fails
    bad_bytes = b"bad corrupted archive"
    objects[primary.object_key] = bad_bytes
    with pytest.raises(ProofError, match="rtfp_artifact_invalid"):
        parse_market_estimates(primary, context, reader)


def test_coexistence_with_v3_national_parser():
    # v3 parser expects row with national identity and 2020+
    r_v3 = dict.fromkeys(COLUMNS, "")
    r_v3.update(
        {
            "ISO3": "MDG",
            "country": "Madagascar",
            "adm1_name": "Market Average",
            "adm2_name": "Market Average",
            "mkt_name": "Market Average",
            "geo_id": "gid_mdg_national_average",
            "price_date": "2026-09-01",
            "currency": "MGA",
            "spatially_interpolated": "0",
            "c_rice": "3500.00",
            "c_sugar": "4200.50",
            "c_wheat_flour": "3800.25",
        }
    )
    zip_bytes = packet(rows=[[r_v3[col] for col in COLUMNS]], headers=COLUMNS)
    zip_digest = hashlib.sha256(zip_bytes).hexdigest()
    zip_key = f"wb_rtfp_mdg/2026/11/{zip_digest}.zip"

    json_bytes = json.dumps(full_study_metadata()).encode()
    json_digest = hashlib.sha256(json_bytes).hexdigest()
    json_key = f"wb_rtfp_mdg/2026/11/{json_digest}.json"

    objects = {zip_key: zip_bytes, json_key: json_bytes}

    class Reader:
        def get(self, key):
            return objects[key]

    reader = Reader()
    primary = RawArtifact(
        str(uuid4()),
        zip_key,
        zip_digest,
        "application/zip",
        "https://microdata.worldbank.org/api/downloads/download/MDG_2021_RTFP_v02_M/360780?filename=MDG_RTFP_mkt_2007_2026-10-05.zip",
        True,
    )
    context = RawArtifact(
        str(uuid4()),
        json_key,
        json_digest,
        "application/json",
        "https://microdata.worldbank.org/metadata/export/8240/json",
        True,
    )

    # v3 should work and extract only c_rice for national
    v3_result = parse_close_estimates_v3(primary, context, reader)
    assert v3_result.parser_version == "3.0.0"
    assert len(v3_result.records) == 1
    assert v3_result.records[0].product_raw == "Rice (local)"

    # v4 should work and extract all 3 commodities
    v4_result = parse_market_estimates(primary, context, reader)
    assert v4_result.parser_version == "4.0.0"
    assert len(v4_result.records) == 3
