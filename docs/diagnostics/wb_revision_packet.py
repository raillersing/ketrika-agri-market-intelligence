"""Offline assembly of original WB editions and independently transcribed cells.

Writes a new corpus directory only. No database, HTTP, ingestion or Gold.
Original receipts remain immutable and retain their initial unqualified status.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ketrika.core.corpus import validate_manifest
from ketrika.pipelines.rebuild_qualification import require_network_none

SOURCE = "wb_rtfp_mdg"
CATALOGUE = "https://microdata.worldbank.org/catalog/8240/data-api"
CONTEXT_SHA = "4a9e254e14c65ca5d3c85d69362f94ca4ccaf46b8e68cfbf88f300df6c122860"
RIGHTS = {
    "status": "verified",
    "licence": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
    "evidence": "https://data.worldbank.org/summary-terms-of-use",
    "dataset_evidence": "https://microdata.worldbank.org/metadata/export/8240/json",
    "attribution": (
        "Andree, B. P. J. (2021). Monthly food price estimates by product and market. "
        "MDG_2021_RTFP_v02_M. World Bank Microdata Library. doi:10.48529/2ZH0-JF55. "
        "Edition identified by each original filename; context version2026-10-05."
    ),
    "scope": "publisher open price estimates; no third-party raw prices or endorsement",
}


def build(originals: Path, annotations: Path, output: Path) -> dict[str, Any]:
    network = require_network_none()
    manual = json.loads(annotations.read_text())
    if (
        manual["method"] != "independent_transcription"
        or manual["human_reviewed"] is not False
        or len(manual["editions"]) != 2
        or any(len(item["values"]) != 30 for item in manual["editions"])
    ):
        raise ValueError("thirty_independent_cells_per_edition_required")
    output.mkdir(exist_ok=False)
    fixtures = output / "tests/fixtures"
    fixtures.mkdir(parents=True)
    entries = []
    stamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    receipts = []
    for folder in ("archives", "candidates"):
        report = json.loads((originals / f"wb-archive-{folder}-20261103/report.json").read_text())
        for receipt in report["receipts"]:
            if not any(
                item["url"] == receipt["url"] and item["status"] == 200 for item in report["trace"]
            ):
                raise ValueError("original_http200_evidence_missing")
            receipts.append(receipt)

    def acquired(digest: str, extension: str, member: str | None = None):
        matching = list(originals.rglob(digest + extension))
        records = [item for item in receipts if item["sha256"] == digest]
        if len(matching) != 1 or len(records) != 1:
            raise ValueError("original_identity_ambiguous")
        raw = matching[0].read_bytes()
        receipt = records[0]
        if len(raw) != receipt["bytes"] or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("original_bytes_mismatch")
        relative = f"tests/fixtures/{digest}{extension}"
        (output / relative).write_bytes(raw)
        acquisition = {
            "source_id": SOURCE,
            "source_url": receipt["url"],
            "catalogue_url": CATALOGUE,
            "mime_type": receipt["mime"],
            "access_method": "public_download",
            "discovered_at": receipt["fetched_at"].replace("+00:00", "Z"),
            "fetched_at": receipt["fetched_at"].replace("+00:00", "Z"),
            "published_at": None,
            "http_status": 200,
            "sha256": digest,
            "size_bytes": len(raw),
            "redirect_chain": [receipt["url"]],
            "allowed_hosts": ["microdata.worldbank.org"],
            "bronze_object_key": None,
            "rights": RIGHTS,
        }
        acquisition_path = f"tests/{digest}-acquisition.json"
        (output / acquisition_path).write_text(json.dumps(acquisition, indent=2))
        entry = {
            "path": relative,
            "sha256": digest,
            "size_bytes": len(raw),
            "artifact_type": "wb_zip_csv_v1" if member else "json",
            "authenticity": "authentic",
            "annotator": "agent",
            "human_reviewed": False,
            "origin": {"kind": "official_acquisition", "reference": acquisition_path},
            "rights": RIGHTS,
        }
        if member:
            entry["archive_member"] = member
        entries.append(entry)
        return entry, raw

    def annotated(source, source_cells, format_name):
        payload = {
            "metadata": {
                "document_path": source["path"],
                "document_sha256": source["sha256"],
                "annotator": "agent",
                "human_reviewed": False,
                "method": "independent_transcription",
                "annotated_at": stamp,
                "scope": manual["scope"],
                "format": format_name,
            },
            "cells": source_cells,
        }
        raw = (json.dumps(payload, indent=2) + "\n").encode()
        relative = f"tests/fixtures/{source['sha256']}-annotation.json"
        (output / relative).write_bytes(raw)
        entries.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
                "artifact_type": "golden",
                "authenticity": "authentic",
                "rights": RIGHTS,
                "origin": {"kind": "independent_annotation", "reference": source["path"]},
                "annotator": "agent",
                "human_reviewed": False,
            }
        )

    for edition in manual["editions"]:
        source, _ = acquired(edition["sha256"], ".zip", edition["member"])
        source_cells = []
        for offset, value in enumerate(edition["values"]):
            year, month = 2024 + offset // 12, offset % 12 + 1
            expected = {
                "c_rice": value,
                "price_date": f"{year:04}-{month:02}-01",
                "currency": "MGA",
                "ISO3": "MDG",
                "country": "Madagascar",
                "mkt_name": "Market Average",
                "adm1_name": "Market Average",
                "adm2_name": "Market Average",
                "geo_id": "gid_mdg_national_average",
                "lat": "",
                "lon": "",
            }
            for column, lexeme in expected.items():
                source_cells.append(
                    {
                        "path": [edition["member"], edition["first_row"] + offset, column],
                        "value_type": "number" if column == "c_rice" else "text",
                        "expected": lexeme,
                    }
                )
        annotated(source, source_cells, "wb_zip_csv_v1")
    source, raw = acquired(CONTEXT_SHA, ".json")
    context = json.loads(raw)
    indices = [
        i
        for i, item in enumerate(context["additional"]["ticker_info"])
        if item.get("iso3") == "MDG" and item.get("ticker") == "rice"
    ]
    if len(indices) != 1:
        raise ValueError("context_ticker_ambiguous")
    annotated(
        source,
        [
            {
                "path": ["additional", "ticker_info", indices[0], column],
                "value_type": "text",
                "expected": value,
            }
            for column, value in (
                ("iso3", "MDG"),
                ("ticker", "rice"),
                ("full_name", "Rice (local)"),
                ("units", "KG"),
            )
        ],
        "json",
    )
    manifest = {"version": 1, "entries": entries}
    (output / "tests/corpus-manifest.json").write_text(json.dumps(manifest, indent=2))
    result = validate_manifest(output, manifest)
    result.update(
        network=network,
        human_reviewed=False,
        silver_imported=False,
        rebuild_qualified=False,
        numeric_annotations=60,
    )
    (output / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("originals", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.originals, arguments.annotations, arguments.output), indent=2))
