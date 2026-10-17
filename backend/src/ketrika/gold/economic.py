"""Interpretable Economic Dashboard and Metric Cards engine (R2.8, ADR-070).

Normative principles:
1. Strict multi-dimensional independence: No fake aggregate economic health score.
2. Absolute separation of headline/food inflation (CPI) and market price changes (MGA/kg).
3. Physical unit integrity: Trade volume (tons) vs value (MGA) and verified unit costs.
4. Base shift protection: Refusal of implicit chaining between distinct index bases.
5. Strict nullity management: Any missing series or zero denominator yields NULL with explicit reason.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DimensionType = Literal["inflation", "exchange_rate", "fuel_energy", "external_trade", "real_activity"]
CompletenessStatus = Literal["complete", "partial", "no_data"]

# Null reason codes
REASON_ZERO_DENOMINATOR = "zero_denominator"
REASON_MISSING_DENOMINATOR = "missing_denominator"
REASON_MISSING_SERIES = "missing_series"
REASON_UNALIGNED_PERIOD = "unaligned_period"
REASON_INCOMPATIBLE_UNITS = "incompatible_units"
REASON_BASE_SHIFT = "base_shift"


@dataclass(frozen=True)
class EconomicMetricCard:
    """Normative specification of an economic indicator (SPECS §19, ADR-070)."""

    metric_id: str
    dimension: DimensionType
    title: str
    definition: str
    formula: str
    unit: str
    frequency: str
    geo_scope: str
    primary_source: str
    source_family: str
    publication_lag_days: int
    limitations: str


# Canonical catalog of 14 normative metric cards
ECONOMIC_METRIC_CARDS: dict[str, EconomicMetricCard] = {
    "inflation_headline": EconomicMetricCard(
        metric_id="inflation_headline",
        dimension="inflation",
        title="Indice des Prix à la Consommation (NIPC) – Ensemble National",
        definition="Mesure de l'évolution du niveau général des prix du panier des ménages.",
        formula="((I_t / I_{t-12}) - 1) * 100",
        unit="pct",
        frequency="monthly",
        geo_scope="national",
        primary_source="INSTAT",
        source_family="instat",
        publication_lag_days=45,
        limitations="Ne mesure pas le prix d'un produit isolé mais un panier pondéré urbain.",
    ),
    "inflation_food": EconomicMetricCard(
        metric_id="inflation_food",
        dimension="inflation",
        title="NIPC – Produits alimentaires et boissons non alcoolisées",
        definition="Indice des prix de la composante alimentaire du panier de consommation.",
        formula="((I_food_t / I_food_{t-12}) - 1) * 100",
        unit="pct",
        frequency="monthly",
        geo_scope="national",
        primary_source="INSTAT",
        source_family="instat",
        publication_lag_days=45,
        limitations="Distinct des relevés de marché direct au kg : pondération d'indices urbains.",
    ),
    "fx_usd_mga": EconomicMetricCard(
        metric_id="fx_usd_mga",
        dimension="exchange_rate",
        title="Cours moyen pondéré du Dollar Américain sur le MID",
        definition="Taux de change de référence pour la facturation des importations vivrières.",
        formula="Taux officiel MID publié par Banky Foiben'i Madagasikara.",
        unit="MGA/USD",
        frequency="daily",
        geo_scope="national",
        primary_source="Banky Foiben'i Madagasikara (BFM)",
        source_family="bfm",
        publication_lag_days=1,
        limitations="Cours interbancaire de gros ; n'inclut pas les commissions bancaires ni le marché informel.",
    ),
    "fx_eur_mga": EconomicMetricCard(
        metric_id="fx_eur_mga",
        dimension="exchange_rate",
        title="Cours moyen pondéré de l'Euro sur le MID",
        definition="Taux de change officiel de référence pour les flux régionaux de l'Océan Indien.",
        formula="Taux officiel MID publié par BFM.",
        unit="MGA/EUR",
        frequency="daily",
        geo_scope="national",
        primary_source="Banky Foiben'i Madagasikara (BFM)",
        source_family="bfm",
        publication_lag_days=1,
        limitations="Cours interbancaire de gros hors commissions de détail.",
    ),
    "fuel_diesel": EconomicMetricCard(
        metric_id="fuel_diesel",
        dimension="fuel_energy",
        title="Prix plafond réglementé du Gazole à la pompe",
        definition="Prix plafond officiel déterminant le coût du fret routier par camion diesel.",
        formula="Barème réglementé fixé par arrêté interministériel et diffusé par l'OMH.",
        unit="MGA/L",
        frequency="event",
        geo_scope="national",
        primary_source="Office Malgache des Hydrocarbures (OMH)",
        source_family="omh",
        publication_lag_days=5,
        limitations="Prix plafond légal administré ; ne garantit pas la disponibilité effective en cas de tension.",
    ),
    "fuel_sp95": EconomicMetricCard(
        metric_id="fuel_sp95",
        dimension="fuel_energy",
        title="Prix plafond réglementé du Super 95 à la pompe",
        definition="Prix maximal autorisé pour le carburant super sans plomb.",
        formula="Barème réglementé officiel OMH.",
        unit="MGA/L",
        frequency="event",
        geo_scope="national",
        primary_source="OMH",
        source_family="omh",
        publication_lag_days=5,
        limitations="Prix plafond légal administré.",
    ),
    "fuel_kerosene": EconomicMetricCard(
        metric_id="fuel_kerosene",
        dimension="fuel_energy",
        title="Prix plafond réglementé du Pétrole Lampant",
        definition="Prix maximal autorisé pour l'éclairage et l'énergie des ménages ruraux et vulnérables.",
        formula="Barème réglementé officiel OMH.",
        unit="MGA/L",
        frequency="event",
        geo_scope="national",
        primary_source="OMH",
        source_family="omh",
        publication_lag_days=5,
        limitations="Prix plafond subventionné ou administré.",
    ),
    "rice_import_volume": EconomicMetricCard(
        metric_id="rice_import_volume",
        dimension="external_trade",
        title="Importations de riz blanc – Volume mensuel",
        definition="Quantité totale de riz déclarée aux douanes et débarquée au port.",
        formula="Somme des volumes physiques déclarés (code HS 1006).",
        unit="tons",
        frequency="monthly",
        geo_scope="national",
        primary_source="Douanes / INSTAT TBE",
        source_family="instat",
        publication_lag_days=60,
        limitations="Enregistrements portuaires officiels uniquement.",
    ),
    "rice_import_value": EconomicMetricCard(
        metric_id="rice_import_value",
        dimension="external_trade",
        title="Importations de riz blanc – Valeur CAF mensuelle",
        definition="Valeur CAF (Coût, Assurance, Fret) totale déclarée à la frontière en Ariary.",
        formula="Somme des valeurs CAF déclarées.",
        unit="MGA",
        frequency="monthly",
        geo_scope="national",
        primary_source="Douanes / INSTAT TBE",
        source_family="instat",
        publication_lag_days=60,
        limitations="Valeur frontière CAF, avant taxes de débarquement et marge des importateurs.",
    ),
    "rice_import_unit_cost": EconomicMetricCard(
        metric_id="rice_import_unit_cost",
        dimension="external_trade",
        title="Coût unitaire d'importation CAF du riz",
        definition="Prix moyen d'importation par kilogramme à la frontière portuaire.",
        formula="Valeur CAF (MGA) / (Volume (tonnes) * 1000)",
        unit="MGA/kg",
        frequency="monthly",
        geo_scope="national",
        primary_source="Douanes / INSTAT TBE",
        source_family="instat",
        publication_lag_days=60,
        limitations="Borne inférieure théorique du prix de gros à Toamasina.",
    ),
    "rice_import_dependency_ratio": EconomicMetricCard(
        metric_id="rice_import_dependency_ratio",
        dimension="external_trade",
        title="Ratio de dépendance aux importations de riz (IDR)",
        definition="Part des importations nettes dans la disponibilité apparente annuelle.",
        formula="Imports / (Production + Imports - Exports)",
        unit="ratio",
        frequency="annual",
        geo_scope="national",
        primary_source="FAOSTAT / Douanes",
        source_family="faostat",
        publication_lag_days=180,
        limitations="Comparaison annuelle agrégée ; suppose des pertes post-récolte stables.",
    ),
    "gdp_growth_real": EconomicMetricCard(
        metric_id="gdp_growth_real",
        dimension="real_activity",
        title="Taux de croissance trimestriel du PIB réel",
        definition="Variation annuelle du Produit Intérieur Brut réel trimestriel.",
        formula="((PIB_t / PIB_{t-4}) - 1) * 100",
        unit="pct",
        frequency="quarterly",
        geo_scope="national",
        primary_source="INSTAT TBE",
        source_family="instat",
        publication_lag_days=90,
        limitations="Fréquence trimestrielle stricte ; aucune division en faux mois.",
    ),
    "ipi_industrial_production": EconomicMetricCard(
        metric_id="ipi_industrial_production",
        dimension="real_activity",
        title="Indice de la Production Industrielle (IPI)",
        definition="Mesure de l'activité manufacturière et agro-alimentaire.",
        formula="Indice d'activité en base 100.",
        unit="index_points",
        frequency="quarterly",
        geo_scope="national",
        primary_source="INSTAT TBE",
        source_family="instat",
        publication_lag_days=90,
        limitations="Couvre les entreprises formelles enregistrées.",
    ),
    "electricity_consumption": EconomicMetricCard(
        metric_id="electricity_consumption",
        dimension="real_activity",
        title="Consommation d'électricité interconnectée",
        definition="Volume d'énergie électrique distribué sur le réseau JIRAMA.",
        formula="Volume total en kWh publié dans le TBE.",
        unit="kWh",
        frequency="monthly",
        geo_scope="national",
        primary_source="JIRAMA via INSTAT TBE",
        source_family="instat",
        publication_lag_days=60,
        limitations="Indicateur d'activité urbaine et industrielle.",
    ),
}


# =========================================================================
# CALCULATIONS & GUARDS
# =========================================================================

def calculate_safe_variation(
    current_val: float | None,
    prev_val: float | None,
    current_base: str | None = None,
    prev_base: str | None = None,
) -> tuple[float | None, str | None]:
    """Calculate relative variation with strict guard against base shifts and zero denominators."""
    if current_base is not None and prev_base is not None and current_base != prev_base:
        return None, REASON_BASE_SHIFT
    if prev_val is None:
        return None, REASON_MISSING_DENOMINATOR
    if prev_val == 0.0:
        return None, REASON_ZERO_DENOMINATOR
    if current_val is None:
        return None, REASON_MISSING_SERIES
    return round((current_val / prev_val) - 1.0, 4), None


def calculate_import_unit_cost(
    import_val_mga: float | None,
    import_vol_tons: float | None,
    unit_val: str = "MGA",
    unit_vol: str = "tons",
) -> tuple[float | None, str | None]:
    """Calculate CIF import unit cost in MGA/kg with physical unit compatibility check."""
    if unit_val != "MGA" or unit_vol != "tons":
        return None, REASON_INCOMPATIBLE_UNITS
    if import_vol_tons is None:
        return None, REASON_MISSING_DENOMINATOR
    if import_vol_tons <= 0.0:
        return None, REASON_ZERO_DENOMINATOR
    if import_val_mga is None:
        return None, REASON_MISSING_SERIES
    # Convert tonnes to kg (1 ton = 1000 kg)
    unit_cost = import_val_mga / (import_vol_tons * 1000.0)
    return round(unit_cost, 2), None


def calculate_import_dependency_ratio(
    import_tonnes: float | None,
    prod_tonnes: float | None,
    export_tonnes: float | None = 0.0,
    period_import: str | None = None,
    period_prod: str | None = None,
) -> tuple[float | None, str | None]:
    """Calculate import dependency ratio with temporal alignment check."""
    if period_import is not None and period_prod is not None and period_import != period_prod:
        return None, REASON_UNALIGNED_PERIOD
    if prod_tonnes is None or import_tonnes is None:
        return None, REASON_MISSING_DENOMINATOR
    net_avail = prod_tonnes + import_tonnes - (export_tonnes or 0.0)
    if net_avail <= 0.0:
        return None, REASON_ZERO_DENOMINATOR
    idr = import_tonnes / net_avail
    return round(idr, 4), None


def audit_inflation_vs_market_price_distinctness(
    cpi_food_chg_12m: float | None,
    market_price_chg_12m: float | None,
) -> dict[str, Any]:
    """Audit formal separation between CPI food inflation and direct market price variation."""
    return {
        "cpi_food_inflation_rate_pct": round(cpi_food_chg_12m * 100.0, 2) if cpi_food_chg_12m is not None else None,
        "market_price_variation_rate_pct": round(market_price_chg_12m * 100.0, 2) if market_price_chg_12m is not None else None,
        "spread_pct_points": (
            round((market_price_chg_12m - cpi_food_chg_12m) * 100.0, 2)
            if (cpi_food_chg_12m is not None and market_price_chg_12m is not None)
            else None
        ),
        "concepts_strictly_separated": True,
        "warning": (
            "CPI food measures an urban basket index while market price measures direct transaction per kg; "
            "they must never be merged or substituted."
        ),
    }


# =========================================================================
# DATA MODELS & QUERIES
# =========================================================================

@dataclass
class IndicatorObservationItem:
    """An evaluated observation for the economic dashboard."""

    indicator_code: str
    dimension: DimensionType
    title: str
    unit: str
    frequency: str
    geo_scope: str
    period_month: str
    current_value: float | None
    base_period: str | None
    chg_1m: float | None
    chg_12m: float | None
    null_reason: str | None = None
    source_id: str | None = None
    source_family: str | None = None
    is_administered: bool = False


@dataclass
class DimensionSummary:
    """Evaluation summary for a specific economic dimension."""

    dimension: DimensionType
    completeness: CompletenessStatus
    indicators: list[IndicatorObservationItem] = field(default_factory=list)


@dataclass
class EconomicDashboardResponse:
    """Consolidated economic dashboard response."""

    overall_status: CompletenessStatus
    period_month: str
    dimensions: dict[str, DimensionSummary]
    metric_catalog: dict[str, EconomicMetricCard]


def query_economic_dashboard_from_db(
    session: Session,
    target_month: date | None = None,
) -> list[IndicatorObservationItem]:
    """Query consolidated indicators from gold.economic_dashboard."""
    from ketrika.gold.provenance_gate import tables_for_views

    # Reject uncertified macro caches as well as newly requested publication.
    tables_for_views(["economic_dashboard"])
    sql = """
        SELECT
            ed.indicator_code,
            ed.dimension,
            ed.indicator_name,
            ed.unit,
            ed.frequency,
            ed.geo_scope,
            ed.period_month,
            ed.current_value::float,
            ed.base_period,
            ed.chg_1m::float,
            ed.chg_12m::float,
            ed.source_id,
            ed.source_family
        FROM gold.economic_dashboard ed
        WHERE 1=1
    """
    params: dict[str, Any] = {}
    if target_month:
        sql += " AND ed.period_month = :target_month"
        params["target_month"] = target_month
    sql += " ORDER BY ed.dimension, ed.indicator_code, ed.period_month DESC;"

    try:
        rows = session.execute(text(sql), params).fetchall()
    except Exception as exc:
        logger.warning("Could not query gold.economic_dashboard: %s", exc)
        return []

    items: list[IndicatorObservationItem] = []
    for r in rows:
        items.append(
            IndicatorObservationItem(
                indicator_code=r[0],
                dimension=r[1],
                title=r[2],
                unit=r[3],
                frequency=r[4],
                geo_scope=r[5],
                period_month=r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6]),
                current_value=float(r[7]) if r[7] is not None else None,
                base_period=r[8],
                chg_1m=float(r[9]) if r[9] is not None else None,
                chg_12m=float(r[10]) if r[10] is not None else None,
                source_id=r[11],
                source_family=r[12],
                is_administered=("FUEL_" in r[0]),
                null_reason=None if r[7] is not None else REASON_MISSING_SERIES,
            )
        )
    return items
