"""Script to generate representative MinCC PPN price and stock fixtures, golden datasets, and LLM replay fixtures (T4.2)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def compute_cache_key(
    provider: str,
    model: str,
    prompt_id: str,
    prompt_version: str,
    content_sha256: str,
    page: int = 1,
) -> str:
    raw = f"{provider}|{model}|{prompt_id}|{prompt_version}|{content_sha256}|{page}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> None:
    from ketrika.core.registry import find_repo_root

    if Path("/app/tests").exists():
        base_dir = Path("/app")
    elif (root / "backend").exists():
        base_dir = root / "backend"
    else:
        base_dir = root
    fixtures_dir = base_dir / "tests" / "fixtures" / "mincc_ppn"
    golden_dir = base_dir / "tests" / "golden" / "mincc_ppn"
    llm_dir = base_dir / "tests" / "fixtures" / "llm"

    fixtures_dir.mkdir(parents=True, exist_ok=True)
    golden_dir.mkdir(parents=True, exist_ok=True)
    llm_dir.mkdir(parents=True, exist_ok=True)

    # 1. Six HTML publications with structured tables
    html_docs = [
        {
            "id": "mincc_pub_01_analamanga_html",
            "region": "Analamanga",
            "date": "2024-02-05",
            "p_start": "2024-02-01",
            "p_end": "2024-02-07",
            "title": "Direction Régionale Analamanga - Relevé Hebdomadaire des Prix et Stocks PPN",
            "items": [
                {
                    "product": "Sucre blanc",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "4 200",
                    "price_val": 4200.0,
                    "unit": "kg",
                    "stock_raw": "1 200 tonnes",
                    "stock_val": 1200.0,
                    "stock_unit": "tonne",
                    "coverage_days": 45.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
                {
                    "product": "Huile alimentaire vrac",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "7 500",
                    "price_val": 7500.0,
                    "unit": "litre",
                    "stock_raw": "850 tonnes",
                    "stock_val": 850.0,
                    "stock_unit": "tonne",
                    "coverage_days": 25.0,
                    "status_label": "Tendu",
                    "status": "tight",
                },
                {
                    "product": "Farine de blé",
                    "actor_level": "wholesale",
                    "actor_label": "Gros",
                    "price_raw": "3 600",
                    "price_val": 3600.0,
                    "unit": "kg",
                    "stock_raw": "1 100 tonnes",
                    "stock_val": 1100.0,
                    "stock_unit": "tonne",
                    "coverage_days": 35.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
                {
                    "product": "Riz blanc local",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "2 800",
                    "price_val": 2800.0,
                    "unit": "kg",
                    "stock_raw": "2 400 tonnes",
                    "stock_val": 2400.0,
                    "stock_unit": "tonne",
                    "coverage_days": 60.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
            ],
        },
        {
            "id": "mincc_pub_02_atsinanana_html",
            "region": "Atsinanana",
            "date": "2024-02-06",
            "p_start": "2024-02-01",
            "p_end": "2024-02-07",
            "title": "DRCC Atsinanana - Suivi des Prix et Stocks aux Débarquements et Entrepôts Toamasina",
            "items": [
                {
                    "product": "Sucre blanc",
                    "actor_level": "wholesale",
                    "actor_label": "Gros",
                    "price_raw": "3 950",
                    "price_val": 3950.0,
                    "unit": "kg",
                    "stock_raw": "2 800 tonnes",
                    "stock_val": 2800.0,
                    "stock_unit": "tonne",
                    "coverage_days": 70.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
                {
                    "product": "Huile alimentaire vrac",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "7 100",
                    "price_val": 7100.0,
                    "unit": "litre",
                    "stock_raw": "1 950 tonnes",
                    "stock_val": 1950.0,
                    "stock_unit": "tonne",
                    "coverage_days": 50.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
                {
                    "product": "Farine de blé",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "3 800",
                    "price_val": 3800.0,
                    "unit": "kg",
                    "stock_raw": "950 tonnes",
                    "stock_val": 950.0,
                    "stock_unit": "tonne",
                    "coverage_days": 30.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
                {
                    "product": "Riz blanc importé",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "2 700",
                    "price_val": 2700.0,
                    "unit": "kg",
                    "stock_raw": "4 500 tonnes",
                    "stock_val": 4500.0,
                    "stock_unit": "tonne",
                    "coverage_days": 90.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
            ],
        },
        {
            "id": "mincc_pub_03_boeny_html",
            "region": "Boeny",
            "date": "2024-02-07",
            "p_start": "2024-02-01",
            "p_end": "2024-02-07",
            "title": "DRCC Boeny - Tableau de Bord PPN Marchés et Grossistes Mahajanga",
            "items": [
                {
                    "product": "Sucre blanc",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "4 300",
                    "price_val": 4300.0,
                    "unit": "kg",
                    "stock_raw": "650 tonnes",
                    "stock_val": 650.0,
                    "stock_unit": "tonne",
                    "coverage_days": 20.0,
                    "status_label": "Tendu",
                    "status": "tight",
                },
                {
                    "product": "Huile alimentaire vrac",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "7 600",
                    "price_val": 7600.0,
                    "unit": "litre",
                    "stock_raw": "420 tonnes",
                    "stock_val": 420.0,
                    "stock_unit": "tonne",
                    "coverage_days": 18.0,
                    "status_label": "Tendu",
                    "status": "tight",
                },
                {
                    "product": "Farine de blé",
                    "actor_level": "wholesale",
                    "actor_label": "Gros",
                    "price_raw": "3 700",
                    "price_val": 3700.0,
                    "unit": "kg",
                    "stock_raw": "580 tonnes",
                    "stock_val": 580.0,
                    "stock_unit": "tonne",
                    "coverage_days": 28.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
                {
                    "product": "Riz blanc local",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "2 900",
                    "price_val": 2900.0,
                    "unit": "kg",
                    "stock_raw": "1 200 tonnes",
                    "stock_val": 1200.0,
                    "stock_unit": "tonne",
                    "coverage_days": 40.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
            ],
        },
        {
            "id": "mincc_pub_04_vakinankaratra_html",
            "region": "Vakinankaratra",
            "date": "2024-02-08",
            "p_start": "2024-02-01",
            "p_end": "2024-02-07",
            "title": "DRCC Vakinankaratra - Relevé PPN District Antsirabe I et II",
            "items": [
                {
                    "product": "Sucre blanc",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "4 250",
                    "price_val": 4250.0,
                    "unit": "kg",
                    "stock_raw": "800 tonnes",
                    "stock_val": 800.0,
                    "stock_unit": "tonne",
                    "coverage_days": 30.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
                {
                    "product": "Huile alimentaire vrac",
                    "actor_level": "wholesale",
                    "actor_label": "Gros",
                    "price_raw": "7 200",
                    "price_val": 7200.0,
                    "unit": "litre",
                    "stock_raw": "600 tonnes",
                    "stock_val": 600.0,
                    "stock_unit": "tonne",
                    "coverage_days": 22.0,
                    "status_label": "Tendu",
                    "status": "tight",
                },
                {
                    "product": "Farine de blé",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "3 850",
                    "price_val": 3850.0,
                    "unit": "kg",
                    "stock_raw": "720 tonnes",
                    "stock_val": 720.0,
                    "stock_unit": "tonne",
                    "coverage_days": 32.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
                {
                    "product": "Riz blanc local",
                    "actor_level": "wholesale",
                    "actor_label": "Gros",
                    "price_raw": "2 650",
                    "price_val": 2650.0,
                    "unit": "kg",
                    "stock_raw": "3 100 tonnes",
                    "stock_val": 3100.0,
                    "stock_unit": "tonne",
                    "coverage_days": 75.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
            ],
        },
        {
            "id": "mincc_pub_05_atsimo_andrefana_html",
            "region": "Atsimo-Andrefana",
            "date": "2024-02-09",
            "p_start": "2024-02-01",
            "p_end": "2024-02-07",
            "title": "DRCC Atsimo-Andrefana - Bulletin de Veille des PPN Toliara",
            "items": [
                {
                    "product": "Sucre blanc",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "4 400",
                    "price_val": 4400.0,
                    "unit": "kg",
                    "stock_raw": "350 tonnes",
                    "stock_val": 350.0,
                    "stock_unit": "tonne",
                    "coverage_days": 12.0,
                    "status_label": "Tendu",
                    "status": "tight",
                },
                {
                    "product": "Huile alimentaire vrac",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "7 800",
                    "price_val": 7800.0,
                    "unit": "litre",
                    "stock_raw": "280 tonnes",
                    "stock_val": 280.0,
                    "stock_unit": "tonne",
                    "coverage_days": 10.0,
                    "status_label": "Rupture",
                    "status": "shortage",
                },
                {
                    "product": "Farine de blé",
                    "actor_level": "wholesale",
                    "actor_label": "Gros",
                    "price_raw": "3 900",
                    "price_val": 3900.0,
                    "unit": "kg",
                    "stock_raw": "410 tonnes",
                    "stock_val": 410.0,
                    "stock_unit": "tonne",
                    "coverage_days": 15.0,
                    "status_label": "Tendu",
                    "status": "tight",
                },
                {
                    "product": "Riz blanc local",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "3 100",
                    "price_val": 3100.0,
                    "unit": "kg",
                    "stock_raw": "950 tonnes",
                    "stock_val": 950.0,
                    "stock_unit": "tonne",
                    "coverage_days": 25.0,
                    "status_label": "Tendu",
                    "status": "tight",
                },
            ],
        },
        {
            "id": "mincc_pub_06_diana_html",
            "region": "Diana",
            "date": "2024-02-10",
            "p_start": "2024-02-01",
            "p_end": "2024-02-07",
            "title": "DRCC Diana - Situation PPN et Surveillance des Stocks Antsiranana",
            "items": [
                {
                    "product": "Sucre blanc",
                    "actor_level": "wholesale",
                    "actor_label": "Gros",
                    "price_raw": "4 100",
                    "price_val": 4100.0,
                    "unit": "kg",
                    "stock_raw": "700 tonnes",
                    "stock_val": 700.0,
                    "stock_unit": "tonne",
                    "coverage_days": 25.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
                {
                    "product": "Huile alimentaire vrac",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "7 700",
                    "price_val": 7700.0,
                    "unit": "litre",
                    "stock_raw": "500 tonnes",
                    "stock_val": 500.0,
                    "stock_unit": "tonne",
                    "coverage_days": 20.0,
                    "status_label": "Tendu",
                    "status": "tight",
                },
                {
                    "product": "Farine de blé",
                    "actor_level": "retail",
                    "actor_label": "Détail",
                    "price_raw": "3 950",
                    "price_val": 3950.0,
                    "unit": "kg",
                    "stock_raw": "480 tonnes",
                    "stock_val": 480.0,
                    "stock_unit": "tonne",
                    "coverage_days": 22.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
                {
                    "product": "Riz blanc importé",
                    "actor_level": "wholesale",
                    "actor_label": "Gros",
                    "price_raw": "2 750",
                    "price_val": 2750.0,
                    "unit": "kg",
                    "stock_raw": "1 800 tonnes",
                    "stock_val": 1800.0,
                    "stock_unit": "tonne",
                    "coverage_days": 45.0,
                    "status_label": "Suffisant",
                    "status": "sufficient",
                },
            ],
        },
    ]

    # Write HTML table fixtures and their expected golden files
    for doc in html_docs:
        html_file = fixtures_dir / f"{doc['id']}.html"
        rows_html = []
        golden_records = []
        for it in doc["items"]:
            rows_html.append(
                f"<tr><td>{it['product']}</td><td>{it['actor_label']}</td><td>{it['price_raw']}</td>"
                f"<td>{it['stock_raw']}</td><td>{int(it['coverage_days'])}</td><td>{it['status_label']}</td></tr>"
            )
            # Price record expected
            golden_records.append(
                {
                    "record_type": "price",
                    "product_raw": it["product"],
                    "actor_level": it["actor_level"],
                    "location_raw": doc["region"],
                    "period_start": doc["p_start"],
                    "period_end": doc["p_end"],
                    "price_raw": it["price_raw"],
                    "price_value": it["price_val"],
                    "unit_raw": it["unit"],
                    "currency_raw": "MGA",
                    "observed_or_imputed": "observed",
                }
            )
            # Stock record expected
            golden_records.append(
                {
                    "record_type": "stock",
                    "product_raw": it["product"],
                    "location_raw": doc["region"],
                    "period_start": doc["p_start"],
                    "period_end": doc["p_end"],
                    "quantity_raw": it["stock_raw"],
                    "quantity_value": it["stock_val"],
                    "unit_raw": it["stock_unit"],
                    "stock_status": it["status"],
                    "coverage_days": it["coverage_days"],
                }
            )

        html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>{doc['title']}</title>
</head>
<body>
    <h1>MINISTÈRE DE L'INDUSTRIALISATION ET DU COMMERCE</h1>
    <h2>{doc['title']}</h2>
    <p>Région : {doc['region']} | Date de publication : {doc['date']}</p>
    <p>Période d'observation : du {doc['p_start']} au {doc['p_end']}</p>
    <table>
        <thead>
            <tr>
                <th>Produit</th>
                <th>Stade de commercialisation</th>
                <th>Prix (Ariary)</th>
                <th>Stock disponible</th>
                <th>Couverture (jours)</th>
                <th>Statut approvisionnement</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>
</body>
</html>
"""
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        golden_file = golden_dir / f"{doc['id']}.expected.json"
        golden_payload = {
            "doc_id": doc["id"],
            "source_id": "mincc_ppn",
            "region": doc["region"],
            "published_at": f"{doc['date']}T08:00:00Z",
            "period_start": doc["p_start"],
            "period_end": doc["p_end"],
            "records_count": len(golden_records),
            "prices_count": len([r for r in golden_records if r["record_type"] == "price"]),
            "stocks_count": len([r for r in golden_records if r["record_type"] == "stock"]),
            "records": golden_records,
        }
        with open(golden_file, "w", encoding="utf-8") as f:
            json.dump(golden_payload, f, indent=2, ensure_ascii=False)

    # 2. Four textual communiques (2 French, 2 Malagasy)
    text_docs = [
        {
            "id": "mincc_pub_07_communique_analamanga_fr",
            "region": "Analamanga",
            "date": "2024-02-15",
            "p_start": "2024-02-08",
            "p_end": "2024-02-15",
            "title": "Communiqué DRCC Analamanga N° 12/2024",
            "lang": "fr",
            "text": (
                "DIRECTION RÉGIONALE DU COMMERCE ET DE LA CONSOMMATION D'ANALAMANGA\n"
                "COMMUNIQUÉ DE PRESSE N° 12/2024-DRCC/ANA\n"
                "Objet : Suivi des prix et de l'état des stocks de produits de première nécessité (PPN)\n"
                "Antananarivo, le 15 février 2024.\n"
                "La Direction Régionale du Commerce et de la Consommation (DRCC) d'Analamanga informe les opérateurs et les consommateurs "
                "que les opérations de contrôle des prix et des stocks se poursuivent activement dans la capitale et sa périphérie.\n"
                "Concernant le sucre blanc, le cours moyen au détail constaté sur les principaux marchés d'Antananarivo s'établit à 4 250 Ar/kg. "
                "Les entrepôts de la région disposent d'un volume global de 1 350 tonnes, garantissant une couverture de 48 jours d'approvisionnement normal.\n"
                "Pour l'huile alimentaire en vrac, le prix au détail est surveillé à 7 450 Ar/L. "
                "Le niveau des stocks disponibles atteint 920 tonnes, ce qui correspond à une durée de couverture estimée à 28 jours avec un statut d'approvisionnement suffisant."
            ),
            "prices": [
                {
                    "product_raw": "Sucre blanc",
                    "actor_level": "retail",
                    "location_raw": "Analamanga",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "price_raw": "4 250",
                    "price_value": 4250.0,
                    "unit_raw": "kg",
                    "currency_raw": "MGA",
                    "observed_or_imputed": "observed",
                    "evidence_text": "cours moyen au détail constaté sur les principaux marchés d'Antananarivo s'établit à 4 250 Ar/kg",
                },
                {
                    "product_raw": "Huile alimentaire vrac",
                    "actor_level": "retail",
                    "location_raw": "Analamanga",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "price_raw": "7 450",
                    "price_value": 7450.0,
                    "unit_raw": "litre",
                    "currency_raw": "MGA",
                    "observed_or_imputed": "observed",
                    "evidence_text": "Pour l'huile alimentaire en vrac, le prix au détail est surveillé à 7 450 Ar/L",
                },
            ],
            "stocks": [
                {
                    "product_raw": "Sucre blanc",
                    "location_raw": "Analamanga",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "quantity_raw": "1 350 tonnes",
                    "quantity_value": 1350.0,
                    "unit_raw": "tonne",
                    "stock_status": "sufficient",
                    "coverage_days": 48.0,
                    "evidence_text": "volume global de 1 350 tonnes, garantissant une couverture de 48 jours d'approvisionnement normal",
                },
                {
                    "product_raw": "Huile alimentaire vrac",
                    "location_raw": "Analamanga",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "quantity_raw": "920 tonnes",
                    "quantity_value": 920.0,
                    "unit_raw": "tonne",
                    "stock_status": "sufficient",
                    "coverage_days": 28.0,
                    "evidence_text": "niveau des stocks disponibles atteint 920 tonnes, ce qui correspond à une durée de couverture estimée à 28 jours",
                },
            ],
        },
        {
            "id": "mincc_pub_08_communique_atsinanana_fr",
            "region": "Atsinanana",
            "date": "2024-02-16",
            "p_start": "2024-02-08",
            "p_end": "2024-02-15",
            "title": "Communiqué Officiel DRCC Atsinanana N° 05/2024",
            "lang": "fr",
            "text": (
                "DIRECTION RÉGIONALE DU COMMERCE ET DE LA CONSOMMATION ATSINANANA\n"
                "COMMUNIQUÉ OFFICIEL N° 05/2024-DRCC/ATS\n"
                "Objet : Situation des débarquements portuaires et des stocks PPN à Toamasina\n"
                "Toamasina, le 16 février 2024.\n"
                "La DRCC Atsinanana communique les derniers relevés relatifs aux denrées stratégiques dans le district de Toamasina.\n"
                "À l'issue du déchargement au grand port, le stock de farine de blé en magasin s'élève à 1 450 tonnes (couverture estimée à 42 jours, situation normale). "
                "Le prix de gros officiel s'établit à 3 550 Ar/kg.\n"
                "Par ailleurs, pour le riz blanc importé (25% brisures), le prix au détail est de 2 680 Ar/kg. "
                "Les stocks disponibles dans les silos portuaires s'élèvent à 5 200 tonnes, assurant 100 jours de couverture pour le marché régional."
            ),
            "prices": [
                {
                    "product_raw": "Farine de blé",
                    "actor_level": "wholesale",
                    "location_raw": "Atsinanana",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "price_raw": "3 550",
                    "price_value": 3550.0,
                    "unit_raw": "kg",
                    "currency_raw": "MGA",
                    "observed_or_imputed": "observed",
                    "evidence_text": "Le prix de gros officiel s'établit à 3 550 Ar/kg",
                },
                {
                    "product_raw": "Riz blanc importé",
                    "actor_level": "retail",
                    "location_raw": "Atsinanana",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "price_raw": "2 680",
                    "price_value": 2680.0,
                    "unit_raw": "kg",
                    "currency_raw": "MGA",
                    "observed_or_imputed": "observed",
                    "evidence_text": "pour le riz blanc importé (25% brisures), le prix au détail est de 2 680 Ar/kg",
                },
            ],
            "stocks": [
                {
                    "product_raw": "Farine de blé",
                    "location_raw": "Atsinanana",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "quantity_raw": "1 450 tonnes",
                    "quantity_value": 1450.0,
                    "unit_raw": "tonne",
                    "stock_status": "sufficient",
                    "coverage_days": 42.0,
                    "evidence_text": "stock de farine de blé en magasin s'élève à 1 450 tonnes (couverture estimée à 42 jours, situation normale)",
                },
                {
                    "product_raw": "Riz blanc importé",
                    "location_raw": "Atsinanana",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "quantity_raw": "5 200 tonnes",
                    "quantity_value": 5200.0,
                    "unit_raw": "tonne",
                    "stock_status": "sufficient",
                    "coverage_days": 100.0,
                    "evidence_text": "stocks disponibles dans les silos portuaires s'élèvent à 5 200 tonnes, assurant 100 jours de couverture",
                },
            ],
        },
        {
            "id": "mincc_pub_09_filazana_boeny_mg",
            "region": "Boeny",
            "date": "2024-02-17",
            "p_start": "2024-02-08",
            "p_end": "2024-02-15",
            "title": "Filazana DRCC Boeny Laharana 08/2024",
            "lang": "mg",
            "text": (
                "FITONDRANA HO AN'NY INDOSTRIA SY NY VAROTRA (DRCC) FARITRA BOENY\n"
                "FILAZANA LAHARANA 08/2024-DRCC/BOE\n"
                "Momba ny vidin-javatra sy ny tahiry PPN ao Mahajanga\n"
                "Mahajanga, faha 17 Febroary 2024.\n"
                "Mampahafantatra ny rehetra ny fitondram-paritra misahana ny varotra ao Boeny fa milamina amin'ny ankapobeny ny tsena sy ny fandatsahana entana.\n"
                "Mikasika ny siramamy fotsy (sucre blanc), ny vidiny antsinjarany ara-dalàna eny an-tsena dia 4 350 Ar isaky ny kilao. "
                "Ny tahiry voaangona any amin'ny tranom-barotra lehibe dia mahatratra 580 taona (tonnes), ampy ho an'ny 18 andro (tendu / misedra fahasahiranana).\n"
                "Ho an'ny menaka fihinana vrac (huile alimentaire), ny vidiny antsinjarany dia 7 650 Ar isaky ny litatra. "
                "Ny tahiry misy kosa dia 390 taona (tonnes), ampy ho an'ny 16 andro, ka mampiseho fahasahiranana (tendu)."
            ),
            "prices": [
                {
                    "product_raw": "Sucre blanc",
                    "actor_level": "retail",
                    "location_raw": "Boeny",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "price_raw": "4 350",
                    "price_value": 4350.0,
                    "unit_raw": "kg",
                    "currency_raw": "MGA",
                    "observed_or_imputed": "observed",
                    "evidence_text": "vidiny antsinjarany ara-dalàna eny an-tsena dia 4 350 Ar isaky ny kilao",
                },
                {
                    "product_raw": "Huile alimentaire vrac",
                    "actor_level": "retail",
                    "location_raw": "Boeny",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "price_raw": "7 650",
                    "price_value": 7650.0,
                    "unit_raw": "litre",
                    "currency_raw": "MGA",
                    "observed_or_imputed": "observed",
                    "evidence_text": "Ho an'ny menaka fihinana vrac (huile alimentaire), ny vidiny antsinjarany dia 7 650 Ar isaky ny litatra",
                },
            ],
            "stocks": [
                {
                    "product_raw": "Sucre blanc",
                    "location_raw": "Boeny",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "quantity_raw": "580 tonnes",
                    "quantity_value": 580.0,
                    "unit_raw": "tonne",
                    "stock_status": "tight",
                    "coverage_days": 18.0,
                    "evidence_text": "tahiry voaangona any amin'ny tranom-barotra lehibe dia mahatratra 580 taona (tonnes), ampy ho an'ny 18 andro",
                },
                {
                    "product_raw": "Huile alimentaire vrac",
                    "location_raw": "Boeny",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "quantity_raw": "390 tonnes",
                    "quantity_value": 390.0,
                    "unit_raw": "tonne",
                    "stock_status": "tight",
                    "coverage_days": 16.0,
                    "evidence_text": "tahiry misy kosa dia 390 taona (tonnes), ampy ho an'ny 16 andro, ka mampiseho fahasahiranana",
                },
            ],
        },
        {
            "id": "mincc_pub_10_filazana_vakinankaratra_mg",
            "region": "Vakinankaratra",
            "date": "2024-02-18",
            "p_start": "2024-02-08",
            "p_end": "2024-02-15",
            "title": "Fanambarana DRCC Vakinankaratra Laharana 14/2024",
            "lang": "mg",
            "text": (
                "FITANDREMANA NY VAROTRA SY NY FANJIHANA (DRCC) VAKINANKARATRA\n"
                "FANAMBARANA LAHARANA 14/2024-DRCC/VAK\n"
                "Fanaraha-maso ny vidin'ny vary sy ny lafarinina ao Antsirabe\n"
                "Antsirabe, faha 18 Febroary 2024.\n"
                "Ny DRCC Vakinankaratra dia mamoaka ny vokatry ny fanadihadiana natao tamin'ireo mpamongady sy mpaninjara PPN.\n"
                "Ny vary gasy fotsy (riz blanc local) dia amidy 2 750 Ar ny kilao amin'ny antsinjarany. "
                "Ny tahiry ao an-toerana dia 2 900 taona (tonnes), ampy ho an'ny 70 andro (normal / ampy tsara).\n"
                "Ny lafarinina varimbazaha (farine de blé) kosa dia mitentina 3 800 Ar ny kilao amin'ny antsinjarany. "
                "Ny tahiry voarakitra dia 680 taona (tonnes), ampy ho an'ny 30 andro (ampy / suffisant)."
            ),
            "prices": [
                {
                    "product_raw": "Riz blanc local",
                    "actor_level": "retail",
                    "location_raw": "Vakinankaratra",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "price_raw": "2 750",
                    "price_value": 2750.0,
                    "unit_raw": "kg",
                    "currency_raw": "MGA",
                    "observed_or_imputed": "observed",
                    "evidence_text": "vary gasy fotsy (riz blanc local) dia amidy 2 750 Ar ny kilao amin'ny antsinjarany",
                },
                {
                    "product_raw": "Farine de blé",
                    "actor_level": "retail",
                    "location_raw": "Vakinankaratra",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "price_raw": "3 800",
                    "price_value": 3800.0,
                    "unit_raw": "kg",
                    "currency_raw": "MGA",
                    "observed_or_imputed": "observed",
                    "evidence_text": "lafarinina varimbazaha (farine de blé) kosa dia mitentina 3 800 Ar ny kilao amin'ny antsinjarany",
                },
            ],
            "stocks": [
                {
                    "product_raw": "Riz blanc local",
                    "location_raw": "Vakinankaratra",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "quantity_raw": "2 900 tonnes",
                    "quantity_value": 2900.0,
                    "unit_raw": "tonne",
                    "stock_status": "sufficient",
                    "coverage_days": 70.0,
                    "evidence_text": "tahiry ao an-toerana dia 2 900 taona (tonnes), ampy ho an'ny 70 andro",
                },
                {
                    "product_raw": "Farine de blé",
                    "location_raw": "Vakinankaratra",
                    "period_start": "2024-02-08",
                    "period_end": "2024-02-15",
                    "quantity_raw": "680 tonnes",
                    "quantity_value": 680.0,
                    "unit_raw": "tonne",
                    "stock_status": "sufficient",
                    "coverage_days": 30.0,
                    "evidence_text": "tahiry voarakitra dia 680 taona (tonnes), ampy ho an'ny 30 andro",
                },
            ],
        },
    ]

    for doc in text_docs:
        html_file = fixtures_dir / f"{doc['id']}.html"
        html_content = f"""<!DOCTYPE html>
<html lang="{doc['lang']}">
<head>
    <meta charset="UTF-8">
    <title>{doc['title']}</title>
</head>
<body>
    <article>
        <h1>{doc['title']}</h1>
        <p><strong>Région :</strong> {doc['region']}</p>
        <p><strong>Date :</strong> {doc['date']}</p>
        <p><strong>Période :</strong> du {doc['p_start']} au {doc['p_end']}</p>
        <div class="content">
            {"<p>" + "</p><p>".join(doc['text'].splitlines()) + "</p>"}
        </div>
    </article>
</body>
</html>
"""
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Compute SHA-256 of the fixture content
        content_sha256 = hashlib.sha256(html_content.encode("utf-8")).hexdigest()

        # Golden expected
        golden_records = []
        for p in doc["prices"]:
            rec = {
                "record_type": "price",
                "product_raw": p["product_raw"],
                "actor_level": p["actor_level"],
                "location_raw": doc["region"],
                "period_start": doc["p_start"],
                "period_end": doc["p_end"],
                "price_raw": p["price_raw"],
                "price_value": p["price_value"],
                "unit_raw": p["unit_raw"],
                "currency_raw": "MGA",
                "observed_or_imputed": "observed",
            }
            golden_records.append(rec)
        for s in doc["stocks"]:
            rec = {
                "record_type": "stock",
                "product_raw": s["product_raw"],
                "location_raw": doc["region"],
                "period_start": doc["p_start"],
                "period_end": doc["p_end"],
                "quantity_raw": s["quantity_raw"],
                "quantity_value": s["quantity_value"],
                "unit_raw": s["unit_raw"],
                "stock_status": s["stock_status"],
                "coverage_days": s["coverage_days"],
            }
            golden_records.append(rec)

        golden_file = golden_dir / f"{doc['id']}.expected.json"
        golden_payload = {
            "doc_id": doc["id"],
            "source_id": "mincc_ppn",
            "region": doc["region"],
            "published_at": f"{doc['date']}T08:00:00Z",
            "period_start": doc["p_start"],
            "period_end": doc["p_end"],
            "records_count": len(golden_records),
            "prices_count": len([r for r in golden_records if r["record_type"] == "price"]),
            "stocks_count": len([r for r in golden_records if r["record_type"] == "stock"]),
            "records": golden_records,
        }
        with open(golden_file, "w", encoding="utf-8") as f:
            json.dump(golden_payload, f, indent=2, ensure_ascii=False)

        # Create LLM Replay Fixture
        cache_key = compute_cache_key(
            provider="replay",
            model="replay-fixture",
            prompt_id="mincc_ppn_extract",
            prompt_version="v1",
            content_sha256=content_sha256,
            page=1,
        )
        llm_fixture_file = llm_dir / f"{cache_key}.json"
        llm_data = {
            "prices": [
                {
                    "product_raw": p["product_raw"],
                    "location_raw": doc["region"],
                    "actor_level": p["actor_level"],
                    "price_raw": p["price_raw"],
                    "price_value": p["price_value"],
                    "unit_raw": p["unit_raw"],
                    "currency_raw": "MGA",
                    "evidence_text": p["evidence_text"],
                }
                for p in doc["prices"]
            ],
            "stocks": [
                {
                    "product_raw": s["product_raw"],
                    "location_raw": doc["region"],
                    "quantity_raw": s["quantity_raw"],
                    "quantity_value": s["quantity_value"],
                    "unit_raw": s["unit_raw"],
                    "stock_status": s["stock_status"],
                    "coverage_days": s["coverage_days"],
                    "evidence_text": s["evidence_text"],
                }
                for s in doc["stocks"]
            ],
        }
        llm_fixture_payload = {
            "cache_key": cache_key,
            "data": llm_data,
            "usage": {
                "input_tokens": 420,
                "output_tokens": 150,
                "cost_usd": 0.00012,
            },
        }
        with open(llm_fixture_file, "w", encoding="utf-8") as f:
            json.dump(llm_fixture_payload, f, indent=2, ensure_ascii=False)
        print(f"Generated LLM replay fixture {llm_fixture_file.name} for {doc['id']}")

    print("All 10 MinCC fixtures, golden sets, and LLM replay fixtures generated successfully!")


if __name__ == "__main__":
    main()
