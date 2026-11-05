#!/usr/bin/env python3
"""Diagnostic script to safely test live network connectivity to external data providers.

Respects AGENTS.md §8: Polite requests only, standard user agent, read-only headers/samples.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from typing import Any

SOURCES: dict[str, dict[str, Any]] = {
    "NASA POWER API (Agroclimatologie Point Madagascar)": {
        "url": "https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M,PRECTOTCORR&community=AG&longitude=47.5&latitude=-18.9&start=20240101&end=20240105&format=JSON",
        "headers": {"User-Agent": "Ketrika-Market-Intelligence/0.2.0 (audit@ketrika.mg)"},
    },
    "World Bank Commodity Data (Pink Sheet Historique 2026)": {
        "url": "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx",
        "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    },
    "HDX / WFP Package API (Madagascar Food Prices)": {
        "url": "https://data.humdata.org/api/3/action/package_show?id=wfp-food-prices-for-madagascar",
        "headers": {
            "User-Agent": "Ketrika-Market-Intelligence/0.2.0 (audit@ketrika.mg)",
            **(
                {"Authorization": f"Bearer {os.environ['HDX_API_KEY']}"}
                if os.environ.get("HDX_API_KEY")
                else {}
            ),
        },
    },
    "Drewry World Container Index (Fret Maritime Mondial)": {
        "url": "https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry",
        "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    },
    "Banque Centrale de Madagascar (Portail BCM)": {
        "url": "https://www.banque-centrale.mg/",
        "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    },
}


def test_source(name: str, config: dict[str, Any]) -> bool:
    print(f"\n[+] Test de : {name}")
    print(f"    URL : {config['url'][:85]}...")
    req = urllib.request.Request(config["url"], headers=config["headers"])
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            code = resp.getcode()
            sample = resp.read(256)
            print(f"    ✔ Statut HTTP {code} OK (échantillon de {len(sample)} octets reçu en direct)")
            return True
    except urllib.error.HTTPError as exc:
        print(f"    ✖ Erreur HTTP {exc.code} : {exc.reason}")
        if exc.code == 403:
            print("      -> Action requise : Jeton API HDX ou en-têtes d'identification nécessaires.")
        return False
    except urllib.error.URLError as exc:
        print(f"    ✖ Erreur réseau : {exc.reason}")
        return False
    except Exception as exc:
        print(f"    ✖ Exception inattendue : {exc}")
        return False


def main() -> int:
    print("=" * 70)
    print("   Ketrika Agri Intelligence — Diagnostic Réseau Sources Live")
    print("=" * 70)
    results = [test_source(name, conf) for name, conf in SOURCES.items()]
    success = sum(results)
    total = len(results)
    print("\n" + "=" * 70)
    print(f"Bilan de connectivité : {success}/{total} sources accessibles en direct.")
    print("=" * 70)
    return 0 if success == total else 1


if __name__ == "__main__":
    sys.exit(main())
