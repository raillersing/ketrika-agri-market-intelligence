"""Acquire official licensing/context for the retained sample, never infer permission."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import SqlBudgetBackend
from ketrika.core.policy import PolicyStop
from ketrika.core.registry import get_source
from ketrika.core.settings import get_settings
from ketrika.pipelines.rebuild_qualification import require_destination

TARGETS = {
    "study.json": "https://microdata.worldbank.org/metadata/export/8240/json",
    "public-licenses.html": "https://datacatalog.worldbank.org/public-licenses",
}
HOSTS = {
    "microdata.worldbank.org",
    "datacatalog.worldbank.org",
    "www.worldbank.org",
    "data.worldbank.org",
}


class OfficialTransport(httpx.HTTPTransport):
    def handle_request(self, request):
        if request.url.scheme != "https" or request.url.host not in HOSTS:
            raise PolicyStop("corpus_external_origin_refused")
        return super().handle_request(request)


def main():
    output = Path("/out/wb-rights-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
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
    try:
        for filename, url in TARGETS.items():
            response = client.get(url, max_rps=source.max_rps)
            receipts.append(
                {
                    "url": url,
                    "final_url": response.url,
                    "http_status": response.status_code,
                    "fetched_at": datetime.now(UTC).isoformat(),
                    "sha256": hashlib.sha256(response.content).hexdigest(),
                    "size_bytes": len(response.content),
                }
            )
            if response.status_code != 200 or len(response.content) > 5 * 1024 * 1024:
                raise PolicyStop("corpus_context_not_successful")
            (output / filename).write_bytes(response.content)
        status = "context_downloaded_pending_review"
    except PolicyStop:
        status = "policy_stopped"
    finally:
        (output / "acquisition.json").write_text(
            json.dumps(
                {
                    "status": status,
                    "receipts": receipts,
                    "rights_status": "unverified",
                    "authenticity_qualified": False,
                },
                indent=2,
            )
            + "\n"
        )
        print(json.dumps({"output": str(output), "status": status}))
        engine.dispose()


if __name__ == "__main__":
    main()
