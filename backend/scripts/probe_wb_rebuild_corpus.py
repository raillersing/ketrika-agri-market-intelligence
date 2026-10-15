"""Discover public RTFP links with the received HTTP policy; never submit a form."""

import argparse
import hashlib
import json
import re
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

PAGES = {
    "download": "https://microdata.worldbank.org/catalog/8240/get-microdata",
    "api": "https://microdata.worldbank.org/catalog/8240/data-api",
    "dictionary": "https://microdata.worldbank.org/catalog/8240/data-dictionary",
}


class OfficialTransport(httpx.HTTPTransport):
    def handle_request(self, request):
        if request.url.scheme != "https" or request.url.host != "microdata.worldbank.org":
            raise PolicyStop("corpus_external_origin_refused")
        return super().handle_request(request)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", choices=tuple(PAGES), default="download")
    page = PAGES[parser.parse_args().page]
    output = Path("/out/wb-probe-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
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
    document = {"source_id": source.source_id, "status": "unknown", "authenticity_qualified": False}
    try:
        response = client.get(page, max_rps=source.max_rps)
        document.update(
            http_status=response.status_code,
            url=response.url,
            sha256=hashlib.sha256(response.content).hexdigest(),
            size_bytes=len(response.content),
        )
        if response.status_code != 200 or len(response.content) > 5 * 1024 * 1024:
            raise PolicyStop("corpus_catalogue_not_accepted")
        tree = LexborHTMLParser(response.text)
        candidates = set()
        for node in tree.css("script:not([src])"):
            for literal in re.findall(r"[\"']([^\"'\\\n]{1,300})[\"']", node.text()):
                if "/api/" in literal and not any(
                    word in literal.lower()
                    for word in ("token", "secret", "api_key", "apikey", "signature")
                ):
                    candidates.add(literal)
        document["declared_api_candidates"] = [
            {"reference": value, "verified": False} for value in sorted(candidates)
        ]
        document["scripts"] = sorted(
            {
                urljoin(response.url, node.attributes["src"])
                for node in tree.css("script[src]")
                if urlsplit(urljoin(response.url, node.attributes["src"])).hostname
                == "microdata.worldbank.org"
            }
        )
        # Only public same-origin path references, never cookies/tokens or raw personal content.
        document["links"] = sorted(
            {
                urljoin(response.url, anchor.attributes["href"])
                for anchor in tree.css("a[href]")
                if urlsplit(urljoin(response.url, anchor.attributes["href"])).hostname
                == "microdata.worldbank.org"
                and not urlsplit(anchor.attributes["href"]).query
            }
        )
        document["forms"] = [
            {
                "method": form.attributes.get("method"),
                "input_types": [node.attributes.get("type") for node in form.css("input")],
            }
            for form in tree.css("form")
        ]
        document["status"] = "catalogue_only_no_download"
    except PolicyStop:
        document["status"] = "policy_stopped"
    finally:
        (output / "probe.json").write_text(json.dumps(document, indent=2) + "\n")
        print(json.dumps({"output": str(output), "status": document["status"]}))
        engine.dispose()


if __name__ == "__main__":
    main()
