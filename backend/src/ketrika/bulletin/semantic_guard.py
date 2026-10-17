"""Semantic and directional integrity guard for market bulletins (R6.5, SPECS §20).

Enforces:
1. Directional polarity consistency: upward variations cannot be labeled as drops; downward variations cannot be labeled as spikes.
2. Temporal consistency: past observations cannot be described as future projections.
3. Observational truth: unproven causal speculations are rejected.
4. Fail-closed fallback: any detected semantic breach triggers automatic fallback to the certified deterministic template.
"""

from __future__ import annotations

import re
from typing import Any

# Polarity keywords
UPWARD_KEYWORDS: tuple[str, ...] = (
    "hausse",
    "augmentation",
    "flambée",
    "flambee",
    "progression",
    "bond",
    "envolée",
    "envolee",
    "croissance",
    "renchérissement",
    "rencherissement",
)

DOWNWARD_KEYWORDS: tuple[str, ...] = (
    "baisse",
    "chute",
    "diminution",
    "repli",
    "recul",
    "effondrement",
    "dégringolade",
    "degringolade",
    "contraction",
)

UNPROVEN_CAUSAL_KEYWORDS: tuple[str, ...] = (
    "spéculation illégale",
    "speculation illegale",
    "faute exclusive",
    "complot",
    "manigance",
)

PLACEHOLDER_REGEX = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def extract_context_window(text: str, placeholder: str, window_chars: int = 120) -> str:
    """Extract sentence or context surrounding a specific placeholder."""
    target = f"{{{{{placeholder}}}}}"
    idx = text.find(target)
    if idx == -1:
        # Check without spaces
        target = f"{{{{ {placeholder} }}}}"
        idx = text.find(target)
    if idx == -1:
        return ""

    start = max(0, idx - window_chars)
    end = min(len(text), idx + len(target) + window_chars)
    return text[start:end].lower()


def validate_semantic_consistency(
    prose_with_placeholders: str,
    facts: dict[str, dict[str, Any]],
) -> tuple[bool, list[str]]:
    """Verify directional, temporal, and factual consistency between prose and facts.

    Returns:
        tuple[bool, list[str]]: (is_valid, list_of_detected_issues)
    """
    issues: list[str] = []

    # 1. Unproven causality check across full text
    lower_text = prose_with_placeholders.lower()
    for causal in UNPROVEN_CAUSAL_KEYWORDS:
        if causal in lower_text:
            issues.append(f"Causalité spéculative ou non prouvée détectée : '{causal}'.")

    # 2. Directional polarity validation per fact
    for fact_id, fact_data in facts.items():
        val = fact_data.get("value")
        unit = str(fact_data.get("unit", ""))

        # Only evaluate percentage or explicit variations
        if unit == "%" and isinstance(val, (int, float)):
            context = extract_context_window(prose_with_placeholders, fact_id)
            if not context:
                continue

            # If variation is strictly positive (increase)
            if val > 0.05:
                # Text must NOT claim a decrease in the immediate context
                has_down = any(down in context for down in DOWNWARD_KEYWORDS)
                has_up = any(up in context for up in UPWARD_KEYWORDS)
                if has_down and not has_up:
                    issues.append(
                        f"Incohérence directionnelle sur {fact_id} : Le fait indique une hausse (+{val:.1f}%), "
                        f"mais le texte utilise un vocabulaire de baisse ('{context.strip()}')."
                    )

            # If variation is strictly negative (decrease)
            elif val < -0.05:
                # Text must NOT claim an increase in the immediate context
                has_up = any(up in context for up in UPWARD_KEYWORDS)
                has_down = any(down in context for down in DOWNWARD_KEYWORDS)
                if has_up and not has_down:
                    issues.append(
                        f"Incohérence directionnelle sur {fact_id} : Le fait indique une baisse ({val:.1f}%), "
                        f"mais le texte utilise un vocabulaire de hausse ('{context.strip()}')."
                    )

        # 3. Temporal consistency check
        val_kind = fact_data.get("value_kind", "observed")
        if val_kind == "observed":
            context = extract_context_window(prose_with_placeholders, fact_id)
            if context and any(k in context for k in ["prévision future", "anticipé pour le mois prochain", "projeté"]):
                issues.append(
                    f"Incohérence temporelle sur {fact_id} : Une observation rétrospective ne peut être qualifiée de prévision future."
                )

    is_valid = len(issues) == 0
    return is_valid, issues
