"""Acquire a bounded public Madagascar API sample, no form submission or promotion.

Endpoints published by World Bank's public NADA data-API documentation. Query
results must identify MDG before any data bytes are retained. Rights stay unverified.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from probe_wb_rebuild_corpus import OfficialTransport
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import SqlBudgetBackend
from ketrika.core.policy import PolicyStop
from ketrika.core.registry import get_source
from ketrika.core.settings import get_settings
from ketrika.pipelines.rebuild_qualification import require_destination

BASE = "https://microdata.worldbank.org/api/tables/"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-metadata", action="store_true")
    parser.add_argument("--valued-rice", action="store_true")
    options = parser.parse_args()
    output = Path("/out/wb-api-sample-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    output.mkdir(exist_ok=False)
    engine = create_engine(get_settings().database_url)
    with Session(engine) as session:
        require_destination(session)
    source = get_source("wb_rtfp_mdg")
    if source.status != "active" or source.legal_review_status != "approved":
        raise PolicyStop("corpus_source_not_approved")
    client = PoliteHttpClient(
        budget_backend=SqlBudgetBackend(engine), transport=OfficialTransport()
    )
    client.bind_source(source.source_id, source.daily_request_budget, source.max_rps)
    receipts, status = [], "failed"

    def fetch(path, params):
        result = client.get(BASE + path, params=params, max_rps=source.max_rps)
        receipts.append(
            {
                "url": result.url,
                "http_status": result.status_code,
                "sha256": hashlib.sha256(result.content).hexdigest(),
                "size_bytes": len(result.content),
                "fetched_at": datetime.now(UTC).isoformat(),
            }
        )
        if result.status_code != 200 or len(result.content) > 5 * 1024 * 1024:
            raise PolicyStop("corpus_api_response_not_accepted")
        return result

    try:
        if not options.skip_metadata:
            metadata = fetch("info/fcv/wld_2021_rtfp_v02_m", {"data_dictionary": "true"})
            json.loads(metadata.content)  # Must be JSON, not a successful HTML shell.
            (output / "metadata.json").write_bytes(metadata.content)
        parameters = {
            "limit": 15,
            "c[ISO3]": "MDG",
            "fields": "ISO3,country,adm1_name,adm2_name,mkt_name,price_date,currency,rice,sugar,wheat_flour,data_coverage,spatially_interpolated",
        }
        if options.valued_rice:
            parameters["c[rice]"] = ">0"
        result = fetch("data/fcv/wld_2021_rtfp_v02_m", parameters)
        payload = json.loads(result.content)
        result_object = payload.get("result", payload) if isinstance(payload, dict) else None
        records = result_object.get("data") if isinstance(result_object, dict) else None
        receipts[-1]["response_keys"] = sorted(payload) if isinstance(payload, dict) else []
        receipts[-1]["result_keys"] = (
            sorted(result_object) if isinstance(result_object, dict) else []
        )
        if not isinstance(records, list) or not 0 < len(records) <= 15:
            raise PolicyStop("corpus_sample_empty_or_unbounded")
        if any(not isinstance(row, dict) or row.get("ISO3") != "MDG" for row in records):
            raise PolicyStop("corpus_sample_country_mismatch")
        if options.valued_rice:
            try:
                valid = all(
                    Decimal(str(row["rice"])).is_finite() and Decimal(str(row["rice"])) > 0
                    for row in records
                )
            except (KeyError, InvalidOperation):
                valid = False
            if not valid:
                raise PolicyStop("corpus_sample_value_filter_not_respected")
        (output / "sample.json").write_bytes(result.content)
        status = "sample_downloaded_unverified"
    except PolicyStop as error:
        status = "policy_stopped_or_sample_refused"
        receipts.append(
            {
                "error_type": type(error).__name__,
                "code": str(error) if str(error).startswith("corpus_") else "policy_stop",
            }
        )
    finally:
        document = {
            "source_id": source.source_id,
            "status": status,
            "receipts": receipts,
            "rights_status": "unverified",
            "authenticity_qualified": False,
            "limitations": "No C1 promotion, parser/revisions/model proof or form acceptance",
        }
        (output / "acquisition.json").write_text(json.dumps(document, indent=2) + "\n")
        print(json.dumps({"output": str(output), "status": status}))
        engine.dispose()


if __name__ == "__main__":
    main()
