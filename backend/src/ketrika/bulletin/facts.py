"""Fact dictionary generator from Gold analytical views (SPECS §20)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.core.logging import get_logger
from ketrika.core.registry import load_sources

logger = get_logger(__name__)


def format_fr_number(val: float | int, decimals: int = 0) -> str:
    """Format number with French spacing (narrow non-breaking space)."""
    if decimals == 0:
        s = f"{int(round(val)):,}".replace(",", " ")
    else:
        parts = f"{val:.{decimals}f}".split(".")
        int_part = f"{int(parts[0]):,}".replace(",", " ")
        s = f"{int_part},{parts[1]}"
    return s


def build_bulletin_facts(
    session: Session,
    period_start: date,
    period_end: date,
) -> dict[str, dict[str, Any]]:
    """Build a deterministic dictionary of market intelligence facts from Gold layer.

    Each fact conforms to SPECS §20:
    {
        "f001": {
            "label": "Prix médian riz blanc local, détail, Analamanga, sept. 2026",
            "value": 2850,
            "unit": "Ar/kg",
            "display": "2 850 Ar/kg",
            "sources": ["miasa_odr", "wfp_hdx_mdg"],
            "observation_ids": ["..."]
        }
    }
    """
    facts: dict[str, dict[str, Any]] = {}
    fact_counter = 1

    def next_key() -> str:
        nonlocal fact_counter
        k = f"f{fact_counter:03d}"
        fact_counter += 1
        return k

    # 1. Macro / Synthesis Facts: National rice prices & variations
    query_rice_nat = text(
        """
        SELECT
            pc.product_code,
            pc.product_name,
            pc.median_price,
            pc.chg_1m,
            pc.chg_12m,
            pc.chosen_source_id,
            ARRAY_AGG(pobs.observation_id) FILTER (WHERE pobs.observation_id IS NOT NULL) AS obs_ids
        FROM gold.price_changes pc
        LEFT JOIN gold.price_obs_current pobs
          ON pc.product_id = pobs.product_id
         AND pc.location_id = pobs.location_id
         AND pc.actor_level = pobs.actor_level
         AND pc.month = date_trunc('month', pobs.period_start)::date
        WHERE pc.product_code = 'rice_milled_local'
          AND pc.admin_level = 0
          AND pc.actor_level = 'retail'
        GROUP BY pc.product_code, pc.product_name, pc.median_price, pc.chg_1m, pc.chg_12m, pc.chosen_source_id
        ORDER BY pc.median_price DESC
        LIMIT 1;
        """
    )
    row_rice = session.execute(query_rice_nat).fetchone()
    if row_rice:
        price_val = float(row_rice.median_price)
        obs_ids = [str(o) for o in (row_rice.obs_ids or [])][:5]
        facts[next_key()] = {
            "label": "Prix médian national du riz blanc local au détail",
            "value": price_val,
            "unit": "Ar/kg",
            "display": f"{format_fr_number(price_val)} Ar/kg",
            "sources": [row_rice.chosen_source_id] if row_rice.chosen_source_id else ["miasa_odr"],
            "observation_ids": obs_ids,
        }
        if row_rice.chg_1m is not None:
            chg_val = float(row_rice.chg_1m) * 100
            facts[next_key()] = {
                "label": "Variation mensuelle du prix médian national du riz blanc local",
                "value": chg_val,
                "unit": "%",
                "display": f"{'+' if chg_val >= 0 else ''}{format_fr_number(chg_val, 1)} %",
                "sources": [row_rice.chosen_source_id]
                if row_rice.chosen_source_id
                else ["miasa_odr"],
                "observation_ids": obs_ids,
            }

    # 2. Market Health Score fact
    query_mh = text(
        """
        SELECT
            mh.product_code,
            mh.product_name,
            mh.location_name,
            mh.market_health_score,
            mh.score_stability,
            mh.score_affordability,
            mh.coverage
        FROM gold.market_health mh
        WHERE mh.market_health_score IS NOT NULL
        ORDER BY mh.month DESC, mh.market_health_score ASC
        LIMIT 1;
        """
    )
    row_mh = session.execute(query_mh).fetchone()
    if row_mh:
        score_val = float(row_mh.market_health_score)
        facts[next_key()] = {
            "label": f"Score de santé du marché ({row_mh.product_name} en région {row_mh.location_name})",
            "value": score_val,
            "unit": "/100",
            "display": f"{format_fr_number(score_val, 0)}/100",
            "sources": ["ketrika_kpi"],
            "observation_ids": [],
        }

    # 3. Regional Price Disparities (Highest vs Lowest Region)
    query_reg = text(
        """
        SELECT
            pc.product_code,
            pc.product_name,
            pc.location_name,
            pc.median_price,
            pc.chosen_source_id,
            ARRAY_AGG(pobs.observation_id) FILTER (WHERE pobs.observation_id IS NOT NULL) AS obs_ids
        FROM gold.price_changes pc
        LEFT JOIN gold.price_obs_current pobs
          ON pc.product_id = pobs.product_id
         AND pc.location_id = pobs.location_id
         AND pc.actor_level = pobs.actor_level
         AND pc.month = date_trunc('month', pobs.period_start)::date
        WHERE pc.product_code = 'rice_milled_local'
          AND pc.admin_level = 1
        GROUP BY pc.product_code, pc.product_name, pc.location_name, pc.median_price, pc.chosen_source_id
        ORDER BY pc.median_price DESC;
        """
    )
    rows_reg = session.execute(query_reg).fetchall()
    if rows_reg:
        high_reg = rows_reg[0]
        low_reg = rows_reg[-1]
        facts[next_key()] = {
            "label": f"Prix le plus élevé observé en région ({high_reg.location_name})",
            "value": float(high_reg.median_price),
            "unit": "Ar/kg",
            "display": f"{format_fr_number(float(high_reg.median_price))} Ar/kg",
            "sources": [high_reg.chosen_source_id] if high_reg.chosen_source_id else ["miasa_odr"],
            "observation_ids": [str(o) for o in (high_reg.obs_ids or [])][:3],
        }
        if low_reg.location_name != high_reg.location_name:
            facts[next_key()] = {
                "label": f"Prix le plus bas observé en région ({low_reg.location_name})",
                "value": float(low_reg.median_price),
                "unit": "Ar/kg",
                "display": f"{format_fr_number(float(low_reg.median_price))} Ar/kg",
                "sources": [low_reg.chosen_source_id]
                if low_reg.chosen_source_id
                else ["miasa_odr"],
                "observation_ids": [str(o) for o in (low_reg.obs_ids or [])][:3],
            }

    # 4. Other PPN Products (Maize, Cassava, Oil, Sugar)
    query_ppn = text(
        """
        SELECT
            pc.product_code,
            pc.product_name,
            pc.median_price,
            pc.chg_1m,
            pc.chosen_source_id,
            ARRAY_AGG(pobs.observation_id) FILTER (WHERE pobs.observation_id IS NOT NULL) AS obs_ids
        FROM gold.price_changes pc
        LEFT JOIN gold.price_obs_current pobs
          ON pc.product_id = pobs.product_id
         AND pc.location_id = pobs.location_id
         AND pc.month = date_trunc('month', pobs.period_start)::date
        WHERE pc.product_code IN ('maize', 'cassava_fresh', 'oil_edible', 'sugar')
          AND pc.median_price IS NOT NULL
        GROUP BY pc.product_code, pc.product_name, pc.median_price, pc.chg_1m, pc.chosen_source_id
        LIMIT 4;
        """
    )
    for r in session.execute(query_ppn).fetchall():
        facts[next_key()] = {
            "label": f"Prix médian national : {r.product_name}",
            "value": float(r.median_price),
            "unit": "Ar/kg",
            "display": f"{format_fr_number(float(r.median_price))} Ar/kg",
            "sources": [r.chosen_source_id] if r.chosen_source_id else ["mincc_ppn"],
            "observation_ids": [str(o) for o in (r.obs_ids or [])][:2],
        }

    # 5. Stocks Facts
    query_stocks = text(
        """
        SELECT
            sl.product_name,
            sl.location_name,
            sl.stock_status,
            sl.coverage_days
        FROM gold.stock_latest sl
        WHERE sl.coverage_days IS NOT NULL
        LIMIT 2;
        """
    )
    for r in session.execute(query_stocks).fetchall():
        days_val = float(r.coverage_days)
        facts[next_key()] = {
            "label": f"Couverture des stocks de {r.product_name} à {r.location_name}",
            "value": days_val,
            "unit": "jours",
            "display": f"{format_fr_number(days_val)} jours",
            "sources": ["mincc_ppn"],
            "observation_ids": [],
        }

    # 6. Active Alerts Count
    query_alerts = text(
        """
        SELECT count(*) AS n_alerts FROM ops.alert WHERE state = 'open';
        """
    )
    n_alerts = int(session.execute(query_alerts).scalar() or 0)
    facts[next_key()] = {
        "label": "Nombre d'alertes de marché actuellement ouvertes",
        "value": n_alerts,
        "unit": "alertes",
        "display": f"{n_alerts} alerte{'s' if n_alerts > 1 else ''}",
        "sources": ["ketrika_alerts"],
        "observation_ids": [],
    }

    # 7. Sources and Attributions
    all_sources = load_sources()
    citations = [f"{s.name} ({s.owner})" for s in all_sources if s.priority in ("P0", "P1")]
    facts["sources_attribution"] = {
        "label": "Sources officielles et institutionnelles collectées",
        "value": len(citations),
        "unit": "sources",
        "display": ", ".join(citations[:4]),
        "sources": [s.source_id for s in all_sources if s.priority in ("P0", "P1")],
        "observation_ids": [],
    }

    return facts
