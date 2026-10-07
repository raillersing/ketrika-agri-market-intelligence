"""Script generating realistic ODR bulletin PDFs, golden datasets and LLM replay fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import weasyprint

from ketrika.extraction.llm.base import compute_cache_key

BULLETINS_DEF = [
    {
        "num": 520,
        "date_str": "20 mai 2018",
        "published_at": "2018-05-20T08:00:00Z",
        "period_str": "Mai 2018",
        "period_start": "2018-05-01",
        "period_end": "2018-05-31",
        "paddy_rows": [
            ("Alaotra Mangoro (Ambatondrazaka)", "950"),
            ("Alaotra Mangoro (Amparafaravola)", "920"),
            ("Boeny (Marovoay)", "980"),
            ("Boeny (Ambato Boeny)", "940"),
            ("Vakinankaratra (Antsirabe II)", "1050"),
            ("Vakinankaratra (Betafo)", "ND"),
            ("Itasy (Miarinarivo)", "1020"),
            ("Itasy (Soavinandriana)", "1000"),
            ("Menabe (Miandrivazo)", "960"),
            ("Menabe (Mahabo)", "950"),
            ("Sofia (Port-Bergé)", "900"),
            ("Atsinanana (Brickaville)", "980"),
        ],
        "wholesale_rows": [
            ("Analamanga (Anosibe)", "1750", "1850", "1700", "1650"),
            ("Atsinanana (Bazar Be Toamasina)", "1800", "1900", "1750", "1600"),
            ("Vakinankaratra (Antsirabe Asabotsy)", "1720", "1820", "1680", "1680"),
            ("Boeny (Mahajanga Tsaramandroso)", "1780", "1880", "1720", "1620"),
            ("Diana (Antsiranana Bazar)", "1850", "NA", "1800", "1650"),
            ("Atsimo-Andrefana (Toliara Bazar)", "1820", "1920", "1780", "1700"),
        ],
        "retail_rows": [
            ("Analamanga", "1900", "2000", "1850", "1750"),
            ("Atsinanana", "1950", "2050", "1900", "1700"),
            ("Vakinankaratra", "1880", "1980", "1820", "1780"),
            ("Boeny", "1920", "2020", "1880", "1720"),
            ("Diana", "2000", "2100", "1950", "1750"),
            ("Atsimo-Andrefana", "1980", "2080", "ND", "1800"),
        ],
    },
    {
        "num": 710,
        "date_str": "25 octobre 2021",
        "published_at": "2021-10-25T08:00:00Z",
        "period_str": "Octobre 2021",
        "period_start": "2021-10-01",
        "period_end": "2021-10-31",
        "paddy_rows": [
            ("Alaotra Mangoro (Ambatondrazaka)", "1300"),
            ("Alaotra Mangoro (Amparafaravola)", "1280"),
            ("Boeny (Marovoay)", "1350"),
            ("Boeny (Ambato Boeny)", "1320"),
            ("Vakinankaratra (Antsirabe II)", "1400"),
            ("Vakinankaratra (Betafo)", "1380"),
            ("Itasy (Miarinarivo)", "1370"),
            ("Itasy (Soavinandriana)", "ND"),
            ("Menabe (Miandrivazo)", "1310"),
            ("Menabe (Mahabo)", "1300"),
            ("Sofia (Port-Bergé)", "1260"),
            ("Atsinanana (Brickaville)", "1340"),
        ],
        "wholesale_rows": [
            ("Analamanga (Anosibe)", "2350", "2500", "2300", "2200"),
            ("Atsinanana (Bazar Be Toamasina)", "2400", "2550", "2350", "2150"),
            ("Vakinankaratra (Antsirabe Asabotsy)", "2320", "2480", "2280", "2250"),
            ("Boeny (Mahajanga Tsaramandroso)", "2380", "NA", "2320", "2180"),
            ("Diana (Antsiranana Bazar)", "2450", "2600", "2400", "2220"),
            ("Atsimo-Andrefana (Toliara Bazar)", "2420", "2580", "2380", "2280"),
        ],
        "retail_rows": [
            ("Analamanga", "2500", "2650", "2450", "2350"),
            ("Atsinanana", "2550", "2700", "2500", "2300"),
            ("Vakinankaratra", "2480", "2620", "2420", "2400"),
            ("Boeny", "2520", "2680", "ND", "2320"),
            ("Diana", "2600", "2750", "2550", "2380"),
            ("Atsimo-Andrefana", "2580", "2720", "2520", "2420"),
        ],
    },
    {
        "num": 850,
        "date_str": "22 janvier 2024",
        "published_at": "2024-01-22T08:00:00Z",
        "period_str": "Janvier 2024",
        "period_start": "2024-01-01",
        "period_end": "2024-01-31",
        "paddy_rows": [
            ("Alaotra Mangoro (Ambatondrazaka)", "1650"),
            ("Alaotra Mangoro (Amparafaravola)", "1620"),
            ("Boeny (Marovoay)", "1700"),
            ("Boeny (Ambato Boeny)", "1680"),
            ("Vakinankaratra (Antsirabe II)", "1750"),
            ("Vakinankaratra (Betafo)", "1720"),
            ("Itasy (Miarinarivo)", "1710"),
            ("Itasy (Soavinandriana)", "1690"),
            ("Menabe (Miandrivazo)", "1640"),
            ("Menabe (Mahabo)", "NA"),
            ("Sofia (Port-Bergé)", "1600"),
            ("Atsinanana (Brickaville)", "1670"),
        ],
        "wholesale_rows": [
            ("Analamanga (Anosibe)", "3150", "3350", "3100", "2950"),
            ("Atsinanana (Bazar Be Toamasina)", "3200", "3400", "3150", "2900"),
            ("Vakinankaratra (Antsirabe Asabotsy)", "3100", "3300", "3050", "3000"),
            ("Boeny (Mahajanga Tsaramandroso)", "3180", "3380", "3120", "2920"),
            ("Diana (Antsiranana Bazar)", "3250", "3450", "3200", "2980"),
            ("Atsimo-Andrefana (Toliara Bazar)", "3220", "ND", "3180", "3020"),
        ],
        "retail_rows": [
            ("Analamanga", "3300", "3500", "3250", "3100"),
            ("Atsinanana", "3350", "3550", "3300", "3050"),
            ("Vakinankaratra", "3280", "3480", "3220", "3150"),
            ("Boeny", "3320", "3520", "3280", "3080"),
            ("Diana", "3400", "3600", "3350", "3120"),
            ("Atsimo-Andrefana", "3380", "3580", "3320", "ND"),
        ],
    },
]

COMMODITIES_WH = [
    ("Riz blanc local (Vary gasy)", "Vary gasy"),
    ("Riz blanc local (Makalioka)", "Makalioka"),
    ("Riz blanc local (Tsipala)", "Tsipala"),
    ("Riz importé (25% brisures)", "25% brisures"),
]


def build_bulletin_html(b: dict) -> str:
    """Build standardized HTML representation of an ODR bulletin."""
    paddy_tr = "\n".join(
        f"<tr><td>{loc}</td><td>{pr}</td></tr>" for loc, pr in b["paddy_rows"]
    )

    wh_tr = "\n".join(
        f"<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td><td>{row[3]}</td><td>{row[4]}</td></tr>"
        for row in b["wholesale_rows"]
    )

    ret_tr = "\n".join(
        f"<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td><td>{row[3]}</td><td>{row[4]}</td></tr>"
        for row in b["retail_rows"]
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: Helvetica, Arial, sans-serif; font-size: 9pt; margin: 15mm; color: #222; }}
h1 {{ font-size: 14pt; margin-bottom: 2px; text-transform: uppercase; color: #1a472a; text-align: center; }}
.subtitle {{ font-size: 10pt; text-align: center; margin-bottom: 15px; font-weight: bold; }}
.meta-box {{ background-color: #f4f6f4; border: 1px solid #c2d6c7; padding: 6px 12px; margin-bottom: 15px; font-size: 8.5pt; }}
h2 {{ font-size: 10.5pt; margin-top: 15px; margin-bottom: 6px; color: #1a472a; border-bottom: 1.5px solid #1a472a; padding-bottom: 2px; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 12px; }}
th, td {{ border: 1px solid #666; padding: 4px 6px; text-align: left; }}
th {{ background-color: #e2ede5; font-size: 8.5pt; font-weight: bold; }}
td {{ font-size: 8.5pt; }}
td:nth-child(n+2) {{ text-align: right; }}
.note {{ font-size: 7.5pt; font-style: italic; color: #555; margin-top: -8px; margin-bottom: 12px; }}
</style>
</head>
<body>
<h1>Ministère de l'Agriculture et de l'Élevage — Observatoire du Riz</h1>
<div class="subtitle">BULLETIN N° {b['num']} — PÉRIODE : {b['period_str']}</div>
<div class="meta-box">
  Date de parution : {b['date_str']} | Unité de prix : Ariary par kilogramme (Ar/kg) | ND : Non disponible, NA : Non applicable.
</div>

<h2>Tableau 1 : Prix au producteur du paddy</h2>
<table>
<thead>
<tr>
  <th style="width: 70%;">Région / District de collecte</th>
  <th style="width: 30%;">Prix moyen (Ar/kg)</th>
</tr>
</thead>
<tbody>
{paddy_tr}
</tbody>
</table>
<div class="note">Source : Enquêtes directes ODR auprès des producteurs et collecteurs primaires.</div>

<h2>Tableau 2 : Prix de gros du riz blanc</h2>
<table>
<thead>
<tr>
  <th>Région / Marché de gros</th>
  <th>Riz blanc local (Vary gasy)</th>
  <th>Riz blanc local (Makalioka)</th>
  <th>Riz blanc local (Tsipala)</th>
  <th>Riz importé (25% brisures)</th>
</tr>
</thead>
<tbody>
{wh_tr}
</tbody>
</table>
<div class="note">Source : Relevés grossistes et demi-grossistes sur les marchés de référence.</div>

<h2>Tableau 3 : Prix au détail du riz blanc</h2>
<table>
<thead>
<tr>
  <th>Région / Zone de consommation</th>
  <th>Riz blanc local (Vary gasy)</th>
  <th>Riz blanc local (Makalioka)</th>
  <th>Riz blanc local (Tsipala)</th>
  <th>Riz importé (25% brisures)</th>
</tr>
</thead>
<tbody>
{ret_tr}
</tbody>
</table>
<div class="note">Source : Relevés détaillants réguliers marchés urbains et ruraux ODR.</div>

</body>
</html>
"""


def extract_expected_records(b: dict) -> list[dict]:
    """Build the exhaustive expected records list for a bulletin."""
    records: list[dict] = []

    # Table 1: Producer paddy
    for loc, pr_raw in b["paddy_rows"]:
        is_missing = pr_raw in ("ND", "NA")
        records.append({
            "product_raw": "Riz paddy",
            "variety": None,
            "actor_level": "producer",
            "location_raw": loc,
            "price_raw": pr_raw,
            "price_value": None if is_missing else float(pr_raw),
            "unit_raw": "kg",
            "currency_raw": "MGA",
            "missing_code": pr_raw if is_missing else None,
            "period_start": b["period_start"],
            "period_end": b["period_end"],
        })

    # Table 2: Wholesale
    for row in b["wholesale_rows"]:
        loc = row[0]
        for col_idx, (p_raw, v_name) in enumerate(COMMODITIES_WH, start=1):
            val_raw = row[col_idx]
            is_missing = val_raw in ("ND", "NA")
            records.append({
                "product_raw": p_raw,
                "variety": v_name,
                "actor_level": "wholesale",
                "location_raw": loc,
                "price_raw": val_raw,
                "price_value": None if is_missing else float(val_raw),
                "unit_raw": "kg",
                "currency_raw": "MGA",
                "missing_code": val_raw if is_missing else None,
                "period_start": b["period_start"],
                "period_end": b["period_end"],
            })

    # Table 3: Retail
    for row in b["retail_rows"]:
        loc = row[0]
        for col_idx, (p_raw, v_name) in enumerate(COMMODITIES_WH, start=1):
            val_raw = row[col_idx]
            is_missing = val_raw in ("ND", "NA")
            records.append({
                "product_raw": p_raw,
                "variety": v_name,
                "actor_level": "retail",
                "location_raw": loc,
                "price_raw": val_raw,
                "price_value": None if is_missing else float(val_raw),
                "unit_raw": "kg",
                "currency_raw": "MGA",
                "missing_code": val_raw if is_missing else None,
                "period_start": b["period_start"],
                "period_end": b["period_end"],
            })

    return records


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    fixtures_dir = root / "tests" / "fixtures" / "miasa_odr"
    golden_dir = root / "tests" / "golden" / "miasa_odr"
    llm_dir = root / "tests" / "fixtures" / "llm"

    fixtures_dir.mkdir(parents=True, exist_ok=True)
    golden_dir.mkdir(parents=True, exist_ok=True)
    llm_dir.mkdir(parents=True, exist_ok=True)

    print("Generating ODR bulletins fixtures & goldens...")

    for b in BULLETINS_DEF:
        num = b["num"]
        html_content = build_bulletin_html(b)
        pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
        content_sha = hashlib.sha256(pdf_bytes).hexdigest()

        pdf_path = fixtures_dir / f"odr_bulletin_{num}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        expected_records = extract_expected_records(b)
        golden_data = {
            "metadata": {
                "source_id": "miasa_odr",
                "document_id": f"odr_bulletin_{num}",
                "bulletin_number": num,
                "period_start": b["period_start"],
                "period_end": b["period_end"],
                "published_at": b["published_at"],
                "content_sha256": content_sha,
                "annotator": "agent",
                "human_reviewed": False,
                "annotated_at": "2026-10-07T03:50:00Z",
                "total_records": len(expected_records),
                "producer_records": len(b["paddy_rows"]),
                "wholesale_records": len(b["wholesale_rows"]) * 4,
                "retail_records": len(b["retail_rows"]) * 4,
            },
            "records": expected_records,
        }

        golden_path = golden_dir / f"odr_bulletin_{num}.expected.json"
        with open(golden_path, "w", encoding="utf-8") as f:
            json.dump(golden_data, f, indent=2, ensure_ascii=False)

        # Page 1: 44 items (12 paddy + 24 wholesale + 8 retail)
        # Page 2: 16 items (16 retail)
        page1_records = expected_records[:44]
        page2_records = expected_records[44:]

        for p_num, p_recs in [(1, page1_records), (2, page2_records)]:
            llm_items = []
            for r in p_recs:
                llm_items.append({
                    "product_raw": r["product_raw"],
                    "variety": r["variety"],
                    "actor_level": r["actor_level"],
                    "location_raw": r["location_raw"],
                    "price_raw": r["price_raw"],
                    "price_value": r["price_value"],
                    "missing_code": r["missing_code"],
                    "evidence_text": f"{r['location_raw']} {r['price_raw']}",
                })

            cache_key = compute_cache_key(
                provider="replay",
                model="replay-fixture",
                prompt_id="miasa_odr_extract",
                prompt_version="v1",
                content_sha256=content_sha,
                page=p_num,
            )

            llm_fixture_path = llm_dir / f"{cache_key}.json"
            with open(llm_fixture_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "data": {"items": llm_items},
                        "usage": {"input_tokens": 500, "output_tokens": 250, "cost_usd": 0.001},
                    },
                    f,
                    indent=2,
                )

        print(
            f"Generated Bulletin {num}: {len(expected_records)} records, PDF {pdf_path.name} (sha: {content_sha[:8]}) with 2 LLM page fixtures."
        )


if __name__ == "__main__":
    main()
