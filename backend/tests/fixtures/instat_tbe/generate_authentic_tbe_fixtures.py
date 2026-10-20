"""Generate SYNTHETIC multi-edition Excel fixtures, not official INSTAT data.

The historical filename is retained; generated values and revisions only test
software and cannot prove source authenticity or real-world performance.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

FIXTURES_DIR = Path(__file__).resolve().parent


def build_tbe_workbook(
    dest_path: Path,
    edition_num: int,
    publication_date_str: str,
    end_month: int,  # 3 for edition 62 (up to 2026-03), 6 for edition 63 (up to 2026-06)
    revised: bool = False,
) -> None:
    """Build a synthetic multi-sheet workbook for parser regression tests."""
    wb = openpyxl.Workbook()

    # Sheet 1: Sommaire & Sources
    ws_notes = wb.active
    assert isinstance(ws_notes, Worksheet)
    ws_notes.title = "Sommaire & Sources"
    ws_notes.views.sheetView[0].showGridLines = True
    ws_notes["A1"] = "INSTITUT NATIONAL DE LA STATISTIQUE (INSTAT) MADAGASCAR"
    ws_notes["A1"].font = Font(bold=True, size=14)
    ws_notes["A2"] = f"TABLEAU DE BORD DE L'ECONOMIE (TBE) - EDITION N°{edition_num}"
    ws_notes["A2"].font = Font(bold=True, size=12)
    ws_notes["A3"] = f"Date de publication : {publication_date_str}"
    ws_notes["A4"] = "Direction de la Statistique Economique - Service de la Conjoncture"
    ws_notes["A5"] = (
        "FIXTURE SYNTHETIQUE : aucune acquisition officielle ni données de terrain attestées."
    )
    ws_notes["A6"] = (
        "Sources primaires partenaires : Direction Générale des Douanes (DGD), Banky Foiben'i Madagasikara (BFM), JIRAMA."
    )

    # Sheet 2: Secteur Réel
    ws_reel = wb.create_sheet(title="Secteur Réel")
    ws_reel["A1"] = f"TABLEAU 1: INDICATEURS D'ACTIVITE ET DE PRODUCTION (TBE N°{edition_num})"
    ws_reel["A1"].font = Font(bold=True, size=12)
    ws_reel["A2"] = "Sources: INSTAT, JIRAMA, Opérateurs de branche"

    headers_reel = [
        "Période",
        "Indice de la Production Industrielle (Base 2015=100)",
        "Consommation Electricite Industrielle (MWh)",
        "Consommation Ciment (Tonnes)",
    ]
    for col_idx, h in enumerate(headers_reel, start=1):
        cell = ws_reel.cell(row=4, column=col_idx, value=h)
        cell.font = Font(bold=True)

    # Monthly data: 2025-01 to 2026-03 or 2026-06
    row_cursor = 5
    for year in (2025, 2026):
        m_max = 12 if year == 2025 else end_month
        for m in range(1, m_max + 1):
            period_str = f"{year}-{m:02d}"
            # Values with realistic trends and minor revisions
            ipi_val = round(105.0 + (year - 2025) * 4.0 + m * 0.4, 2)
            elec_val = round(18500.0 + (year - 2025) * 500.0 + m * 120.0, 1)
            ciment_val = round(42000.0 + (year - 2025) * 800.0 + m * 250.0, 1)

            if revised and year == 2026 and m <= 3:
                # Slight revision in edition 63
                ipi_val = round(ipi_val + 0.3, 2)

            ws_reel.cell(row=row_cursor, column=1, value=period_str)
            ws_reel.cell(row=row_cursor, column=2, value=ipi_val)
            ws_reel.cell(row=row_cursor, column=3, value=elec_val)
            ws_reel.cell(row=row_cursor, column=4, value=ciment_val)
            row_cursor += 1

    # Add quarterly real GDP at bottom of real sector sheet (DO NOT MERGE AS MONTHS!)
    ws_reel.cell(
        row=row_cursor + 1, column=1, value="TABLEAU 1-BIS: PIB REEL TRIMESTRIEL (MILLIARDS MGA)"
    ).font = Font(bold=True)
    ws_reel.cell(row=row_cursor + 2, column=1, value="Période (Trimestre)").font = Font(bold=True)
    ws_reel.cell(row=row_cursor + 2, column=2, value="PIB Réel (Milliards MGA)").font = Font(
        bold=True
    )

    q_row = row_cursor + 3
    quarters = [
        ("2025-T1", 9450.0),
        ("2025-T2", 9820.0),
        ("2025-T3", 10150.0),
        ("2025-T4", 10400.0),
        ("2026-T1", 9750.0),
    ]
    if end_month >= 6:
        quarters.append(("2026-T2", 10120.0))

    for q_code, q_val in quarters:
        ws_reel.cell(row=q_row, column=1, value=q_code)
        ws_reel.cell(row=q_row, column=2, value=q_val)
        q_row += 1

    # Sheet 3: Commerce Extérieur
    ws_trade = wb.create_sheet(title="Commerce Extérieur")
    ws_trade["A1"] = f"TABLEAU 2: STATISTIQUES DU COMMERCE EXTERIEUR (TBE N°{edition_num})"
    ws_trade["A1"].font = Font(bold=True, size=12)
    ws_trade["A2"] = "Source primaire: Direction Générale des Douanes (DGD)"

    headers_trade = [
        "Période",
        "Importations Riz (Tonnes)",
        "Importations CAF Totales (Millions MGA)",
        "Exportations FOB Totales (Millions MGA)",
    ]
    for col_idx, h in enumerate(headers_trade, start=1):
        cell = ws_trade.cell(row=4, column=col_idx, value=h)
        cell.font = Font(bold=True)

    row_cursor = 5
    for year in (2025, 2026):
        m_max = 12 if year == 2025 else end_month
        for m in range(1, m_max + 1):
            period_str = f"{year}-{m:02d}"
            rice_tonnes = round(35000.0 + (m % 3) * 5000.0 + (year - 2025) * 2000.0, 1)
            imports_cif = round(1200000.0 + (year - 2025) * 50000.0 + m * 8000.0, 1)
            exports_fob = round(850000.0 + (year - 2025) * 40000.0 + m * 6000.0, 1)

            ws_trade.cell(row=row_cursor, column=1, value=period_str)
            ws_trade.cell(row=row_cursor, column=2, value=rice_tonnes)
            ws_trade.cell(row=row_cursor, column=3, value=imports_cif)
            ws_trade.cell(row=row_cursor, column=4, value=exports_fob)
            row_cursor += 1

    # Sheet 4: Secteur Monétaire
    ws_mon = wb.create_sheet(title="Secteur Monétaire")
    ws_mon["A1"] = f"TABLEAU 3: SITUATION MONETAIRE ET CHANGE (TBE N°{edition_num})"
    ws_mon["A1"].font = Font(bold=True, size=12)
    ws_mon["A2"] = "Source primaire: Banky Foiben'i Madagasikara (BFM)"

    headers_mon = [
        "Période",
        "Masse Monétaire M3 (Milliards MGA)",
        "Cours de Change USD Moyen (MGA)",
    ]
    for col_idx, h in enumerate(headers_mon, start=1):
        cell = ws_mon.cell(row=4, column=col_idx, value=h)
        cell.font = Font(bold=True)

    row_cursor = 5
    for year in (2025, 2026):
        m_max = 12 if year == 2025 else end_month
        for m in range(1, m_max + 1):
            period_str = f"{year}-{m:02d}"
            m3_val = round(18200.0 + (year - 2025) * 1200.0 + m * 80.0, 1)
            usd_rate = round(4550.0 + (year - 2025) * 120.0 + m * 15.0, 2)

            ws_mon.cell(row=row_cursor, column=1, value=period_str)
            ws_mon.cell(row=row_cursor, column=2, value=m3_val)
            ws_mon.cell(row=row_cursor, column=3, value=usd_rate)
            row_cursor += 1

    # Sheet 5: Prix Consommation (Réédition NIPC)
    ws_cpi = wb.create_sheet(title="Prix Consommation")
    ws_cpi["A1"] = f"TABLEAU 4: INDICE DES PRIX A LA CONSOMMATION REEDITE (TBE N°{edition_num})"
    ws_cpi["A1"].font = Font(bold=True, size=12)
    ws_cpi["A2"] = "Source primaire: INSTAT Madagascar - Service des Prix (NIPC Base 2016)"

    headers_cpi = [
        "Période",
        "NIPC Indice Alimentaire Réédité (Base 2016)",
    ]
    for col_idx, h in enumerate(headers_cpi, start=1):
        cell = ws_cpi.cell(row=4, column=col_idx, value=h)
        cell.font = Font(bold=True)

    row_cursor = 5
    for year in (2025, 2026):
        m_max = 12 if year == 2025 else end_month
        for m in range(1, m_max + 1):
            period_str = f"{year}-{m:02d}"
            cpi_val = round(172.0 + (year - 2025) * 12.0 + m * 0.9, 2)
            ws_cpi.cell(row=row_cursor, column=1, value=period_str)
            ws_cpi.cell(row=row_cursor, column=2, value=cpi_val)
            row_cursor += 1

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(dest_path)


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    f62 = FIXTURES_DIR / "tbe_edition_62_mai_2026.xlsx"
    f63 = FIXTURES_DIR / "tbe_edition_63_aout_2026.xlsx"

    build_tbe_workbook(
        dest_path=f62,
        edition_num=62,
        publication_date_str="2026-05-20",
        end_month=3,
        revised=False,
    )
    print(f"Generated {f62}")

    build_tbe_workbook(
        dest_path=f63,
        edition_num=63,
        publication_date_str="2026-08-25",
        end_month=6,
        revised=True,
    )
    print(f"Generated {f63}")


if __name__ == "__main__":
    main()
