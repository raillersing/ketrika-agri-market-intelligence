"""Bounded official-document acquisition; separate from the frozen QA source.

No Silver/Gold, no active DB/S3, no private site, no rights/authenticity claim.
All HTTP goes through the received durable robots/budget/challenge client.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
from selectolax.lexbor import LexborHTMLParser
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import SqlBudgetBackend
from ketrika.core.policy import PolicyStop
from ketrika.core.registry import get_source
from ketrika.core.settings import get_settings
from ketrika.pipelines.rebuild_qualification import require_destination

PAGES = (
    "https://instat.mg/p/nipc-nouvel-indice-des-prix-a-la-consommation-septembre-2025",
    "https://instat.mg/p/nipc-nouvel-indice-des-prix-a-la-consommation-mars-2026",
)
HOSTS = {"instat.mg", "www.instat.mg"}
LIMIT = 5 * 1024 * 1024


class OfficialTransport(httpx.HTTPTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.scheme != "https" or request.url.host not in HOSTS:
            raise PolicyStop("corpus_external_origin_refused")
        return super().handle_request(request)


def main() -> None:
    output = Path("/out/instat-corpus-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    output.mkdir(exist_ok=False)
    engine = create_engine(get_settings().database_url)
    with Session(engine) as session:
        require_destination(session)  # Existing dedicated lab only, never an active target.
    source = get_source("instat_nipc")
    if source.status != "active" or source.legal_review_status != "approved":
        raise PolicyStop("corpus_source_not_approved")
    client = PoliteHttpClient(
        budget_backend=SqlBudgetBackend(engine), transport=OfficialTransport()
    )
    client.bind_source(source.source_id, source.daily_request_budget, source.max_rps)
    receipts = []

    def fetch(url: str):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username:
            raise PolicyStop("corpus_external_origin_refused")
        response = client.get(url, max_rps=source.max_rps)
        receipt = {
            "url": url,
            "final_url": response.url,
            "http_status": response.status_code,
            "fetched_at": datetime.now(UTC).isoformat(),
            "sha256": hashlib.sha256(response.content).hexdigest(),
            "size_bytes": len(response.content),
            "mime_type": response.headers.get("content-type"),
        }
        receipts.append(receipt)
        if len(response.content) > LIMIT:
            raise PolicyStop("corpus_response_too_large")
        if response.status_code != 200:
            raise PolicyStop("corpus_document_not_successful")
        return response

    status = "failed"
    try:
        # Rights remain unverified even if a legal page is HTTP 200.
        fetch(source.tos_url)
        for page in PAGES:
            landing = fetch(page)
            targets = {
                urljoin(landing.url, anchor.attributes["href"])
                for anchor in LexborHTMLParser(landing.text).css("a[href]")
                if anchor.attributes["href"].lower().endswith(".xlsx")
                and "nipc" in anchor.attributes["href"].lower()
            }
            if len(targets) != 1:
                raise PolicyStop("corpus_download_link_ambiguous")
            response = fetch(next(iter(targets)))
            if not response.content.startswith(b"PK\x03\x04"):
                raise PolicyStop("corpus_document_not_xlsx")
            digest = hashlib.sha256(response.content).hexdigest()
            (output / (digest + ".xlsx")).write_bytes(response.content)
        status = "downloaded_unverified"
    except PolicyStop as error:
        status = "policy_stopped"
        receipts.append({"error_type": type(error).__name__})
    finally:
        document = {
            "source_id": source.source_id,
            "status": status,
            "receipts": receipts,
            "rights_status": "unverified",
            "authenticity_qualified": False,
            "limitations": "No corpus promotion, parser/revision proof or source qualification",
        }
        (output / "acquisition.json").write_text(json.dumps(document, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "output": str(output),
                    "status": status,
                    "document_responses": sum("http_status" in item for item in receipts),
                }
            )
        )
        engine.dispose()


if __name__ == "__main__":
    main()
