"""Compare archived record hashes with the received corpus; no URL is fetched."""

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import create_engine, text

base = Path("/tmp/copilot-clone-69aeb37/backend")
manifest = json.loads((base / "tests/corpus-manifest.json").read_text())
known = {}
for row in manifest["entries"]:
    assert hashlib.sha256((base / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    known[row["sha256"]] = row["authenticity"]
engine = create_engine(os.environ["DATABASE_URL"])
if engine.url.database != "ketrika_restore_au08_20261028":
    raise ValueError("Only the selected historical qualification clone is permitted")
counts: Counter[tuple[str, str | None, str]] = Counter()
with engine.connect() as connection, connection.begin():
    connection.execute(text("SET TRANSACTION READ ONLY"))
    rows = connection.execute(
        text(
            "SELECT source_id,source_url,content_sha256 FROM meta.source_record "
            "WHERE source_id IN ('miasa_odr','mincc_ppn','wb_rtfp_mdg') "
            "AND content_sha256 ~ '^[0-9a-f]{64}$'"
        )
    ).all()
    for source, url, digest in rows:
        host = urlsplit(url).hostname
        if host not in {"www.agriculture.gov.mg", "www.commerce.gov.mg", "microdata.worldbank.org"}:
            continue
        counts[(source, host, known.get(digest, "not_in_received_manifest"))] += 1
print(
    json.dumps(
        {
            "network_requests": 0,
            "rights_or_revision_qualified": False,
            "matches": [
                {"source_id": source, "hostname": host, "classification": kind, "records": count}
                for (source, host, kind), count in sorted(counts.items())
            ],
            "scope": "selected archived hashes only; no source URL or business values exported",
        },
        indent=2,
    )
)
engine.dispose()
