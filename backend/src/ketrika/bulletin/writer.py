"""Bulletin writer generating prose with strict placeholder validation (SPECS §20)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

import jinja2

from ketrika.core.logging import get_logger

logger = get_logger(__name__)

# Regular expressions
PLACEHOLDER_REGEX = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
DIGIT_REGEX = re.compile(r"\d")


def validate_prose(prose: str, allowed_placeholders: set[str]) -> tuple[bool, str]:
    """Strictly validate generated prose against SPECS §20 constraints:

    1. All referenced placeholders must exist in allowed_placeholders.
    2. Outside placeholders, prose MUST NOT contain ANY digit (regex \\d strictly forbidden).
    """
    # 1. Check placeholders
    found_placeholders = PLACEHOLDER_REGEX.findall(prose)
    for ph in found_placeholders:
        if ph not in allowed_placeholders:
            return False, f"Placeholder inconnu '{{{{{ph}}}}}' non présent dans les faits"

    # 2. Check for literal digits outside placeholders
    stripped_text = PLACEHOLDER_REGEX.sub("", prose)
    match = DIGIT_REGEX.search(stripped_text)
    if match:
        idx = match.start()
        context = stripped_text[max(0, idx - 15) : min(len(stripped_text), idx + 15)]
        return (
            False,
            f"Chiffre littéral interdit '{match.group()}' détecté dans le texte (contexte: '...{context}...'). "
            f"Tous les nombres doivent exclusivement provenir de placeholders {{{{fXXX}}}}.",
        )

    return True, ""


def render_fallback_template(
    facts: dict[str, dict[str, Any]],
    period_start: date,
    period_end: date,
) -> str:
    """Render deterministic fallback markdown template (SPECS §20.3)."""
    templates_dir = Path(__file__).resolve().parent / "templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        autoescape=False,
    )
    template = env.get_template("fallback.md.j2")

    context: dict[str, Any] = {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "sources_attribution": "{{ sources_attribution }}",
    }
    # Expose placeholder strings for jinja2 conditional evaluation in template
    for k in facts:
        context[k] = f"{{{{ {k} }}}}"

    rendered = template.render(**context)
    return rendered


def generate_bulletin_prose(
    facts: dict[str, dict[str, Any]],
    period_start: date,
    period_end: date,
    llm_client: Any = None,
) -> tuple[str, bool]:
    """Generate professional market commentary in French.

    Returns:
        tuple[str, bool]: (prose_template_with_placeholders, is_fallback)
    """
    allowed_placeholders = set(facts.keys()) | {
        "period_start",
        "period_end",
        "sources_attribution",
    }

    if llm_client is not None:
        # Build fact catalog WITHOUT numerical values (only id and label)
        facts_catalog = [{"id": k, "label": v["label"]} for k, v in facts.items()]

        system_prompt = (
            "Vous êtes un analyste de marché agricole pour Ketrika Madagascar.\n"
            "Rédigez un bulletin hebdomadaire de veille sur les denrées vivrières (riz, maïs, manioc, huile, sucre).\n"
            "RÈGLE ABSOLUE NON NÉGOCIABLE : Vous ne devez JAMAIS écrire de chiffres numériques (0-9).\n"
            "Chaque nombre, prix, pourcentage ou statistique DOIT être référencé sous forme de placeholder {{fXXX}}.\n"
            "Tout texte contenant un chiffre littéral sera automatiquement rejeté."
        )

        prompt = (
            f"Période couverte : Du {{{{period_start}}}} au {{{{period_end}}}}.\n\n"
            f"Catalogue des faits disponibles :\n{facts_catalog}\n\n"
            f"Rédigez le bulletin avec les sections : Synthèse, Filière Riz, Autres PPN, Stocks, Climat et Alertes."
        )

        for attempt in range(2):
            try:
                raw_response = llm_client.generate(prompt=prompt, system_prompt=system_prompt)
                valid, reason = validate_prose(raw_response, allowed_placeholders)
                if valid:
                    logger.info("bulletin_prose_validated_by_llm", attempt=attempt)
                    return raw_response, False
                logger.warning(
                    "bulletin_prose_validation_failed",
                    attempt=attempt,
                    reason=reason,
                )
                prompt += f"\n\nERREUR DE VALIDATION PRÉCÉDENTE : {reason}. CORRIGEZ IMMÉDIATEMENT EN SUPPRIMANT TOUT CHIFFRE."
            except Exception as exc:
                logger.error("llm_call_failed", error=str(exc))
                break

    # Repli déterministe obligatoire
    logger.info("using_deterministic_fallback_template")
    prose = render_fallback_template(facts, period_start, period_end)
    return prose, True


if __name__ == "__main__":
    from ketrika.bulletin.service import generate_weekly_bulletin
    from ketrika.core.db import get_session

    print("Generating weekly bulletin draft (SPECS §20)...")
    with get_session() as session:
        b = generate_weekly_bulletin(session)
        session.commit()
        print(f"Bulletin generated successfully! ID: {b.bulletin_id}")
        print(f"HTML artifact: {b.html_object_key}")
        print(f"PDF artifact: {b.pdf_object_key}")
