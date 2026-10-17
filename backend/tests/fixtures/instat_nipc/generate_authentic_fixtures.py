"""Generate SYNTHETIC Excel parser fixtures, never official INSTAT evidence.

The historical filename is retained for compatibility. Generated values and
revisions cannot qualify source authenticity or market accuracy.
"""

from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.worksheet import Worksheet

FIXTURES_DIR = Path(__file__).resolve().parent


def build_historic_workbook(dest_path: Path) -> None:
    """Build a synthetic multi-sheet NIPC workbook (Base 2016 and Base 2011)."""
    wb = openpyxl.Workbook()

    # Sheet 1: Note Méthodologique (metadata without tabular cpi data)
    ws_notes = wb.active
    assert isinstance(ws_notes, Worksheet)
    ws_notes.title = "Avertissement et Methodes"
    ws_notes.views.sheetView[0].showGridLines = True
    ws_notes["A1"] = "INSTITUT NATIONAL DE LA STATISTIQUE (INSTAT) MADAGASCAR"
    ws_notes["A1"].font = Font(bold=True, size=14)
    ws_notes["A2"] = "Direction de la Statistique des Ménages - Service des Prix à la Consommation"
    ws_notes["A3"] = "Nouveau Système de l'Indice des Prix à la Consommation (NIPC)"
    ws_notes["A4"] = "Base de référence : Année 2016 = 100 (depuis janvier 2016)"
    ws_notes["A5"] = (
        "FIXTURE SYNTHETIQUE : aucune licence institutionnelle ni acquisition officielle attestée."
    )
    ws_notes["A6"] = (
        "Note sur les changements de base : L'ancienne base 2011=100 ne doit pas être raccordée sans coefficient officiel."
    )

    # Sheet 2: Indices Nationaux Base 2016 (2016-2023)
    ws_2016 = wb.create_sheet(title="Indices Nationaux (Base 2016)")
    ws_2016["A1"] = "TABLEAU 1: EVOLUTION MENSUELLE DU NIPC NATIONAL (BASE 2016 = 100)"
    ws_2016["A1"].font = Font(bold=True, size=12)
    ws_2016["A2"] = "Source: Enquêtes mensuelles de prix - INSTAT Madagascar (Moyenne Nationale)"

    # Row 3: Merged header categories
    # Merge B3:C3 for "FONCTION 01 : PRODUITS ALIMENTAIRES"
    ws_2016.merge_cells("C3:D3")
    ws_2016["C3"] = "FONCTION 01 : ALIMENTATION ET BOISSONS"
    ws_2016["C3"].alignment = Alignment(horizontal="center")
    ws_2016["C3"].font = Font(bold=True)

    ws_2016.merge_cells("E3:F3")
    ws_2016["E3"] = "SOUS-GROUPES VIVRIERS STRATEGIQUES"
    ws_2016["E3"].alignment = Alignment(horizontal="center")
    ws_2016["E3"].font = Font(bold=True)

    # Row 4: Column labels
    headers = [
        "Période",
        "Indice Général (Ensemble)",
        "Produits alimentaires et boissons non alcoolisées",
        "Détail Alimentation",
        "Riz de consommation",
        "Pain et céréales",
    ]
    for col_idx, h in enumerate(headers, start=1):
        cell = ws_2016.cell(row=4, column=col_idx, value=h)
        cell.font = Font(bold=True)

    # 96 months: 2016-01 to 2023-12
    row_cursor = 5
    base_ensemble = 100.0
    base_alim = 100.0
    base_riz = 100.0
    base_pain = 100.0

    for year in range(2016, 2024):
        for month in range(1, 13):
            month_idx = (year - 2016) * 12 + month - 1
            period_str = f"{year}-{month:02d}"

            # Trend with slight seasonal inflation
            val_ens = round(base_ensemble + month_idx * 0.65 + ((month % 3) * 0.2), 2)
            val_alim = round(base_alim + month_idx * 0.76 + ((month % 4) * 0.3), 2)
            val_riz = round(base_riz + month_idx * 0.72 + ((month % 2) * 0.4), 2)

            # Introduce some ND cells for the earliest 3 months of pain & cereales
            if month_idx < 3:
                val_pain = "ND"
            else:
                val_pain = round(base_pain + month_idx * 0.68, 2)

            ws_2016.cell(row=row_cursor, column=1, value=period_str)
            ws_2016.cell(row=row_cursor, column=2, value=val_ens)
            ws_2016.cell(row=row_cursor, column=3, value=val_alim)
            ws_2016.cell(row=row_cursor, column=4, value=round(val_alim * 0.99, 2))
            ws_2016.cell(row=row_cursor, column=5, value=val_riz)
            ws_2016.cell(row=row_cursor, column=6, value=val_pain)
            row_cursor += 1

    # Sheet 3: Indices Historiques Base 2011 (2011-2015)
    ws_2011 = wb.create_sheet(title="Indices Base 2011")
    ws_2011["A1"] = "SERIE HISTORIQUE DU NIPC (BASE 2011 = 100)"
    ws_2011["A1"].font = Font(bold=True, size=12)
    ws_2011["A2"] = "Base antérieure 2011 = 100 (Non raccordée à la base 2016)"

    ws_2011.cell(row=4, column=1, value="Mois").font = Font(bold=True)
    ws_2011.cell(row=4, column=2, value="Indice Général").font = Font(bold=True)
    ws_2011.cell(row=4, column=3, value="Produits Alimentaires").font = Font(bold=True)
    ws_2011.cell(row=4, column=4, value="Riz").font = Font(bold=True)

    row_cursor = 5
    for year in range(2011, 2016):
        for month in range(1, 13):
            month_idx = (year - 2011) * 12 + month - 1
            period_str = f"{year}M{month:02d}"
            v_ens = round(100.0 + month_idx * 0.62, 2)
            v_alim = round(100.0 + month_idx * 0.70, 2)
            v_riz = round(100.0 + month_idx * 0.65, 2)
            ws_2011.cell(row=row_cursor, column=1, value=period_str)
            ws_2011.cell(row=row_cursor, column=2, value=v_ens)
            ws_2011.cell(row=row_cursor, column=3, value=v_alim)
            ws_2011.cell(row=row_cursor, column=4, value=v_riz)
            row_cursor += 1

    wb.save(dest_path)
    print(f"Created {dest_path}")


def build_recent_workbook(dest_path: Path) -> None:
    """Build authentic monthly NIPC workbook with French date names and revisions."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "NIPC 2024 Mensuel"

    ws["A1"] = "REPUBLIQUE DE MADAGASCAR"
    ws["A2"] = "INSTITUT NATIONAL DE LA STATISTIQUE"
    ws["A3"] = "BULLETIN MENSUEL DU NIPC - EXERCICE 2024"
    ws["A4"] = "Base 2016 = 100 - Moyenne Nationale"
    ws["A5"] = "Date de publication : 15 Octobre 2024"

    # Merge header for series group
    ws.merge_cells("C7:D7")
    ws["C7"] = "ALIMENTATION ET SOUS-RUBRIQUES"
    ws["C7"].font = Font(bold=True)

    ws.cell(row=8, column=1, value="Mois d'observation").font = Font(bold=True)
    ws.cell(row=8, column=2, value="Indice d'Ensemble").font = Font(bold=True)
    ws.cell(row=8, column=3, value="Produits alimentaires").font = Font(bold=True)
    ws.cell(row=8, column=4, value="Riz de consommation").font = Font(bold=True)

    months_data = [
        ("Janvier 2024", 166.15, 175.80, 172.90),
        ("Février 2024", 167.30, 177.20, 174.10),
        ("Mars 2024", 168.05, 178.15, 175.05),
        ("Avril 2024", 168.90, 179.30, 176.20),
        ("Mai 2024", 169.55, 180.25, 177.15),
        ("Juin 2024", 170.20, 181.00, 177.80),
        ("Juillet 2024", 171.05, 182.10, 178.95),
        ("Août 2024", 171.85, 183.05, 179.70),
        ("Septembre 2024", 172.50, 184.20, 180.50),
    ]

    for idx, (m_label, v_ens, v_alim, v_riz) in enumerate(months_data, start=9):
        ws.cell(row=idx, column=1, value=m_label)
        ws.cell(row=idx, column=2, value=v_ens)
        ws.cell(row=idx, column=3, value=v_alim)
        ws.cell(row=idx, column=4, value=v_riz)

    wb.save(dest_path)
    print(f"Created {dest_path}")


if __name__ == "__main__":
    build_historic_workbook(FIXTURES_DIR / "nipc_historique_2016_2023.xlsx")
    build_recent_workbook(FIXTURES_DIR / "nipc_recent_2024.xlsx")
