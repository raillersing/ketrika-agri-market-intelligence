"""Script to generate representative Douanes statistics fixtures, golden datasets, and revision snapshots (T4.3)."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def main() -> None:
    from ketrika.core.registry import find_repo_root

    root = find_repo_root()
    base_dir = (
        Path("/app")
        if Path("/app/tests").exists()
        else (root / "backend" if (root / "backend").exists() else root)
    )
    fixtures_dir = base_dir / "tests" / "fixtures" / "douanes_stats"
    golden_dir = base_dir / "tests" / "golden" / "douanes_stats"

    fixtures_dir.mkdir(parents=True, exist_ok=True)
    golden_dir.mkdir(parents=True, exist_ok=True)

    # 1. Main dataset: douanes_stats_2024.csv (36 trade flows across 3 months for PPN commodities)
    # Commodities:
    # - 1006.30: Riz semi-blanchi ou blanchi (import)
    # - 1511.90: Huile de palme et fractions (import)
    # - 1701.99: Sucre raffiné (import)
    # - 1101.00: Farine de froment / blé (import)
    # - 1005.90: Maïs grain (import et export)
    # - 0713.33: Haricot sec (export)

    commodities = [
        ("import", "10063000", "Riz semi-blanchi ou blanchi", "Inde", "IND", 25000000.0, 75000000000.0, 16666666.0),
        ("import", "10063000", "Riz semi-blanchi ou blanchi", "Pakistan", "PAK", 12000000.0, 36000000000.0, 8000000.0),
        ("import", "15119000", "Huile de palme et fractions", "Malaisie", "MYS", 8000000.0, 48000000000.0, 10666666.0),
        ("import", "15119000", "Huile de palme et fractions", "Indonésie", "IDN", 6500000.0, 39000000000.0, 8666666.0),
        ("import", "17019900", "Sucre de canne ou de betterave raffiné", "Maurice", "MUS", 5000000.0, 18000000000.0, 4000000.0),
        ("import", "17019900", "Sucre de canne ou de betterave raffiné", "Brésil", "BRA", 7000000.0, 24500000000.0, 5444444.0),
        ("import", "11010000", "Farine de froment ou de méteil", "Turquie", "TUR", 9000000.0, 29700000000.0, 6600000.0),
        ("import", "11010000", "Farine de froment ou de méteil", "Égypte", "EGY", 4500000.0, 14850000000.0, 3300000.0),
        ("import", "10059000", "Maïs en grains", "Afrique du Sud", "ZAF", 3500000.0, 7700000000.0, 1711111.0),
        ("export", "07133300", "Haricots secs communs", "Inde", "IND", 1200000.0, 5400000000.0, 1200000.0),
        ("export", "07133300", "Haricots secs communs", "Maurice", "MUS", 850000.0, 3825000000.0, 850000.0),
        ("export", "10059000", "Maïs en grains", "Réunion (France)", "FRA", 450000.0, 1125000000.0, 250000.0),
    ]

    months = [("2024", "01", "2024-01-01", "2024-01-31"), ("2024", "02", "2024-02-01", "2024-02-29"), ("2024", "03", "2024-03-01", "2024-03-31")]

    main_csv_rows = []
    golden_records = []

    for year, month, p_start, p_end in months:
        m_mult = 1.0 + (int(month) - 1) * 0.05  # slight monthly trend
        for flow, hs, name, partner, iso3, weight, val_mga, val_usd in commodities:
            w_adj = round(weight * m_mult, 1)
            v_mga_adj = round(val_mga * m_mult, 2)
            v_usd_adj = round(val_usd * m_mult, 2)

            main_csv_rows.append({
                "annee": year,
                "mois": month,
                "flux": flow,
                "code_sh": hs,
                "designation_produit": name,
                "pays_partenaire": partner,
                "code_iso3_pays": iso3,
                "poids_net_kg": f"{w_adj:.1f}",
                "valeur_caf_fob_mga": f"{v_mga_adj:.2f}",
                "valeur_usd": f"{v_usd_adj:.2f}",
            })

            golden_records.append({
                "flow": flow,
                "hs_code": hs,
                "product_raw": name,
                "partner_raw": partner,
                "partner_iso3": iso3,
                "period_start": p_start,
                "period_end": p_end,
                "weight_kg": w_adj,
                "value_mga": v_mga_adj,
                "value_usd": v_usd_adj,
            })

    # Write main CSV
    main_csv_file = fixtures_dir / "douanes_stats_2024.csv"
    fieldnames = [
        "annee", "mois", "flux", "code_sh", "designation_produit",
        "pays_partenaire", "code_iso3_pays", "poids_net_kg",
        "valeur_caf_fob_mga", "valeur_usd"
    ]
    with open(main_csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(main_csv_rows)
    print(f"Written {len(main_csv_rows)} rows to {main_csv_file.name}")

    # Write golden file
    golden_file = golden_dir / "douanes_stats_2024.expected.json"
    golden_payload = {
        "source_id": "douanes_stats",
        "records_count": len(golden_records),
        "records": golden_records,
    }
    with open(golden_file, "w", encoding="utf-8") as f:
        json.dump(golden_payload, f, indent=2, ensure_ascii=False)
    print(f"Written {len(golden_records)} golden records to {golden_file.name}")

    # 2. Revision test snapshot pair: douanes_snapshot_v1.csv and douanes_snapshot_v2.csv
    # In v1: 4 import flows for April 2024
    v1_rows = [
        {
            "annee": "2024", "mois": "04", "flux": "import", "code_sh": "10063000",
            "designation_produit": "Riz semi-blanchi ou blanchi", "pays_partenaire": "Inde",
            "code_iso3_pays": "IND", "poids_net_kg": "25000000.0", "valeur_caf_fob_mga": "75000000000.0",
            "valeur_usd": "16666666.0"
        },
        {
            "annee": "2024", "mois": "04", "flux": "import", "code_sh": "15119000",
            "designation_produit": "Huile de palme et fractions", "pays_partenaire": "Malaisie",
            "code_iso3_pays": "MYS", "poids_net_kg": "8000000.0", "valeur_caf_fob_mga": "48000000000.0",
            "valeur_usd": "10666666.0"
        },
        {
            "annee": "2024", "mois": "04", "flux": "import", "code_sh": "17019900",
            "designation_produit": "Sucre de canne ou de betterave raffiné", "pays_partenaire": "Maurice",
            "code_iso3_pays": "MUS", "poids_net_kg": "5000000.0", "valeur_caf_fob_mga": "18000000000.0",
            "valeur_usd": "4000000.0"
        },
        {
            "annee": "2024", "mois": "04", "flux": "import", "code_sh": "11010000",
            "designation_produit": "Farine de froment ou de méteil", "pays_partenaire": "Turquie",
            "code_iso3_pays": "TUR", "poids_net_kg": "9000000.0", "valeur_caf_fob_mga": "29700000000.0",
            "valeur_usd": "6600000.0"
        },
    ]

    # In v2: Flow 1 (India Rice import) is revised: weight adjusted to 26,500,000 kg and value to 79,500,000,000 MGA
    v2_rows = [
        {
            "annee": "2024", "mois": "04", "flux": "import", "code_sh": "10063000",
            "designation_produit": "Riz semi-blanchi ou blanchi", "pays_partenaire": "Inde",
            "code_iso3_pays": "IND", "poids_net_kg": "26500000.0", "valeur_caf_fob_mga": "79500000000.0",
            "valeur_usd": "17666666.0"
        },
        v1_rows[1],
        v1_rows[2],
        v1_rows[3],
    ]

    v1_file = fixtures_dir / "douanes_snapshot_v1.csv"
    with open(v1_file, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(v1_rows)
    print(f"Written v1 snapshot ({v1_file.name})")

    v2_file = fixtures_dir / "douanes_snapshot_v2.csv"
    with open(v2_file, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(v2_rows)
    print(f"Written v2 snapshot ({v2_file.name})")


if __name__ == "__main__":
    main()
