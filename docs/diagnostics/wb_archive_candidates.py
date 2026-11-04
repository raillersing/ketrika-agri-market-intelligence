"""ADR161: discover only official WB metadata under existing durable budgets."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from http.cookiejar import DefaultCookiePolicy
from pathlib import Path
from typing import Any

import httpx
from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import SqlBudgetBackend
from ketrika.core.policy import PolicyStop
from ketrika.core.registry import get_source
from ketrika.core.settings import get_settings
from sqlalchemy import create_engine, text

from odr_live_policy import source_must_stop
from transport_witness import TransportWitness
from wb_archive_policy import DOWNLOADS, Bounded, permitted_request

SOURCE = "wb_rtfp_mdg"
ORIGIN = "https://microdata.worldbank.org"
MAX_BYTES = 1024 * 1024
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024


class Anonymous(DefaultCookiePolicy):
    def set_ok(self, cookie, request):
        return False

    def return_ok(self, cookie, request):
        return False


class Official(httpx.HTTPTransport):
    def __init__(self):
        super().__init__()
        self.trace = []

    def handle_request(self, request):
        if not permitted_request(request.method, str(request.url), request.headers):
            raise PolicyStop("archive_metadata_request_not_permitted")
        request.headers["accept-encoding"] = "identity"
        response = super().handle_request(request)
        self.trace.append(
            {
                "url": str(request.url),
                "status": response.status_code,
                "location": response.headers.get("location"),
            }
        )
        if response.status_code in (401, 403):
            response.close()
            raise PolicyStop("http_access_refused")
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            response.close()
            raise ValueError("archive_encoded_response_refused")
        response.stream = Bounded(
            response.stream,
            MAX_ARCHIVE_BYTES if request.url.path in DOWNLOADS else MAX_BYTES,
        )
        return response


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--stage", choices=("metadata", "listing", "archives"), default="metadata"
)
stage = parser.parse_args().stage
engine = create_engine(get_settings().database_url)
if engine.url.database != "ketrika":
    raise ValueError("existing_central_acquisition_database_required")
budget = SqlBudgetBackend(engine)
budget.check(SOURCE, ORIGIN)
source = get_source(SOURCE)
if source.status != "active" or source.legal_review_status != "approved":
    raise ValueError("approved_active_source_required")
output = Path(
    "/tmp/wb-archive-" + ("candidates" if stage == "metadata" else stage) + "-20261103"
)
output.mkdir(exist_ok=False)
official = Official()
transport = TransportWitness(official)
report: dict[str, Any] = {
    "started_at": datetime.now(UTC).isoformat(),
    "source_id": SOURCE,
    "status": "unknown",
    "rights_verified": False,
    "revision_qualified": False,
    "silver_imported": False,
    "receipts": [],
}
try:
    with PoliteHttpClient(
        budget_backend=budget, transport=transport, timeout=30, connect_timeout=10
    ) as client:
        client.bind_source(SOURCE, 10, min(source.max_rps, 0.2))
        client._client.cookies.jar.set_policy(Anonymous())
        requests = {
            "metadata": (
                ("/catalog/8240/data-api", "html"),
                ("/metadata/export/8240/json", "json"),
            ),
            "listing": (
                ("/api/downloads/MDG_2021_RTFP_v02_M/files?type=data", "json"),
            ),
            "archives": (
                ("/api/downloads/info/MDG_2021_RTFP_v02_M/360505", "json"),
                ("/api/downloads/info/MDG_2021_RTFP_v02_M/360780", "json"),
                (
                    "/api/downloads/download/MDG_2021_RTFP_v02_M/360505?filename=MDG_RTFP_mkt_2007_2026-09-28.zip",
                    "zip",
                ),
                (
                    "/api/downloads/download/MDG_2021_RTFP_v02_M/360780?filename=MDG_RTFP_mkt_2007_2026-10-05.zip",
                    "zip",
                ),
            ),
        }[stage]
        for path, kind in requests:
            response = client.get(ORIGIN + path, max_rps=0.2)
            mime = (
                response.headers.get("content-type", "").split(";")[0].strip().lower()
            )
            accepted = (
                (
                    mime
                    in {
                        "application/zip",
                        "application/x-zip-compressed",
                        "application/octet-stream",
                    }
                    and response.content.startswith(b"PK\x03\x04")
                )
                if kind == "zip"
                else kind in mime
            )
            if response.status_code != 200 or not accepted:
                raise ValueError("archive_metadata_not_accepted")
            digest = hashlib.sha256(response.content).hexdigest()
            with (output / (digest + "." + kind)).open("xb") as stream:
                stream.write(response.content)
            report["receipts"].append(
                {
                    "url": response.url,
                    "bytes": len(response.content),
                    "sha256": digest,
                    "mime": response.headers.get("content-type"),
                    "fetched_at": datetime.now(UTC).isoformat(),
                }
            )
        report["status"] = (
            "archive_candidates_downloaded_unqualified"
            if stage == "archives"
            else "metadata_downloaded_unqualified"
        )
except PolicyStop as exc:
    report.update(status="policy_stopped", reason=exc.reason)
    if official.trace and official.trace[-1]["status"] in (401, 403):
        budget.stop(SOURCE, ORIGIN, official.trace[-1]["status"])
    if source_must_stop(exc.reason):
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE meta.source SET status='disabled' WHERE source_id=:id"),
                {"id": SOURCE},
            )
except (httpx.NetworkError, httpx.TimeoutException) as exc:
    report.update(status="network_unavailable", error_class=type(exc).__name__)
except ValueError as exc:
    report.update(status="candidate_refused", reason=str(exc))
finally:
    report["trace"] = official.trace
    report["transport_attempts"] = transport.attempts
    report["finished_at"] = datetime.now(UTC).isoformat()
    with (output / "report.json").open("x") as report_stream:
        json.dump(report, report_stream, sort_keys=True, indent=2)
    engine.dispose()
    print(json.dumps(report))
