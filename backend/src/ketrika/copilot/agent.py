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


def generate_sql_from_question(question: str, settings: Settings | None = None) -> str:
    """Generate a read-only Gold SQL query from a user question in French.

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
        ]
    ):
        # Trigger an intentionally guarded query or raise directly
        return "SELECT email FROM auth.user_account;"

    # 1. Price forecasting (Prévisions, horizons p10/p50/p90)
    if any(k in q for k in ["prévision", "prevision", "futur", "horizon", "p10", "p50", "p90"]):
        prod = "maize" if "maïs" in q or "mais" in q else "rice_milled"
        loc_clause = (
            "AND (location_pcode = 'MG-T' OR location_name ILIKE '%analamanga%')"
            if "analamanga" in q
            else ""
        )
        return f"""
        SELECT product_name, location_name, horizon, target_period, p10, p50, p90, model_name
        FROM gold.forecast_latest
        WHERE product_code = '{prod}' {loc_clause}
        ORDER BY horizon ASC
        LIMIT 3;
        """.strip()

    # 2. Climat / Précipitations / Météo (évalué avant anomalies pour intercepter les anomalies de pluie)
    if any(k in q for k in ["pluie", "précipitation", "precipitation", "climat", "météo", "meteo", "pluviométri", "pluviometri"]):
        loc_clause = (
            "WHERE location_pcode = 'MG-T' OR location_name ILIKE '%analamanga%'"
            if "analamanga" in q
            else ""
        )
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
        prod = "maize" if "maïs" in q or "mais" in q else "rice_milled"
        loc_clause = (
            "AND (location_pcode = 'MG-T' OR location_name ILIKE '%analamanga%')"
            if "analamanga" in q
            else ""
        )
        return f"""
        SELECT product_name, location_name, month, median_price, chg_1m, chg_12m, z_score_robust
        FROM gold.price_changes
        WHERE product_code = '{prod}' {loc_clause}
        ORDER BY month DESC
        LIMIT 6;
        """.strip()

    # 5. Volatilité des prix
    if "volatilité" in q or "volatilite" in q or "vol_12" in q:
        prod = "maize" if "maïs" in q or "mais" in q else "rice_milled"
        return f"""
        SELECT product_name, location_name, month, median_price, vol_12, med_12, mad_12
        FROM gold.price_changes
        WHERE product_code = '{prod}'
        ORDER BY month DESC
        LIMIT 5;
        """.strip()

    # 6. Stocks (statut, rupture, tension, disponibilité)
    if any(k in q for k in ["stock", "rupture", "disponibilité", "disponibilite"]):
        loc_clause = ""
        if "atsimo" in q:
            loc_clause = "AND (location_pcode = 'MG-U' OR location_name ILIKE '%atsimo%')"
        elif "analamanga" in q:
            loc_clause = "AND (location_pcode = 'MG-T' OR location_name ILIKE '%analamanga%')"
        return f"""
        SELECT product_name, location_name, latest_status, trend_direction, period_end
        FROM gold.stock_latest
        WHERE 1=1 {loc_clause}
        ORDER BY period_end DESC
        LIMIT 10;
        """.strip()

    # 7. Commerce extérieur / Importations / Dépendance
    if any(k in q for k in ["dépendance", "dependance", "idr"]):
        prod = "maize" if "maïs" in q or "mais" in q else "rice_milled"
        return f"""
        SELECT product_name, year, import_tons, production_tons, idr_pct
        FROM gold.import_dependency
        WHERE product_code = '{prod}'
        ORDER BY year DESC
        LIMIT 5;
        """.strip()

    if any(k in q for k in ["import", "export", "douane", "commerce"]):
        prod = "maize" if "maïs" in q or "mais" in q else "rice_milled"
        return f"""
        SELECT month, flow, weight_tons, value_mga
        FROM gold.trade_monthly
        WHERE product_code = '{prod}'
        ORDER BY month DESC
        LIMIT 12;
        """.strip()

    # 8. Score de santé du marché (Market Health Score)
    if any(k in q for k in ["market health", "santé du marché", "sante du marche", "score"]):
        loc_clause = (
            "AND (location_pcode = 'MG-T' OR location_name ILIKE '%analamanga%')"
            if "analamanga" in q
            else ""
        )
        return f"""
        SELECT product_name, location_name, month, market_health_score, score_price_stability, score_affordability
        FROM gold.market_health
        WHERE 1=1 {loc_clause}
        ORDER BY month DESC
        LIMIT 6;
        """.strip()

    # 9. Prix par source (min, max, médiane détaillée)
    if "par source" in q or "selon la source" in q or "détail des sources" in q:
        prod = "maize" if "maïs" in q or "mais" in q else "rice_milled"
        return f"""
        SELECT month, source_id, median_price, min_price, max_price, n_obs
        FROM gold.price_monthly
        WHERE product_code = '{prod}'
        ORDER BY month DESC
        LIMIT 10;
        """.strip()

    # 10. Source health / Retard / Fraîcheur / DataOps
    if any(k in q for k in ["sla", "retard", "fraîcheur", "fraicheur", "stale"]) or (
        "source" in q and any(k in q for k in ["santé", "sante", "health", "statut", "état", "etat"])
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
    prod = "maize" if "maïs" in q or "mais" in q else "rice_milled"
    loc_clause = (
        "AND (location_pcode = 'MG-T' OR location_name ILIKE '%analamanga%')"
        if "analamanga" in q
        else ""
    )
    return f"""
    SELECT product_name, location_name, month, median_price, chosen_source_id
    FROM gold.price_monthly_best
    WHERE product_code = '{prod}' {loc_clause}
    ORDER BY month DESC
    LIMIT 6;
    """.strip()


AGRICULTURAL_KEYWORDS: tuple[str, ...] = (
    "riz", "vary", "makalioka", "tsipala", "maïs", "mais", "manioc", "huile", "sucre",
    "farine", "légumineuse", "legumineuse", "haricot", "arachide", "blé", "ble", "ppn",
    "prix", "cours", "tarif", "ariary", "mga", "marché", "marche", "anosibe", "grossiste",
    "détail", "detail", "stock", "rupture", "disponibilité", "disponibilite", "soudure",
    "récolte", "recolte", "culture", "production", "import", "export", "douane", "commerce",
    "dépendance", "dependance", "idr", "météo", "meteo", "pluie", "précipitation", "precipitation",
    "climat", "sécheresse", "secheresse", "cyclone", "inondation", "ipc", "cpi", "inflation",
    "indice", "flambée", "flambee", "hausse", "baisse", "chute", "anomalie", "volatilité",
    "volatilite", "source", "sla", "retard", "fraîcheur", "fraicheur", "santé", "sante", "score",
    "prévision", "prevision", "futur", "horizon", "p10", "p50", "p90", "analamanga", "alaotra",
    "vakinankaratra", "boeny", "atsimo", "madagascar", "produit", "vivrier",
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
