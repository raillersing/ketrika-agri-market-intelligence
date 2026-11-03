"""ADR144: bounded public ODR candidates, never source/revision qualification."""

import hashlib
import io
import json
from datetime import UTC, datetime
from http.cookiejar import DefaultCookiePolicy
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import httpx
import pdfplumber
from selectolax.lexbor import LexborHTMLParser
from sqlalchemy import create_engine, text

from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import SqlBudgetBackend
from ketrika.core.policy import PolicyStop
from ketrika.core.registry import get_source
from ketrika.core.settings import get_settings

SOURCE = "miasa_odr"
HOSTS = {"www.minae.gov.mg", "minae.gov.mg"}
LANDING = "https://www.minae.gov.mg/bulletin-mensuel-odr-n-40-mois-de-2024-septembre-2024/"
KNOWN = (
    "https://www.minae.gov.mg/wp-content/uploads/2025/04/Bulletin_N%C2%B041_ODR_Octobre_2024.pdf",
    "https://www.minae.gov.mg/wp-content/uploads/2025/04/Bulletin_N%C2%B042_ODR_Novembre_2024.pdf",
)
MAX_PDF = 5 * 1024 * 1024
MAX_HTML = 1024 * 1024


class Anonymous(DefaultCookiePolicy):
    def set_ok(self, cookie, request):
        return False

    def return_ok(self, cookie, request):
        return False


class Bounded(httpx.SyncByteStream):
    def __init__(self, stream, maximum, trace):
        self.stream, self.maximum, self.trace = stream, maximum, trace

    def __iter__(self):
        total, digest = 0, hashlib.sha256()
        for chunk in self.stream:
            total += len(chunk)
            if total > self.maximum:
                raise ValueError("candidate_response_too_large")
            digest.update(chunk)
            yield chunk
        self.trace.update(bytes=total, sha256=digest.hexdigest())

    def close(self):
        self.stream.close()


class Official(httpx.HTTPTransport):
    def __init__(self):
        super().__init__()
        self.trace = []

    def handle_request(self, request):
        is_pdf = request.url.path.startswith(
            "/wp-content/uploads/"
        ) and request.url.path.lower().endswith(".pdf")
        if (
            request.url.scheme != "https"
            or request.url.host not in HOSTS
            or request.method != "GET"
            or request.url.query
            or not (
                request.url.path == "/robots.txt"
                or request.url.path == urlsplit(LANDING).path
                or is_pdf
            )
            or any(key in request.headers for key in ("authorization", "cookie"))
        ):
            raise ValueError("candidate_request_outside_public_scope")
        request.headers["accept-encoding"] = "identity"
        response = super().handle_request(request)
        entry = {
            "url": str(request.url),
            "status": response.status_code,
            "mime": response.headers.get("content-type"),
            "location": response.headers.get("location"),
            "fetched_at": datetime.now(UTC).isoformat(),
        }
        self.trace.append(entry)
        if response.status_code in (401, 403):
            response.close()
            raise PolicyStop("http_access_refused")
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            response.close()
            raise ValueError("candidate_encoded_response_refused")
        response.stream = Bounded(response.stream, MAX_PDF if is_pdf else MAX_HTML, entry)
        return response


engine = create_engine(get_settings().database_url)
assert engine.url.database == "ketrika_corpus_discovery_20261028"
source = get_source(SOURCE)
assert source.status == "active" and source.legal_review_status == "approved"
output = Path("/tmp/odr-revision-candidates-20261029")
output.mkdir(exist_ok=False)
transport = Official()
report = {
    "started_at": datetime.now(UTC).isoformat(),
    "status": "unknown",
    "source_id": SOURCE,
    "rights_verified": False,
    "authenticity_qualified": False,
    "revision_qualified": False,
    "silver_imported": False,
    "documents": [],
}
try:
    with PoliteHttpClient(
        budget_backend=SqlBudgetBackend(engine), transport=transport, timeout=30, connect_timeout=10
    ) as client:
        client.bind_source(SOURCE, 10, min(source.max_rps, 0.2))
        client._client.cookies.jar.set_policy(Anonymous())
        page = client.get(LANDING, max_rps=0.2)
        if page.status_code != 200 or "html" not in page.headers.get("content-type", "").lower():
            raise ValueError("candidate_landing_not_accepted")
        tree = LexborHTMLParser(page.text)
        links = set()
        for anchor in tree.css("a[href]"):
            url = urljoin(page.url, anchor.attributes["href"])
            parsed = urlsplit(url)
            label = unquote(parsed.path).lower()
            if (
                parsed.scheme == "https"
                and parsed.hostname in HOSTS
                and not parsed.query
                and parsed.path.startswith("/wp-content/uploads/")
                and label.endswith(".pdf")
                and "septembre" in label
                and "2024" in label
                and "odr" in label
            ):
                links.add(url)
        report["september_candidates"] = [{"url": url, "verified": False} for url in sorted(links)]
        if len(links) != 1:
            raise ValueError("candidate_september_link_missing_or_ambiguous")
        for url in (*sorted(links), *KNOWN):
            response = client.get(url, max_rps=0.2)
            if response.status_code != 200 or not response.content.startswith(b"%PDF-"):
                raise ValueError("candidate_not_a_successful_pdf")
            if "pdf" not in response.headers.get("content-type", "").lower():
                raise ValueError("candidate_pdf_mime_unverified")
            with pdfplumber.open(io.BytesIO(response.content)) as document:
                if not 0 < len(document.pages) <= 80:
                    raise ValueError("candidate_page_count_outside_bounds")
                text_pages = [p.extract_text() or "" for p in document.pages]
                if any(
                    marker in "\n".join(text_pages).lower()
                    for marker in ("numéro de cin", "telephone personnel", "téléphone personnel")
                ):
                    raise ValueError("candidate_private_fields_need_review")
                descriptor = {
                    "url": response.url,
                    "bytes": len(response.content),
                    "sha256": hashlib.sha256(response.content).hexdigest(),
                    "mime": response.headers.get("content-type"),
                    "pages": len(document.pages),
                    "text_characters": [len(value) for value in text_pages],
                    "fetched_at": datetime.now(UTC).isoformat(),
                    "verified_http": True,
                    "rights_verified": False,
                    "authenticity_qualified": False,
                }
            path = output / (descriptor["sha256"] + ".pdf")
            try:
                with path.open("xb") as stream:
                    stream.write(response.content)
            except FileExistsError:
                if path.read_bytes() != response.content:
                    raise ValueError("candidate_immutable_copy_collision") from None
            report["documents"].append(descriptor)
        report["status"] = "candidates_downloaded_unqualified"
except PolicyStop as exc:
    report.update(status="policy_stopped", reason=exc.reason)
    if transport.trace and transport.trace[-1]["status"] in (401, 403):
        last = transport.trace[-1]
        parsed = urlsplit(last["url"])
        SqlBudgetBackend(engine).stop(SOURCE, parsed.scheme + "://" + parsed.netloc, last["status"])
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE meta.source SET status='disabled' WHERE source_id=:id"), {"id": SOURCE}
        )
except (httpx.NetworkError, httpx.TimeoutException):
    report["status"] = "network_unavailable"
except ValueError as exc:
    report.update(status="candidate_refused", reason=str(exc))
finally:
    report["trace"] = transport.trace
    report["finished_at"] = datetime.now(UTC).isoformat()
    with (output / "report.json").open("x") as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
    engine.dispose()
    print(json.dumps(report))
