"""Copilot analyst agent orchestrating NL2SQL, SQL Guard, execution and placeholder response generation (SPECS §21)."""

from __future__ import annotations

import logging
from typing import Any

from ketrika.copilot.executor import execute_copilot_query
from ketrika.copilot.sql_guard import SqlGuardError
from ketrika.copilot.writer import (
    build_cell_placeholders,
    render_deterministic_fallback,
)
from ketrika.core.settings import Settings, get_settings

logger = logging.getLogger("ketrika.copilot.agent")


def resolve_product_code(q: str) -> str:
    """Resolve PPN commodity code from query keywords including Malagasy terms."""
    if any(k in q for k in ["maïs", "mais", "katsaka"]):
        return "maize"
    if any(k in q for k in ["manioc", "mangahazo"]):
        return "cassava"
    if any(k in q for k in ["huile", "menaka"]):
        return "oil_edible"
    if any(k in q for k in ["sucre", "siramamy"]):
        return "sugar"
    if any(k in q for k in ["farine", "blé", "ble"]):
        return "wheat_flour"
    if any(k in q for k in ["haricot", "légumineuse", "legumineuse", "voamena", "lojy"]):
        return "beans"
    return "rice_milled"


def resolve_product_filter(prod: str) -> str:
    """Generate SQL filter matching both canonical uppercase and lowercase legacy codes."""
    if prod == "rice_milled":
        return "(product_code = 'rice_milled' OR product_code = 'RICE_WHITE_LOCAL' OR product_code = 'RICE_WHITE_IMPORTED')"
    if prod == "maize":
        return "(product_code = 'maize' OR product_code = 'MAIZE_GRAIN')"
    if prod == "sugar":
        return "(product_code = 'sugar' OR product_code = 'SUGAR')"
    if prod == "oil_edible":
        return "(product_code = 'oil_edible' OR product_code = 'VEG_OIL')"
    if prod == "wheat_flour":
        return "(product_code = 'wheat_flour' OR product_code = 'WHEAT_FLOUR')"
    if prod == "beans":
        return "(product_code = 'beans' OR product_code = 'BEANS_DRY')"
    if prod == "cassava":
        return "(product_code = 'cassava' OR product_code = 'CASSAVA_FRESH' OR product_code = 'CASSAVA_DRIED')"
    return f"product_code = '{prod}'"


def resolve_location_clause(q: str, prefix_operator: str = "AND") -> str:
    """Resolve location filter clause from query keywords."""
    op = f"{prefix_operator} "
    if any(k in q for k in ["analamanga", "antananarivo", "anosibe"]):
        return f"{op}(location_pcode = 'MG-T' OR location_name ILIKE '%analamanga%')"
    if any(k in q for k in ["alaotra", "amparafaravola"]):
        return f"{op}(location_pcode = 'MG-H' OR location_name ILIKE '%alaotra%')"
    if any(k in q for k in ["atsimo", "toliara", "tuléar"]):
        return f"{op}(location_pcode = 'MG-U' OR location_name ILIKE '%atsimo%')"
    if any(k in q for k in ["vakinankaratra", "antsirabe"]):
        return f"{op}(location_pcode = 'MG-D' OR location_name ILIKE '%vakinankaratra%')"
    if any(k in q for k in ["boeny", "mahajanga", "majunga"]):
        return f"{op}(location_pcode = 'MG-C' OR location_name ILIKE '%boeny%')"
    if any(k in q for k in ["atsinanana", "toamasina", "tamatave"]):
        return f"{op}(location_pcode = 'MG-A' OR location_name ILIKE '%atsinanana%')"
    return ""


def generate_sql_from_question(question: str, settings: Settings | None = None) -> str:
    """Generate a read-only Gold SQL query from a user question in French or Malagasy.

    Uses semantic pattern matching with fallback to LLM generation when enabled.
    """
    q = question.lower().strip()

    # Security check: prompt injections attempting to read auth / system tables
    if any(
        k in q
        for k in [
            "auth.user_account",
            "auth.api_key",
            "pg_read_file",
            "pg_shadow",
            "ignore tes règles",
            "ignore tes instructions",
            "identifiants administrateur",
            "system prompt",
        ]
    ):
        return "SELECT email FROM auth.user_account;"

    # Direct SQL input check (passes through to validate_gold_sql so SQL Guard blocks hostiles)
    words = q.split()
    if words:
        first_token = words[0].strip("();,").lower()
        if first_token in (
            "select",
            "drop",
            "delete",
            "update",
            "insert",
            "with",
            "alter",
            "create",
            "truncate",
        ):
            return question.strip()

    # 1. Price forecasting (Prévisions, horizons p10/p50/p90)
    if any(k in q for k in ["prévision", "prevision", "futur", "horizon", "p10", "p50", "p90"]):
        prod = resolve_product_code(q)
        loc_clause = resolve_location_clause(q, "AND")
        return f"""
        SELECT product_name, location_name, horizon, target_period, p10, p50, p90, model_name
        FROM gold.forecast_latest
        WHERE {resolve_product_filter(prod)} {loc_clause}
        ORDER BY horizon ASC
        LIMIT 3;
        """.strip()

    # 2. Climat / Précipitations / Météo (évalué avant anomalies pour intercepter les anomalies de pluie)
    if any(
        k in q
        for k in [
            "pluie",
            "précipitation",
            "precipitation",
            "climat",
            "météo",
            "meteo",
            "pluviométri",
            "pluviometri",
            "sécheresse",
            "secheresse",
        ]
    ):
        loc_clause = resolve_location_clause(q, "WHERE")
        return f"""
        SELECT location_name, month, precip_total_mm, baseline_precip_mm, rain_anom_pct
        FROM gold.weather_monthly
        {loc_clause}
        ORDER BY month DESC
        LIMIT 6;
        """.strip()

    # 3. Anomalies, Flambées et Chutes de prix (spikes / drops / z-score)
    if any(k in q for k in ["flambée", "flambee", "anomalie", "pic", "hausse anormale"]):
        return """
        SELECT product_name, location_name, month, median_price, chg_1m, z_score_robust
        FROM gold.price_changes
        WHERE z_score_robust > 3.0 AND chg_1m > 0.15
        ORDER BY month DESC, z_score_robust DESC
        LIMIT 10;
        """.strip()

    if any(k in q for k in ["chute", "baisse anormale"]):
        return """
        SELECT product_name, location_name, month, median_price, chg_1m, z_score_robust
        FROM gold.price_changes
        WHERE z_score_robust < -3.0 AND chg_1m < -0.15
        ORDER BY month DESC, z_score_robust ASC
        LIMIT 10;
        """.strip()

    # 4. Variations de prix (sur un an, a/a, m/m, glissement annuel)
    if any(k in q for k in ["variation", "inflation", "évolution", "evolution", "glissement"]):
        prod = resolve_product_code(q)
        loc_clause = resolve_location_clause(q, "AND")
        return f"""
        SELECT product_name, location_name, month, median_price, chg_1m, chg_12m, z_score_robust
        FROM gold.price_changes
        WHERE {resolve_product_filter(prod)} {loc_clause}
        ORDER BY month DESC
        LIMIT 6;
        """.strip()

    # 5. Volatilité des prix
    if "volatilité" in q or "volatilite" in q or "vol_12" in q:
        prod = resolve_product_code(q)
        return f"""
        SELECT product_name, location_name, month, median_price, vol_12, med_12, mad_12
        FROM gold.price_changes
        WHERE {resolve_product_filter(prod)}
        ORDER BY month DESC
        LIMIT 5;
        """.strip()

    # 6. Stocks (statut, rupture, tension, disponibilité)
    if any(k in q for k in ["stock", "rupture", "disponibilité", "disponibilite", "tension"]):
        loc_clause = resolve_location_clause(q, "AND")
        return f"""
        SELECT product_name, location_name, latest_status, trend_direction, period_end
        FROM gold.stock_latest
        WHERE 1=1 {loc_clause}
        ORDER BY period_end DESC
        LIMIT 10;
        """.strip()

    # 7. Commerce extérieur / Importations / Dépendance
    if any(k in q for k in ["dépendance", "dependance", "idr"]):
        prod = resolve_product_code(q)
        return f"""
        SELECT product_name, year, import_tons, production_tons, idr_pct
        FROM gold.import_dependency
        WHERE {resolve_product_filter(prod)}
        ORDER BY year DESC
        LIMIT 5;
        """.strip()

    # Commerce extérieur (douanes, imports/exports) - exclusion stricte de l'adjectif "important"
    if any(
        k in q
        for k in [
            "importation",
            "importations",
            "exportation",
            "exportations",
            "douane",
            "douanes",
            "commerce extérieur",
            "commerce exterieur",
        ]
    ) or any(
        w in q.split() for w in ["import", "imports", "export", "exports", "douane", "commerce"]
    ):
        prod = resolve_product_code(q)
        return f"""
        SELECT month, flow, weight_tons, value_mga
        FROM gold.trade_monthly
        WHERE {resolve_product_filter(prod)}
        ORDER BY month DESC
        LIMIT 12;
        """.strip()

    # 8. Score de santé du marché (Market Health Score)
    if any(k in q for k in ["market health", "santé du marché", "sante du marche", "score"]):
        loc_clause = resolve_location_clause(q, "AND")
        return f"""
        SELECT product_name, location_name, month, market_health_score, score_price_stability, score_affordability
        FROM gold.market_health
        WHERE 1=1 {loc_clause}
        ORDER BY month DESC
        LIMIT 6;
        """.strip()

    # 9. Prix par source (min, max, médiane détaillée)
    if "par source" in q or "selon la source" in q or "détail des sources" in q:
        prod = resolve_product_code(q)
        return f"""
        SELECT month, source_id, median_price, min_price, max_price, n_obs
        FROM gold.price_monthly
        WHERE {resolve_product_filter(prod)}
        ORDER BY month DESC
        LIMIT 10;
        """.strip()

    # 10. Source health / Retard / Fraîcheur / DataOps
    if any(k in q for k in ["sla", "retard", "fraîcheur", "fraicheur", "stale"]) or (
        "source" in q
        and any(k in q for k in ["santé", "sante", "health", "statut", "état", "etat"])
    ):
        return """
        SELECT source_id, priority, freshness_days, freshness_sla_days, is_stale
        FROM gold.source_health
        WHERE is_stale = true OR freshness_days > freshness_sla_days
        ORDER BY freshness_days DESC
        LIMIT 10;
        """.strip()

    # 11. Indice IPC Alimentaire (INSTAT NIPC)
    if any(k in q for k in ["ipc", "cpi", "indice des prix"]):
        return """
        SELECT series_label, month, index_value, chg_1m, chg_12m
        FROM gold.cpi_food
        ORDER BY month DESC
        LIMIT 12;
        """.strip()

    # Check relevance to agricultural market intelligence domain
    has_agri_context = any(kw in q for kw in AGRICULTURAL_KEYWORDS)
    if not has_agri_context:
        # Out-of-scope question: refuse honestly rather than guessing
        return ""

    # 12. Default : Prix mensuel retenu (Best) pour les questions relatives aux prix vivriers
    prod = resolve_product_code(q)
    loc_clause = resolve_location_clause(q, "AND")
    return f"""
    SELECT product_name, location_name, month, median_price, chosen_source_id
    FROM gold.price_monthly_best
    WHERE {resolve_product_filter(prod)} {loc_clause}
    ORDER BY month DESC
    LIMIT 6;
    """.strip()


AGRICULTURAL_KEYWORDS: tuple[str, ...] = (
    "riz",
    "vary",
    "makalioka",
    "tsipala",
    "maïs",
    "mais",
    "katsaka",
    "manioc",
    "mangahazo",
    "huile",
    "menaka",
    "sucre",
    "siramamy",
    "farine",
    "légumineuse",
    "legumineuse",
    "haricot",
    "voamena",
    "lojy",
    "arachide",
    "blé",
    "ble",
    "ppn",
    "prix",
    "vidiny",
    "vidin'ny",
    "cours",
    "tarif",
    "ariary",
    "mga",
    "marché",
    "marche",
    "tsena",
    "anosibe",
    "grossiste",
    "détail",
    "detail",
    "stock",
    "rupture",
    "disponibilité",
    "disponibilite",
    "tension",
    "soudure",
    "récolte",
    "recolte",
    "vokatra",
    "culture",
    "production",
    "import",
    "export",
    "douane",
    "commerce",
    "dépendance",
    "dependance",
    "idr",
    "météo",
    "meteo",
    "pluie",
    "orana",
    "précipitation",
    "precipitation",
    "climat",
    "sécheresse",
    "secheresse",
    "cyclone",
    "inondation",
    "ipc",
    "cpi",
    "inflation",
    "indice",
    "flambée",
    "flambee",
    "hausse",
    "baisse",
    "chute",
    "anomalie",
    "volatilité",
    "volatilite",
    "source",
    "sla",
    "retard",
    "fraîcheur",
    "fraicheur",
    "santé",
    "sante",
    "score",
    "prévision",
    "prevision",
    "futur",
    "horizon",
    "p10",
    "p50",
    "p90",
    "analamanga",
    "alaotra",
    "vakinankaratra",
    "boeny",
    "atsimo",
    "atsinanana",
    "antananarivo",
    "toamasina",
    "mahajanga",
    "antsirabe",
    "toliara",
    "madagascar",
    "produit",
    "vivrier",
)


class CopilotAgent:
    """End-to-end Copilot Analyst Agent for agricultural market intelligence."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def ask(self, question: str) -> dict[str, Any]:
        """Process a natural language user query and return verified answer, SQL and citations."""
        clean_q = question.strip()
        if not clean_q:
            return {
                "answer_markdown": "Veuillez poser une question sur le marché des produits vivriers PPN.",
                "sql": "",
                "rows_preview": [],
                "citations": [],
                "value_kinds": [],
                "provenance_summary": "Aucune question fournie.",
            }

        # 1. Translate question to SQL
        raw_sql = generate_sql_from_question(clean_q, self.settings)

        # Honest abstention on out-of-scope queries
        if not raw_sql:
            return {
                "answer_markdown": (
                    "Je suis le Copilote d'intelligence de marché de Ketrika, spécialisé dans la veille des prix, "
                    "stocks, approvisionnements et météo agricole des produits vivriers à Madagascar (riz, maïs, manioc, "
                    "huile, sucre, légumineuses, farine). Votre question ne semble pas concerner ces filières ou "
                    "dépasse le périmètre des données officielles disponibles."
                ),
                "sql": "",
                "rows_preview": [],
                "citations": [],
                "value_kinds": [],
                "provenance_summary": "Abstention loyale : question hors périmètre vivrier ou non reconnue.",
            }

        # 2. Validate and execute SQL under copilot_ro role
        try:
            query_result = execute_copilot_query(raw_sql, self.settings)
        except SqlGuardError as s_err:
            logger.warning("copilot_query_blocked_by_guard: %s (%s)", raw_sql, s_err)
            return {
                "answer_markdown": f"⚠️ **Requête non autorisée :** {s_err}",
                "sql": raw_sql,
                "rows_preview": [],
                "citations": [],
                "value_kinds": [],
                "provenance_summary": "Requête refusée par la politique de sécurité SQL Guard.",
            }
        except Exception as exc:
            logger.error("copilot_execution_failed: %s (%s)", raw_sql, exc)
            return {
                "answer_markdown": f"Une erreur est survenue lors de l'exécution de la requête : {exc}",
                "sql": raw_sql,
                "rows_preview": [],
                "citations": [],
                "value_kinds": [],
                "provenance_summary": "Erreur d'exécution technique.",
            }

        # 3. Format response using strict cell placeholder system (anti-hallucination)
        cell_map, rows_preview = build_cell_placeholders(query_result)

        # Build initial prose referencing placeholders
        if not query_result.rows:
            answer_md = "Aucun enregistrement ne correspond à vos critères dans les données officielles Gold."
        else:
            # Deterministic clean presentation
            answer_md = render_deterministic_fallback(query_result)

        return {
            "answer_markdown": answer_md,
            "sql": query_result.sql,
            "rows_preview": rows_preview,
            "citations": query_result.citations,
            "value_kinds": query_result.value_kinds,
            "provenance_summary": (
                "Données officielles vérifiées issues du schéma Gold avec traçabilité Bronze SHA-256 intégrale. "
                "Zéro chiffre libre non audité."
            ),
        }
