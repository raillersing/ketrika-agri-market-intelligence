"""Copilot response writer with strict anti-hallucination placeholder substitutions (SPECS §21, AGENTS §4.7)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ketrika.copilot.executor import QueryResult


@dataclass
class CellReference:
    """A referenced data cell from query results."""

    placeholder: str
    column: str
    row_index: int
    raw_value: Any
    display_value: str


def format_cell_value(col_name: str, val: Any) -> str:
    """Format cell value for display according to market intelligence conventions."""
    if val is None:
        return "N/D"

    # Percentage changes
    if "chg_" in col_name or "pct" in col_name or "share" in col_name:
        try:
            num = float(val)
            pct = num * 100 if abs(num) <= 1.0 and "pct" not in col_name else num
            sign = "+" if pct > 0 else ""
            return f"{sign}{pct:.1f}%".replace(".", ",")
        except (ValueError, TypeError):
            pass

    # Prices (Ariary)
    if (
        "price" in col_name
        or "mga" in col_name
        or col_name in ("p10", "p50", "p90", "med_12", "mad_12")
    ):
        try:
            num = float(val)
            # French space formatting (e.g. 2 850)
            formatted = f"{num:,.0f}".replace(",", " ")
            return f"{formatted} Ar"
        except (ValueError, TypeError):
            pass

    # Weights (tons)
    if "tons" in col_name:
        try:
            num = float(val)
            formatted = f"{num:,.1f}".replace(",", " ").replace(".", ",")
            return f"{formatted} t"
        except (ValueError, TypeError):
            pass

    # Z-scores
    if "z_score" in col_name:
        try:
            num = float(val)
            return f"{num:+.2f}".replace(".", ",")
        except (ValueError, TypeError):
            pass

    # Dates
    if hasattr(val, "strftime"):
        return str(val.strftime("%Y-%m-%d"))

    return str(val)


def build_cell_placeholders(
    query_result: QueryResult,
) -> tuple[dict[str, CellReference], list[dict[str, str]]]:
    """Map all query result cells into indexed tokens {{c_R_C}}."""
    cell_map: dict[str, CellReference] = {}
    rows_preview: list[dict[str, str]] = []

    for r_idx, row in enumerate(query_result.rows[:50]):  # Cap preview at 50 rows
        row_display: dict[str, str] = {}
        for c_idx, col in enumerate(query_result.columns):
            raw_val = row.get(col)
            display = format_cell_value(col, raw_val)
            placeholder = f"{{{{c_{r_idx}_{c_idx}}}}}"
            cell_map[f"c_{r_idx}_{c_idx}"] = CellReference(
                placeholder=placeholder,
                column=col,
                row_index=r_idx,
                raw_value=raw_val,
                display_value=display,
            )
            row_display[col] = display
        rows_preview.append(row_display)

    return cell_map, rows_preview


def validate_anti_hallucination_prose(text_with_placeholders: str) -> bool:
    """Verify that NO free digit appears in the prose outside of {{...}} tags."""
    # Temporarily strip all valid placeholder tags {{...}}
    stripped = re.sub(r"\{\{[^{}]+\}\}", "", text_with_placeholders)
    # Check if any digit exists in the remaining text
    return bool(not re.search(r"\d", stripped))


def render_deterministic_fallback(query_result: QueryResult) -> str:
    """Generate deterministic markdown analysis when LLM text fails or is absent."""
    if not query_result.rows:
        return "Aucun résultat trouvé pour cette requête dans la base analytique."

    lines: list[str] = ["Voici les données observées issues du marché :", ""]
    # Generate markdown table for up to 10 rows
    cols = query_result.columns
    header = "| " + " | ".join(cols) + " |"
    separator = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines.extend([header, separator])

    for row in query_result.rows[:10]:
        row_vals = [format_cell_value(c, row.get(c)) for c in cols]
        lines.append("| " + " | ".join(row_vals) + " |")

    if query_result.row_count > 10:
        lines.append(
            f"\n*(Affichage de 10 lignes sur un total de {query_result.row_count} enregistrements)*"
        )

    return "\n".join(lines)


def assemble_final_response(
    prose_with_placeholders: str,
    cell_map: dict[str, CellReference],
    query_result: QueryResult,
) -> str:
    """Validate and substitute placeholders into the final user-facing Markdown text."""
    # Check anti-hallucination compliance
    if not validate_anti_hallucination_prose(prose_with_placeholders):
        # Fall back to guaranteed deterministic template without hallucination
        return render_deterministic_fallback(query_result)

    # Perform placeholder substitutions
    final_text = prose_with_placeholders
    for key, cell in cell_map.items():
        token = f"{{{{{key}}}}}"
        if token in final_text:
            final_text = final_text.replace(token, cell.display_value)

    # Ensure no leftover un-substituted placeholder
    final_text = re.sub(r"\{\{c_\d+_\d+\}\}", "N/D", final_text)
    return final_text
