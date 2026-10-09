"""Acquire a small official Madagascar WDI corpus in Docker without DB/S3 access.

One-off corpus only, not a collector or R2.2 source qualification. No fallback domains,
authentication, browser, or requests after a policy rejection. No active credentials.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from ketrika.core.policy import PolicyEngine, PolicyStop

UA = "KetrikaAgriBot/0.1; contact@example.com"
CATALOGUE = "https://datacatalog.worldbank.org/public-licenses"
URL = "https://api.worldbank.org/v2/country/MDG/indicator/NY.GDP.MKTP.CD?date=2022:2023&format=json&source=2"


def main() -> None:
    output = Path("/tmp/ketrika-r04-wdi-acquisition")
    output.mkdir(exist_ok=False)
    policy = PolicyEngine()
    robots = []
    acquired = []
    with httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=False) as client:
        for host in ("api.worldbank.org", "datacatalog.worldbank.org"):
            url = f"https://{host}/robots.txt"
            policy.throttle(url, max_rps=0.2)
            response = client.get(url)
            policy.check_post_fetch(response.text, response.status_code, url)
            if response.status_code not in (200, 404):
                raise PolicyStop("Robots unreachable or redirected; acquisition refused")
            rules = response.text if response.status_code == 200 else ""
            policy.set_robots_txt(host, rules)
            robots.append(
                {
                    "url": url,
                    "http_status": response.status_code,
                    "sha256": hashlib.sha256(response.content).hexdigest(),
                    "rules": rules,
                    "interpretation": "RFC 9309: 404 has no rules; never ignore 401/403",
                }
            )
        for url in (CATALOGUE, URL):
            policy.check_pre_fetch(url, max_rps=0.2)
            fetched = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            response = client.get(url)
            policy.check_post_fetch(response.text, response.status_code, url)
            if response.status_code != 200:
                raise PolicyStop(f"Non-success: {response.status_code}; no redirect or retry")
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
            if url == CATALOGUE:
                if (
                    "creativecommons.org/licenses/by/4.0" not in response.text
                    or "default license" not in response.text
                ):
                    raise ValueError("Expected dataset licensing terms absent")
                acquired[-1]["verified_excerpt"] = (
                    "CC-BY 4.0 is the default license for World Bank-produced open datasets; attribution and additional terms apply."
                )
                acquired[-1]["excerpt_kind"] = "paraphrase of mechanically checked source clauses"
            else:
                payload = response.json()
                if not isinstance(payload, list) or len(payload) != 2 or len(payload[1]) != 2:
                    raise ValueError("Expected two annual WDI records")
                if any(
                    record.get("countryiso3code") != "MDG"
                    or record.get("indicator", {}).get("id") != "NY.GDP.MKTP.CD"
                    for record in payload[1]
                ):
                    raise ValueError("Country/indicator not verified by response")
                (output / "wdi_mdg_gdp_2022_2023.json").write_bytes(response.content)
    receipt = acquired[-1] | {
        "source_id": "world_bank_wdi_corpus",
        "source_url": URL,
        "catalogue_url": CATALOGUE,
        "discovered_at": acquired[0]["fetched_at"],
        "published_at": None,
        "bronze_object_key": None,
        "access_method": "api",
        "allowed_hosts": [urlsplit(URL).hostname],
        "user_agent": UA,
        "request_count": 4,
        "max_rps": 0.2,
        "robots": robots,
        "documentation": acquired[:-1],
        "rights": {
            "status": "verified",
            "licence": "CC BY 4.0 with World Bank additional dataset terms",
            "evidence": CATALOGUE,
            "redistribution_allowed": True,
            "attribution": "World Bank, World Development Indicators, GDP (current US$), Madagascar; unmodified API response",
        },
        "limitations": "Two annual GDP records only; not prices, agroclimate, a qualified connector, publication history, predictive accuracy or human review.",
    }
    (output / "acquisition.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(output),
                "requests": 4,
                "sha256": receipt["sha256"],
                "size_bytes": receipt["size_bytes"],
            }
        )
    )


if __name__ == "__main__":
    main()
