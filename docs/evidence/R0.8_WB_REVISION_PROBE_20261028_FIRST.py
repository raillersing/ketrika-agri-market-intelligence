"""ADR142: bounded comparison with original bytes, never a Silver load."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

from ketrika.connectors.manual_wb import STUDY_URL, recent_rice_history_url
from ketrika.core.http import PoliteHttpClient
from ketrika.core.http_budget import SqlBudgetBackend
from ketrika.core.policy import PolicyStop
from ketrika.core.registry import get_source
from ketrika.core.settings import get_settings

MAX_BYTES = 256 * 1024
SOURCE = "wb_rtfp_mdg"
ORIGIN = "https://microdata.worldbank.org"
OLD_SHA = "9d17c04cb0ddb0886afb677685aecfc4e746deb14b0284155466b26ceef695e3"
COLUMNS = {
    "ISO3",
    "country",
    "adm1_name",
    "adm2_name",
    "mkt_name",
    "price_date",
    "currency",
    "c_rice",
    "data_coverage",
    "spatially_interpolated",
}
GRAIN = ("ISO3", "country", "adm1_name", "adm2_name", "mkt_name", "price_date", "currency")


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


class Official(httpx.HTTPTransport):
    def __init__(self):
        super().__init__()
        self.requests = []

    def handle_request(self, request):
        if request.url.scheme != "https" or request.url.host != "microdata.worldbank.org":
            raise PolicyStop("corpus_external_origin_refused")
        if (
            request.method != "GET"
            or request.url.path
            not in (
                "/robots.txt",
                "/metadata/export/8240/json",
                "/api/tables/data/fcv/wld_2021_rtfp_v02_m",
            )
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


def rows(content):
    document = json.loads(content, parse_float=Decimal)
    data = document.get("data")
    if not isinstance(data, list) or not 0 < len(data) <= 120:
        raise PolicyStop("corpus_rows_outside_bounds")
    result = {}
    for row in data:
        if not isinstance(row, dict) or set(row) != COLUMNS or row["ISO3"] != "MDG":
            raise PolicyStop("corpus_country_or_columns_invalid")
        key = tuple(row[name] for name in GRAIN)
        value = Decimal(str(row["c_rice"]))
        if key in result or not value.is_finite() or value <= 0:
            raise PolicyStop("corpus_duplicate_or_invalid_value")
        result[key] = value
    return result


engine = create_engine(get_settings().database_url)
assert engine.url.database == "ketrika_corpus_discovery_20261028"
source = get_source(SOURCE)
assert source.status == "active" and source.legal_review_status == "approved"
original = Path("/tmp/wb-original-20261024.json").read_bytes()
assert hashlib.sha256(original).hexdigest() == OLD_SHA
old = rows(original)
output = Path("/tmp/wb-revision-probe-20261028")
output.mkdir(exist_ok=False)
transport = Official()
report = {
    "started_at": datetime.now(UTC).isoformat(),
    "original_sha256": OLD_SHA,
    "original_fetched_at": "2026-10-24T13:13:10.103455+00:00",
    "authentic_revision_qualified": False,
    "silver_imported": False,
    "source_values": "publisher modeled close estimates, never observed prices",
    "receipts": [],
    "status": "unknown",
}
try:
    with PoliteHttpClient(
        budget_backend=SqlBudgetBackend(engine), transport=transport, timeout=30, connect_timeout=10
    ) as client:
        client.bind_source(SOURCE, 10, min(source.max_rps, 0.2))
        for kind, url in (
            ("context", STUDY_URL),
            ("data", recent_rice_history_url(datetime.now(UTC).date())),
        ):
            response = client.get(url, max_rps=0.2)
            if response.status_code != 200:
                raise PolicyStop("corpus_response_not_accepted")
            document = json.loads(response.content)
            if kind == "context":
                if not isinstance(document, dict) or "study_desc" not in document:
                    raise PolicyStop("corpus_context_invalid")
            else:
                current = rows(response.content)
            digest = hashlib.sha256(response.content).hexdigest()
            if kind == "data":
                with (output / (digest + ".json")).open("xb") as stream:
                    stream.write(response.content)
            report["receipts"].append(
                {
                    "kind": kind,
                    "url": response.url,
                    "sha256": digest,
                    "bytes": len(response.content),
                    "payload_persisted": kind == "data",
                    "fetched_at": datetime.now(UTC).isoformat(),
                }
            )
        common = old.keys() & current.keys()
        report.update(
            status="compared_not_qualified",
            old_rows=len(old),
            new_rows=len(current),
            common_identities=len(common),
            changed_values=sum(old[k] != current[k] for k in common),
            old_only=len(old.keys() - current.keys()),
            new_only=len(current.keys() - old.keys()),
        )
except PolicyStop as exc:
    report.update(status="policy_stopped", reason=exc.reason)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE meta.source SET status='disabled' WHERE source_id=:id"), {"id": SOURCE}
        )
except (httpx.NetworkError, httpx.TimeoutException):
    report["status"] = "network_unavailable"
finally:
    report["requests"] = transport.requests
    report["finished_at"] = datetime.now(UTC).isoformat()
    report["original_bytes_unchanged"] = (
        hashlib.sha256(Path("/tmp/wb-original-20261024.json").read_bytes()).hexdigest() == OLD_SHA
    )
    with (output / "report.json").open("x") as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
    engine.dispose()
    print(json.dumps(report))
