"""Catalog and metadata of the Gold analytical layer for the Copilot (SPECS §15, §21)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColumnInfo:
    """Description of a column in a Gold materialized view."""

    name: str
    data_type: str
    description: str
    is_key: bool = False
    sample_values: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ViewInfo:
    """Description of a Gold analytical view."""

    view_name: str
    description: str
    grain: str
    columns: list[ColumnInfo]
    example_query: str


GOLD_VIEWS_CATALOG: list[ViewInfo] = [
    ViewInfo(
        view_name="gold.price_obs_current",
        description="Observations brutes individuelles courantes et acceptées avec provenance complète.",
        grain="1 ligne par observation de prix courante",
        columns=[
            ColumnInfo(
                "observation_id", "UUID", "Identifiant unique de l'observation", is_key=True
            ),
            ColumnInfo("source_id", "TEXT", "Identifiant de la source (odr, wfp_hdx_mdg, etc.)"),
            ColumnInfo("source_priority", "TEXT", "Niveau de priorité officiel (P0, P1, P2)"),
            ColumnInfo("product_id", "UUID", "Identifiant du produit canonique"),
            ColumnInfo("product_code", "TEXT", "Code produit canonique (ex: rice_milled, maize)"),
            ColumnInfo("product_name", "TEXT", "Nom usuel français du produit"),
            ColumnInfo("location_id", "UUID", "Identifiant géographique de référence"),
            ColumnInfo("location_pcode", "TEXT", "Code P-code du lieu (ex: MG-T, MG-U)"),
            ColumnInfo("location_name", "TEXT", "Nom de la région ou du district"),
            ColumnInfo("actor_level", "TEXT", "Stade de la filière: producer, wholesale, retail"),
            ColumnInfo("period_start", "DATE", "Début de la période observée"),
            ColumnInfo("period_end", "DATE", "Fin de la période observée"),
            ColumnInfo(
                "price_mga_per_base",
                "NUMERIC",
                "Prix normalisé en Ariary par unité de base (Ar/kg)",
            ),
            ColumnInfo("observed_or_imputed", "TEXT", "observed ou imputed"),
            ColumnInfo("extraction_method", "TEXT", "deterministic ou llm_verified"),
            ColumnInfo("confidence", "NUMERIC", "Indice de confiance (0.0 à 1.0)"),
        ],
        example_query="SELECT product_name, location_name, price_mga_per_base, period_start FROM gold.price_obs_current WHERE product_code = 'rice_milled' LIMIT 10;",
    ),
    ViewInfo(
        view_name="gold.price_monthly",
        description="Agrégats mensuels de prix ventilés par produit, région, niveau d'acteur et source de données.",
        grain="product x location x actor_level x month x source",
        columns=[
            ColumnInfo("product_id", "UUID", "ID produit"),
            ColumnInfo("product_code", "TEXT", "Code produit"),
            ColumnInfo("product_name", "TEXT", "Nom usuel produit"),
            ColumnInfo("location_id", "UUID", "ID lieu"),
            ColumnInfo("location_pcode", "TEXT", "P-code lieu"),
            ColumnInfo("location_name", "TEXT", "Nom lieu"),
            ColumnInfo("actor_level", "TEXT", "Niveau d'acteur (retail, wholesale, producer)"),
            ColumnInfo("month", "DATE", "Premier jour du mois (YYYY-MM-01)"),
            ColumnInfo("source_id", "TEXT", "Source ayant collecté ces observations"),
            ColumnInfo("source_priority", "TEXT", "Priorité de la source (P0, P1)"),
            ColumnInfo("median_price", "NUMERIC", "Prix médian en Ariary (MGA)"),
            ColumnInfo("min_price", "NUMERIC", "Prix minimum observé"),
            ColumnInfo("max_price", "NUMERIC", "Prix maximum observé"),
            ColumnInfo("n_obs", "BIGINT", "Nombre d'observations collectées"),
            ColumnInfo("imputed_share", "NUMERIC", "Part des observations imputées (0.0 à 1.0)"),
        ],
        example_query="SELECT month, source_id, median_price FROM gold.price_monthly WHERE product_code = 'rice_milled' AND location_pcode = 'MG-T' ORDER BY month DESC LIMIT 10;",
    ),
    ViewInfo(
        view_name="gold.price_monthly_best",
        description="Série mensuelle de référence avec arbitrage officiel de priorité (P0 observé > P1 observé > P1 imputé).",
        grain="product x location x actor_level x month",
        columns=[
            ColumnInfo("product_id", "UUID", "ID produit"),
            ColumnInfo("product_code", "TEXT", "Code produit"),
            ColumnInfo("product_name", "TEXT", "Nom produit"),
            ColumnInfo("location_id", "UUID", "ID lieu"),
            ColumnInfo("location_pcode", "TEXT", "P-code"),
            ColumnInfo("location_name", "TEXT", "Nom de la région"),
            ColumnInfo("admin_level", "SMALLINT", "1 pour Région, 2 pour District"),
            ColumnInfo("actor_level", "TEXT", "retail, wholesale, producer"),
            ColumnInfo("month", "DATE", "Mois de référence (YYYY-MM-01)"),
            ColumnInfo("median_price", "NUMERIC", "Prix médian officiel retenu en Ariary/kg"),
            ColumnInfo("min_price", "NUMERIC", "Prix minimum"),
            ColumnInfo("max_price", "NUMERIC", "Prix maximum"),
            ColumnInfo("n_obs", "BIGINT", "Nombre d'observations"),
            ColumnInfo("chosen_source_id", "TEXT", "Source officielle retenue après arbitrage"),
            ColumnInfo("chosen_priority", "TEXT", "Priorité de la source retenue"),
            ColumnInfo(
                "observed_or_imputed", "TEXT", "Nature de la valeur retenue (observed ou imputed)"
            ),
        ],
        example_query="SELECT month, median_price, chosen_source_id FROM gold.price_monthly_best WHERE product_code = 'rice_milled' AND location_pcode = 'MG-T' AND actor_level = 'retail' ORDER BY month DESC LIMIT 12;",
    ),
    ViewInfo(
        view_name="gold.price_changes",
        description="Variations de prix (m/m, sur 3 mois, sur 1 an), volatilité robuste (MAD/médiane) et z-score robuste.",
        grain="product x location x actor_level x month",
        columns=[
            ColumnInfo("product_id", "UUID", "ID produit"),
            ColumnInfo("product_code", "TEXT", "Code produit"),
            ColumnInfo("product_name", "TEXT", "Nom produit"),
            ColumnInfo("location_id", "UUID", "ID lieu"),
            ColumnInfo("location_pcode", "TEXT", "P-code région"),
            ColumnInfo("location_name", "TEXT", "Nom région"),
            ColumnInfo("actor_level", "TEXT", "Stade filière (retail)"),
            ColumnInfo("month", "DATE", "Mois"),
            ColumnInfo("median_price", "NUMERIC", "Prix médian actuel"),
            ColumnInfo("chg_1m", "NUMERIC", "Variation relative sur 1 mois (ex: 0.15 = +15%)"),
            ColumnInfo("chg_3m", "NUMERIC", "Variation relative sur 3 mois"),
            ColumnInfo("chg_12m", "NUMERIC", "Variation relative sur 12 mois (a/a)"),
            ColumnInfo("med_12", "NUMERIC", "Médiane mobile sur 12 mois"),
            ColumnInfo("mad_12", "NUMERIC", "Écart absolu médian (MAD) sur 12 mois"),
            ColumnInfo("vol_12", "NUMERIC", "Volatilité robuste sur 12 mois (mad_12 / med_12)"),
            ColumnInfo(
                "z_score_robust",
                "NUMERIC",
                "Z-score statistique robuste (P - med_12)/(1.4826 * mad_12)",
            ),
        ],
        example_query="SELECT month, median_price, chg_1m, chg_12m, z_score_robust FROM gold.price_changes WHERE product_code = 'rice_milled' AND location_pcode = 'MG-T' ORDER BY month DESC LIMIT 6;",
    ),
    ViewInfo(
        view_name="gold.stock_latest",
        description="Dernier état des stocks de PPN et tendance sur les 3 dernières observations.",
        grain="product x location",
        columns=[
            ColumnInfo("product_id", "UUID", "ID produit"),
            ColumnInfo("product_code", "TEXT", "Code produit"),
            ColumnInfo("product_name", "TEXT", "Nom usuel"),
            ColumnInfo("location_id", "UUID", "ID lieu"),
            ColumnInfo("location_pcode", "TEXT", "P-code"),
            ColumnInfo("location_name", "TEXT", "Nom région"),
            ColumnInfo("period_end", "DATE", "Date du dernier relevé"),
            ColumnInfo(
                "latest_status",
                "TEXT",
                "Statut actuel: sufficient (suffisant), tight (tendu), shortage (rupture)",
            ),
            ColumnInfo("prev_status", "TEXT", "Statut précédent"),
            ColumnInfo("trend_direction", "TEXT", "improving, stable, deteriorating"),
            ColumnInfo("days_of_supply", "NUMERIC", "Autonomie estimée en jours"),
        ],
        example_query="SELECT product_name, location_name, latest_status, trend_direction FROM gold.stock_latest WHERE product_code = 'rice_milled';",
    ),
    ViewInfo(
        view_name="gold.trade_monthly",
        description="Volumes et valeurs des flux commerciaux officiels mensuels (Douanes / FAOSTAT).",
        grain="product x flow x month",
        columns=[
            ColumnInfo("product_id", "UUID", "ID produit"),
            ColumnInfo("product_code", "TEXT", "Code produit"),
            ColumnInfo("product_name", "TEXT", "Nom produit"),
            ColumnInfo("flow", "TEXT", "import ou export"),
            ColumnInfo("month", "DATE", "Mois (YYYY-MM-01)"),
            ColumnInfo("weight_tons", "NUMERIC", "Poids net en tonnes"),
            ColumnInfo("value_mga", "NUMERIC", "Valeur CAF/FOB en Ariary"),
            ColumnInfo("value_usd", "NUMERIC", "Valeur en Dollars USD"),
            ColumnInfo("unit_value_mga_kg", "NUMERIC", "Valeur unitaire en Ar/kg"),
        ],
        example_query="SELECT month, flow, weight_tons, value_mga FROM gold.trade_monthly WHERE product_code = 'rice_milled' ORDER BY month DESC LIMIT 12;",
    ),
    ViewInfo(
        view_name="gold.import_dependency",
        description="Taux annuel de dépendance aux importations (IDR = imports / (production + imports - exports)).",
        grain="product x year",
        columns=[
            ColumnInfo("product_id", "UUID", "ID produit"),
            ColumnInfo("product_code", "TEXT", "Code produit"),
            ColumnInfo("product_name", "TEXT", "Nom produit"),
            ColumnInfo("year", "INTEGER", "Année civile"),
            ColumnInfo("import_tons", "NUMERIC", "Volume importé (tonnes)"),
            ColumnInfo("export_tons", "NUMERIC", "Volume exporté (tonnes)"),
            ColumnInfo("production_tons", "NUMERIC", "Production nationale (tonnes)"),
            ColumnInfo("idr_pct", "NUMERIC", "Taux de dépendance aux importations en %"),
        ],
        example_query="SELECT year, import_tons, production_tons, idr_pct FROM gold.import_dependency WHERE product_code = 'rice_milled' ORDER BY year DESC LIMIT 5;",
    ),
    ViewInfo(
        view_name="gold.weather_monthly",
        description="Précipitations mensuelles observées (NASA POWER / CHIRPS) et écarts par rapport à la climatologie.",
        grain="district x month",
        columns=[
            ColumnInfo("location_id", "UUID", "ID du district"),
            ColumnInfo("location_pcode", "TEXT", "P-code district"),
            ColumnInfo("location_name", "TEXT", "Nom district"),
            ColumnInfo("month", "DATE", "Mois"),
            ColumnInfo("precip_total_mm", "NUMERIC", "Cumul de pluie mensuel (mm)"),
            ColumnInfo("baseline_precip_mm", "NUMERIC", "Normale climatique mensuelle (mm)"),
            ColumnInfo(
                "rain_anom_pct", "NUMERIC", "Anomalie en % vs normale (ex: -0.35 = -35% déficit)"
            ),
            ColumnInfo("t2m_max_c", "NUMERIC", "Température maximale moyenne (°C)"),
            ColumnInfo("t2m_min_c", "NUMERIC", "Température minimale moyenne (°C)"),
        ],
        example_query="SELECT month, location_name, precip_total_mm, rain_anom_pct FROM gold.weather_monthly WHERE location_pcode = 'MG-T' ORDER BY month DESC LIMIT 6;",
    ),
    ViewInfo(
        view_name="gold.cpi_food",
        description="Indice des Prix à la Consommation (INSTAT NIPC) pour la composante alimentaire.",
        grain="série x mois",
        columns=[
            ColumnInfo("series_code", "TEXT", "Code de la série d'indice"),
            ColumnInfo("series_label", "TEXT", "Libellé officiel de la série"),
            ColumnInfo("geo_scope", "TEXT", "Périmètre (national, urbain, Antananarivo)"),
            ColumnInfo("month", "DATE", "Mois d'observation"),
            ColumnInfo("index_value", "NUMERIC", "Valeur de l'indice IPC"),
            ColumnInfo("chg_1m", "NUMERIC", "Inflation mensuelle"),
            ColumnInfo("chg_12m", "NUMERIC", "Inflation annuelle (glissement annuel)"),
        ],
        example_query="SELECT month, index_value, chg_1m, chg_12m FROM gold.cpi_food ORDER BY month DESC LIMIT 12;",
    ),
    ViewInfo(
        view_name="gold.market_health",
        description="Indicateur synthétique Market Health Score (0-100) combinant stabilité, accessibilité, disponibilité et climat.",
        grain="product x region x month",
        columns=[
            ColumnInfo("product_id", "UUID", "ID produit"),
            ColumnInfo("product_code", "TEXT", "Code produit"),
            ColumnInfo("product_name", "TEXT", "Nom produit"),
            ColumnInfo("location_id", "UUID", "ID région"),
            ColumnInfo("location_pcode", "TEXT", "P-code région"),
            ColumnInfo("location_name", "TEXT", "Nom région"),
            ColumnInfo("month", "DATE", "Mois"),
            ColumnInfo(
                "market_health_score", "NUMERIC", "Score global de santé de marché (0 à 100)"
            ),
            ColumnInfo(
                "score_price_stability", "NUMERIC", "Score stabilité des prix (0-100, poids 0.30)"
            ),
            ColumnInfo(
                "score_affordability", "NUMERIC", "Score accessibilité prix (0-100, poids 0.25)"
            ),
            ColumnInfo(
                "score_availability", "NUMERIC", "Score disponibilité stocks (0-100, poids 0.25)"
            ),
            ColumnInfo(
                "score_climate_risk", "NUMERIC", "Score risque climatique (0-100, poids 0.20)"
            ),
            ColumnInfo("coverage", "NUMERIC", "Taux de couverture des composantes disponibles"),
        ],
        example_query="SELECT month, market_health_score, score_price_stability, score_affordability FROM gold.market_health WHERE product_code = 'rice_milled' AND location_pcode = 'MG-T' ORDER BY month DESC LIMIT 6;",
    ),
    ViewInfo(
        view_name="gold.source_health",
        description="Cockpit de surveillance DataOps sur la fraîcheur et la qualité des sources officielles.",
        grain="source",
        columns=[
            ColumnInfo("source_id", "TEXT", "Identifiant de la source"),
            ColumnInfo("source_name", "TEXT", "Nom complet"),
            ColumnInfo("priority", "TEXT", "P0, P1, P2"),
            ColumnInfo("freshness_days", "INTEGER", "Jours écoulés depuis la dernière donnée"),
            ColumnInfo("freshness_sla_days", "INTEGER", "Seuil SLA de fraîcheur en jours"),
            ColumnInfo("is_stale", "BOOLEAN", "Vrai si la source dépasse son délai SLA"),
            ColumnInfo("parse_success_rate", "NUMERIC", "Taux de succès de découpage technique"),
            ColumnInfo("last_run_started_at", "TIMESTAMPTZ", "Horodatage de la dernière ingestion"),
        ],
        example_query="SELECT source_id, priority, freshness_days, freshness_sla_days, is_stale FROM gold.source_health ORDER BY priority ASC, freshness_days DESC;",
    ),
    ViewInfo(
        view_name="gold.forecast_latest",
        description="Prévisions de prix univariées à 1, 2 et 3 mois avec intervalles de conformité 80% (p10, p50, p90).",
        grain="série x horizon",
        columns=[
            ColumnInfo("product_id", "UUID", "ID produit"),
            ColumnInfo("product_code", "TEXT", "Code produit"),
            ColumnInfo("product_name", "TEXT", "Nom produit"),
            ColumnInfo("location_id", "UUID", "ID lieu"),
            ColumnInfo("location_pcode", "TEXT", "P-code lieu"),
            ColumnInfo("location_name", "TEXT", "Nom région"),
            ColumnInfo("actor_level", "TEXT", "retail, wholesale, producer"),
            ColumnInfo("horizon", "SMALLINT", "Horizon en mois: 1, 2 ou 3"),
            ColumnInfo("target_period", "DATE", "Mois cible de la prévision (YYYY-MM-01)"),
            ColumnInfo("p10", "NUMERIC", "Borne inférieure intervalle 80% (Ar/kg)"),
            ColumnInfo("p50", "NUMERIC", "Valeur médiane prévue (Ar/kg)"),
            ColumnInfo("p90", "NUMERIC", "Borne supérieure intervalle 80% (Ar/kg)"),
            ColumnInfo(
                "model_name",
                "TEXT",
                "Nom du modèle sélectionné au backtest (SeasonalNaive, AutoETS, AutoARIMA)",
            ),
            ColumnInfo(
                "wape", "NUMERIC", "Erreur WAPE du modèle sur les 6 dernières fenêtres de test"
            ),
        ],
        example_query="SELECT horizon, target_period, p10, p50, p90, model_name FROM gold.forecast_latest WHERE product_code = 'rice_milled' AND location_pcode = 'MG-T' ORDER BY horizon ASC;",
    ),
]


def generate_schema_catalog_markdown() -> str:
    """Format the complete Gold schema catalog into a structured markdown document for prompt injection."""
    lines: list[str] = [
        "# Catalogue des vues analytiques disponibles (Schéma `gold`)",
        "",
        "Seul le schéma `gold` est accessible. Toute requête doit porter exclusivement sur ces vues.",
        "",
    ]

    for view in GOLD_VIEWS_CATALOG:
        lines.append(f"## {view.view_name}")
        lines.append(f"**Description :** {view.description}")
        lines.append(f"**Grain :** {view.grain}")
        lines.append("")
        lines.append("| Colonne | Type | Rôle / Description |")
        lines.append("|---|---|---|")
        for col in view.columns:
            key_tag = " `[KEY]`" if col.is_key else ""
            lines.append(f"| `{col.name}`{key_tag} | `{col.data_type}` | {col.description} |")
        lines.append("")
        lines.append(f"**Exemple de requête :**\n```sql\n{view.example_query}\n```")
        lines.append("")

    return "\n".join(lines)
