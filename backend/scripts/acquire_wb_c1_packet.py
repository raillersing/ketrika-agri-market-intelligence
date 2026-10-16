"""Fresh bounded C1 packet with observed MIME, redirects and robots trace.

All data remain local/unpromoted until corpus and independent annotation checks.
No private data, submission, S3 write, Silver load or instruction from content.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import SqlBudgetBackend
from ketrika.core.policy import PolicyStop
from ketrika.core.registry import get_source
from ketrika.core.settings import get_settings
from ketrika.pipelines.rebuild_qualification import require_destination

HOSTS = {"microdata.worldbank.org", "datacatalog.worldbank.org"}
CATALOGUE = "https://microdata.worldbank.org/catalog/8240/study-description"
PARAMS = {
    "limit": 15,
    "c[ISO3]": "MDG",
    "c[rice]": ">0",
    "fields": "ISO3,country,adm1_name,adm2_name,mkt_name,price_date,currency,rice,sugar,wheat_flour,data_coverage,spatially_interpolated",
}


class TraceTransport(httpx.HTTPTransport):
    def __init__(self):
        super().__init__()
        self.trace = []

    def handle_request(self, request):
        if request.url.scheme != "https" or request.url.host not in HOSTS:
            raise PolicyStop("corpus_external_origin_refused")
        response = super().handle_request(request)
        self.trace.append(
            {
                "url": str(request.url),
                "status": response.status_code,
                "mime": response.headers.get("content-type"),
                "location": response.headers.get("location"),
                "fetched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
        )
        return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modeled-rice", action="store_true")
    options = parser.parse_args()
    parameters = dict(PARAMS)
    if options.modeled_rice:
        parameters.pop("c[rice]")
        parameters["c[c_rice]"] = ">0"
        parameters["fields"] = (
            "ISO3,country,adm1_name,adm2_name,mkt_name,price_date,currency,c_rice,data_coverage,spatially_interpolated"
        )
    output = Path("/out/wb-c1-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    output.mkdir(exist_ok=False)
    engine = create_engine(get_settings().database_url)
    with Session(engine) as session:
        require_destination(session)
    source = get_source("wb_rtfp_mdg")
    if source.status != "active" or source.legal_review_status != "approved":
        raise PolicyStop("corpus_source_not_approved")
    transport = TraceTransport()
    client = PoliteHttpClient(budget_backend=SqlBudgetBackend(engine), transport=transport)
    client.bind_source(source.source_id, source.daily_request_budget, source.max_rps)
    receipts, status = [], "failed"
    try:
        targets = (
            ("study.json", "https://microdata.worldbank.org/metadata/export/8240/json", None),
            (
                "sample.json",
                "https://microdata.worldbank.org/api/tables/data/fcv/wld_2021_rtfp_v02_m",
                parameters,
            ),
            ("public-licenses.html", "https://datacatalog.worldbank.org/public-licenses", None),
        )
        for filename, url, params in targets:
            first = len(transport.trace)
            result = client.get(url, params=params, max_rps=source.max_rps)
            if result.status_code != 200 or len(result.content) > 5 * 1024 * 1024:
                raise PolicyStop("corpus_document_not_accepted")
            trace = transport.trace[first:]
            # Follow only the actually observed document chain, not intervening robots probes.
            request_url = str(httpx.URL(url, params=params)) if params else url
            expected, chain = request_url, []
            for event in trace:
                if event["url"] != expected:
                    continue
                chain.append(expected)
                if event["status"] in (301, 302, 303, 307, 308) and event["location"]:
                    expected = urljoin(expected, event["location"])
            if not chain or chain[-1] != result.url:
                raise PolicyStop("corpus_document_chain_missing")
            if filename == "sample.json":
                rows = json.loads(result.content).get("data")
                if (
                    not isinstance(rows, list)
                    or len(rows) != 15
                    or any(row.get("ISO3") != "MDG" for row in rows)
                ):
                    raise PolicyStop("corpus_sample_country_or_count_mismatch")
            (output / filename).write_bytes(result.content)
            receipts.append(
                {
                    "filename": filename,
                    "source_url": request_url,
                    "catalogue_url": CATALOGUE,
                    "http_status": 200,
                    "fetched_at": trace[-1]["fetched_at"],
                    "redirect_chain": chain,
                    "sha256": hashlib.sha256(result.content).hexdigest(),
                    "size_bytes": len(result.content),
                    "mime_type": result.headers.get("content-type", "").split(";")[0].strip(),
                    "headers_mime": result.headers.get("content-type"),
                }
            )
        status = "downloaded_pending_corpus_validation"
    except PolicyStop:
        status = "policy_stopped"
    finally:
        document = {
            "source_id": source.source_id,
            "status": status,
            "receipts": receipts,
            "trace": transport.trace,
            "user_agent": client.user_agent,
            "rights_status": "unverified",
            "authenticity_qualified": False,
        }
        (output / "acquisition.json").write_text(json.dumps(document, indent=2) + "\n")
        print(
            json.dumps({"output": str(output), "status": status, "requests": len(transport.trace)})
        )
        engine.dispose()


if __name__ == "__main__":
    main()
