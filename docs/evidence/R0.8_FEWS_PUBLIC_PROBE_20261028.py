"""ADR142: anonymous bounded discovery only; no source payload is persisted."""

import csv
import hashlib
import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import SqlBudgetBackend
from ketrika.core.policy import PolicyStop
from ketrika.core.settings import get_settings

MAX_BYTES = 256 * 1024
ORIGIN = "https://fdw.fews.net"


class Bounded(httpx.SyncByteStream):
    def __init__(self, stream):
        self.stream = stream

    def __iter__(self):
        total = 0
        for chunk in self.stream:
            total += len(chunk)
            if total > MAX_BYTES:
                raise PolicyStop("corpus_response_too_large")
            yield chunk

    def close(self):
        self.stream.close()


class PublicOnly(httpx.HTTPTransport):
    def __init__(self):
        super().__init__()
        self.requests = []

    def handle_request(self, request):
        if request.url.scheme != "https" or request.url.host != "fdw.fews.net":
            raise PolicyStop("corpus_external_origin_refused")
        if (
            request.method != "GET"
            or request.url.path not in ("/robots.txt", "/api/marketpricefacts.csv")
            or any(key in request.headers for key in ("authorization", "cookie"))
        ):
            raise PolicyStop("corpus_nonpublic_request_refused")
        request.headers["accept-encoding"] = "identity"
        response = super().handle_request(request)
        self.requests.append({"path": request.url.path, "status": response.status_code})
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            response.close()
            raise PolicyStop("corpus_encoded_response_refused")
        response.stream = Bounded(response.stream)
        return response


engine = create_engine(get_settings().database_url)
assert engine.url.database == "ketrika_corpus_discovery_20261028"
with engine.connect() as connection:
    assert connection.scalar(text("SELECT current_database()")) == engine.url.database
transport = PublicOnly()
report = {
    "started_at": datetime.now(UTC).isoformat(),
    "source": "fewsnet_price_history_probe",
    "authenticity_qualified": False,
    "redistribution_rights_verified": False,
    "source_payload_persisted": False,
    "editions": [],
    "status": "unknown",
}
try:
    with PoliteHttpClient(
        budget_backend=SqlBudgetBackend(engine), transport=transport, timeout=30, connect_timeout=10
    ) as client:
        client.bind_source("fewsnet_price_history_probe", 10, 0.2)
        for as_of in ("2024-03-01", "2026-10-01"):
            response = client.get(
                ORIGIN + "/api/marketpricefacts.csv",
                max_rps=0.2,
                params={
                    "country": "Madagascar",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                    "as_of_date": as_of,
                },
            )
            if response.status_code != 200:
                raise PolicyStop("corpus_response_not_accepted")
            if "csv" not in response.headers.get("content-type", "").lower():
                raise PolicyStop("corpus_not_csv")
            rows = csv.DictReader(io.StringIO(response.content.decode("utf-8-sig")))
            if (
                not rows.fieldnames
                or len(rows.fieldnames) > 128
                or any(
                    not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name)
                    for name in rows.fieldnames
                )
            ):
                raise PolicyStop("corpus_unknown_csv_columns")
            count = sum(1 for _ in rows)
            report["editions"].append(
                {
                    "requested_as_of": as_of,
                    "status": 200,
                    "bytes": len(response.content),
                    "rows": count,
                    "columns": rows.fieldnames,
                    "sha256": hashlib.sha256(response.content).hexdigest(),
                    "historical_state_verified": False,
                }
            )
        report["status"] = "public_metadata_only"
except PolicyStop as exc:
    report["status"] = "policy_stopped"
    report["reason"] = exc.reason
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE meta.source SET status='disabled' WHERE source_id='fewsnet_price_history_probe'"
            )
        )
except (httpx.NetworkError, httpx.TimeoutException):
    report["status"] = "network_unavailable"
finally:
    report["requests"] = transport.requests
    report["finished_at"] = datetime.now(UTC).isoformat()
    with Path("/tmp/fews-public-probe-20261028.json").open("x") as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
    engine.dispose()
    print(json.dumps(report))
