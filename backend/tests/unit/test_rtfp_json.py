"""Parser contract tests on explicit synthetic data/context artifacts."""

import hashlib
import json

import pytest

from ketrika.connectors.base import RawArtifact
from ketrika.connectors.rtfp_json import parse_close_estimates
from ketrika.core.provenance import ProofError
from tests.unit.test_provenance_rtfp import Reader, sample


def artifacts(references):
    return tuple(
        RawArtifact(
            str(item.source_record_id),
            item.object_key,
            item.content_sha256,
            item.mime_type,
            "https://example.invalid/synthetic",
            True,
        )
        for item in references.values()
    )


def test_close_estimate_preserves_raw_and_explicit_imputed_unknown_actor():
    _, _, references, objects = sample()
    primary, context = artifacts(references)
    result = parse_close_estimates(primary, context, Reader(objects))
    assert result.parser_version == "2.0.0"
    assert len(result.records) == 1
    record = result.records[0]
    assert (record.price_raw, record.price_value, record.unit_raw) == (
        "1234.56785",
        1234.5679,
        "KG",
    )
    assert (record.actor_level, record.observed_or_imputed, record.value_kind) == (
        "unknown",
        "imputed",
        "point",
    )
    assert record.period_end.isoformat() == "2024-02-29"
    assert record.evidence["provenance"]["context_source_record_id"] == context.source_record_id


@pytest.mark.parametrize(
    "case",
    [
        "country",
        "unit",
        "date",
        "ambiguous",
        "no_estimate",
        "nonfinite",
        "zero",
        "overflow",
        "boolean",
        "underflow",
        "float_loss",
    ],
)
def test_parser_refuses_missing_or_ambiguous_evidence(case):
    _, _, references, objects = sample()
    primary, context = artifacts(references)
    data = json.loads(objects[primary.object_key])
    study = json.loads(objects[context.object_key])
    if case == "country":
        data["data"][0]["ISO3"] = "XXX"
    elif case == "unit":
        del study["additional"]["ticker_info"][0]["units"]
    elif case == "date":
        data["data"][0]["price_date"] = "2024-02-02"
    elif case == "ambiguous":
        study["additional"]["ticker_info"] *= 2
    elif case == "no_estimate":
        del data["data"][0]["c_rice"]
    else:
        data["data"][0]["c_rice"] = {
            "nonfinite": "NaN",
            "zero": "0",
            "overflow": "1e30",
            "boolean": True,
            "underflow": "0.000000001",
            "float_loss": "99999999999999.1234",
        }[case]
    updated = []
    for artifact, document in ((primary, data), (context, study)):
        content = json.dumps(document).encode()
        sha = hashlib.sha256(content).hexdigest()
        key = f"wb_rtfp_mdg/2026/10/{sha}.json"
        objects[key] = content
        updated.append(
            RawArtifact(artifact.source_record_id, key, sha, artifact.mime_type, artifact.url, True)
        )
    with pytest.raises(ProofError):
        parse_close_estimates(*updated, Reader(objects))
