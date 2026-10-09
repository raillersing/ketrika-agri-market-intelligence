"""Bounded public NASA acquisition in a disposable Docker container, never active S3.

No authentication, messages, browser, database, or alternate domains after rejection.
Only machine-produced bytes/receipts are written to a new /tmp output directory.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from protego import Protego

from ketrika.core.policy import PolicyEngine, PolicyStop

HOST = "power.larc.nasa.gov"
CATALOGUE = f"https://{HOST}/docs/services/api/temporal/daily/"
RIGHTS_URL = "https://registry.opendata.aws/nasa-power/"
URL = (
    f"https://{HOST}/api/temporal/daily/point?parameters=PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M"
    "&community=AG&longitude=47.525&latitude=-18.924&start=20240101&end=20240103"
    "&format=JSON&time-standard=UTC"
)
UA = "KetrikaAgriBot/0.1; contact@example.com"


def main() -> None:
    output = Path("/tmp/ketrika-r04-nasa-acquisition")
    output.mkdir(exist_ok=False)
    policy = PolicyEngine()
    receipts = []
    acquired = []
    with httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=False) as client:
        for host in (HOST, "registry.opendata.aws"):
            url = f"https://{host}/robots.txt"
            policy.throttle(url, max_rps=0.2)
            response = client.get(url)
            policy.check_post_fetch(response.text, response.status_code, url)
            if response.status_code != 200:
                raise PolicyStop("Robots unavailable: acquisition refused")
            parser = Protego.parse(response.text)
            policy.set_robots_txt(host, response.text)
            urls = (CATALOGUE, URL) if host == HOST else (RIGHTS_URL,)
            if not all(parser.can_fetch(target, UA) for target in urls):
                raise PolicyStop("Robots refuses corpus acquisition")
            receipts.append(
                {
                    "url": url,
                    "http_status": 200,
                    "sha256": hashlib.sha256(response.content).hexdigest(),
                    "rules": response.text,
                }
            )
        for url in (CATALOGUE, RIGHTS_URL, URL):
            policy.check_pre_fetch(url, max_rps=0.2)
            fetched = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            response = client.get(url)
            policy.check_post_fetch(response.text, response.status_code, url)
            if response.status_code != 200:
                raise PolicyStop(f"No success/redirect bypass permitted: {response.status_code}")
            if len(response.content) > 5 * 1024 * 1024:
                raise ValueError("Corpus response exceeds 5 MiB")
            acquired.append(
                {
                    "url": url,
                    "http_status": 200,
                    "fetched_at": fetched,
                    "sha256": hashlib.sha256(response.content).hexdigest(),
                    "size_bytes": len(response.content),
                    "mime_type": response.headers.get("content-type", ""),
                    "redirect_chain": [url],
                }
            )
            if url == RIGHTS_URL:
                clause = "There are no restrictions on the use, access, and/or download of data from the NASA POWER Project."
                if clause not in response.text:
                    raise ValueError("Expected rights clause not present; do not invent rights")
                acquired[-1]["verified_excerpt"] = clause
                acquired[-1]["creative_commons_by_4_link_present"] = (
                    "creativecommons.org/licenses/by/4.0" in response.text
                )
            if url == URL:
                payload = response.json()
                if payload.get("type") != "Feature" or not payload.get("properties", {}).get(
                    "parameter"
                ):
                    raise ValueError("Unexpected NASA data response")
                (output / "nasa_power_20240101_20240103.json").write_bytes(response.content)
    receipt = acquired[-1] | {
        "source_id": "nasa_power",
        "source_url": URL,
        "catalogue_url": CATALOGUE,
        "discovered_at": acquired[0]["fetched_at"],
        "published_at": None,
        "bronze_object_key": None,
        "access_method": "api",
        "allowed_hosts": [urlsplit(URL).hostname],
        "user_agent": UA,
        "request_count": 5,
        "max_rps": 0.2,
        "robots": receipts,
        "documentation": acquired[:-1],
        "rights": {
            "status": "verified",
            "licence": "POWER unrestricted use/access/download; CC BY 4.0 linked by NASA-managed AWS catalogue",
            "evidence": RIGHTS_URL,
            "redistribution_allowed": True,
            "attribution": "NASA Langley Research Center POWER Project",
        },
        "limitations": "One historical grid-point response, model-derived meteorology, not a station observation, continuous live collector, market forecast or human review.",
    }
    (output / "acquisition.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(output),
                "requests": 5,
                "sha256": receipt["sha256"],
                "size_bytes": receipt["size_bytes"],
            }
        )
    )


if __name__ == "__main__":
    main()
