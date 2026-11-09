"""Normative market indicators and KPI calculation formulas (SPECS §16, MVP_EXECUTION_PLAN T5.2)."""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal


def calculate_variation(current_price: float, previous_price: float | None) -> float | None:
    """Calculate price variation chg_k = P_t / P_{t-k} - 1 (SPECS §16)."""
    if previous_price is None or previous_price <= 0:
        return None
    return round((current_price / previous_price) - 1.0, 4)


def _shift_month(d: date, lag_months: int) -> date:
    """Shift date backwards by exact lag_months, anchored to day 1."""
    total_months = d.year * 12 + (d.month - 1) - lag_months
    target_year = total_months // 12
    target_month = (total_months % 12) + 1
    return date(target_year, target_month, 1)


def calculate_calendar_aligned_variation(
    prices_by_month: Mapping[Any, float],
    current_month: date | str,
    lag_months: int,
) -> float | None:
    """Calculate variation strictly against the exact calendar month (current_month - lag_months).

    If there is a gap (month missing in prices_by_month), returns None.
    Never computes variation against an arbitrary previous available row.
    """
    if lag_months <= 0:
        raise ValueError("lag_months must be positive")

    curr_d = (
        current_month
        if isinstance(current_month, date)
        else date.fromisoformat(str(current_month)[:10])
    )
    curr_d = date(curr_d.year, curr_d.month, 1)

    target_d = _shift_month(curr_d, lag_months)

    norm_prices: dict[date, float] = {}
    for k, v in prices_by_month.items():
        kd = k if isinstance(k, date) else date.fromisoformat(str(k)[:10])
        norm_prices[date(kd.year, kd.month, 1)] = v

    if curr_d not in norm_prices or target_d not in norm_prices:
        return None

    return calculate_variation(norm_prices[curr_d], norm_prices[target_d])


KNOWN_DERIVATIONS: dict[str, str] = {
    "wfp_hdx_mdg": "un_wfp",
    "wb_rtfp_mdg": "un_wfp",  # WB RTFP relies on WFP primary data
}

ROOT_SOURCE_FAMILIES: dict[str, str] = {
    "wfp_hdx_mdg": "un_wfp",
    "wb_rtfp_mdg": "un_wfp",  # WB RTFP relies on WFP primary data
    "fao_fpma_mdg": "un_fao",  # FAO FPMA shares WFP / national primary data
    "miasa_odr": "madagascar_gov",
    "mincc_ppn": "madagascar_gov",
    "douanes_stats": "madagascar_gov",
    "instat_nipc": "madagascar_gov",
    "instat_tbe": "madagascar_gov",
    "faostat": "un_fao",
    "ecmwf_open": "ecmwf",
    "chc_chirps": "chc_ucsb",
    "dgm_bulletins": "dgm_madagascar",
    "fewsnet_ipc": "fewsnet",
    "nasa_power": "nasa",
}


def audit_source_family_independence(
    source_items: Sequence[dict[str, Any] | str],
) -> dict[str, Any]:
    """Audit source independence and prevent false multi-source corroboration (C3, SPECS §14, ADR-100).

    Identifies root source families and prevents counting derivative sources
    (such as WB RTFP deriving from WFP HDX) as independent confirmations.
    """
    sources: list[str] = []
    declared_families: list[str] = []
    root_families: set[str] = set()
    has_dependent_derivation = False

    for item in source_items:
        if isinstance(item, str):
            s_id = item
            fam = ROOT_SOURCE_FAMILIES.get(s_id, s_id)
            dep = None
        else:
            s_id = item.get("source_id", "")
            fam = item.get("source_family") or ROOT_SOURCE_FAMILIES.get(s_id, s_id)
            dep = item.get("source_dependency")

        if dep in ("wfp_fao", "fao_fpma") or s_id == "wb_rtfp_mdg":
            fam = "un_wfp"
            has_dependent_derivation = True

        sources.append(s_id)
        declared_families.append(fam)
        root_fam = ROOT_SOURCE_FAMILIES.get(s_id, fam)
        root_families.add(root_fam)

    source_set = set(sources)
    if "wb_rtfp_mdg" in source_set and ("wfp_hdx_mdg" in source_set or "fao_fpma_mdg" in source_set):
        has_dependent_derivation = True
    if "wfp_hdx_mdg" in source_set and "fao_fpma_mdg" in source_set:
        has_dependent_derivation = True

    return {
        "n_sources": len(sources),
        "sources": sources,
        "n_independent_families": len(root_families),
        "independent_families": sorted(root_families),
        "has_dependent_derivation": has_dependent_derivation,
        "is_truly_independent": len(root_families) == len(sources) and not has_dependent_derivation,
    }


def calculate_robust_volatility(prices: list[float], use_log: bool = False) -> float | None:
    """Calculate robust volatility vol_12 = MAD(prices ou log P sur 12 mois) / median (SPECS §16)."""
    valid = [p for p in prices if p > 0]
    if len(valid) < 3:
        return None

    med_raw = statistics.median(valid)
    if med_raw <= 0:
        return None

    if use_log:
        logs = [math.log(p) for p in valid]
        med_log = statistics.median(logs)
        mad_log = statistics.median([abs(x - med_log) for x in logs])
        return round(mad_log / med_raw, 4)
    else:
        mad = statistics.median([abs(p - med_raw) for p in valid])
        return round(mad / med_raw, 4)


def calculate_robust_z_score(current_price: float, prices_12m: list[float]) -> float | None:
    """Calculate robust z-score: z = (P_t - med_12) / (1.4826 * MAD_12) (SPECS §16)."""
    valid = [p for p in prices_12m if p > 0]
    if len(valid) < 3:
        return None

    med = statistics.median(valid)
    mad = statistics.median([abs(p - med) for p in valid])
    if mad == 0:
        return 0.0

    return round((current_price - med) / (1.4826 * mad), 4)


def calculate_import_dependency_ratio(
    production_t: float, imports_t: float, exports_t: float
) -> float | None:
    """Calculate Import Dependency Ratio: IDR = imports / (production + imports - exports) (SPECS §16)."""
    net_availability = production_t + imports_t - exports_t
    if net_availability <= 0:
        return None
    return round(imports_t / net_availability, 4)


def calculate_price_stability_score(vol_12: float | None) -> float | None:
    """Calculate price stability component score S_p (0-100) (SPECS §16).

    Formula: 100 * (1 - min(vol_12 / 0.30, 1)).
    """
    if vol_12 is None or vol_12 < 0:
        return None
    ratio = min(vol_12 / 0.30, 1.0)
    return round(100.0 * (1.0 - ratio), 2)


def calculate_affordability_score(chg_12m: float | None) -> float | None:
    """Calculate affordability component score A_f (0-100) (SPECS §16).

    Formula: 100 * (1 - min(max(chg_12m, 0) / 0.40, 1)).
    """
    if chg_12m is None:
        return None
    excess_inflation = max(chg_12m, 0.0)
    ratio = min(excess_inflation / 0.40, 1.0)
    return round(100.0 * (1.0 - ratio), 2)


def calculate_availability_score(
    stock_status: Literal["sufficient", "tight", "shortage", "unknown"] | str | None,
) -> float | None:
    """Calculate availability component score A_v (0-100) (SPECS §16).

    sufficient = 100, tight = 50, shortage = 0; à défaut composante absente.
    """
    if not stock_status:
        return None
    status_lower = stock_status.strip().lower()
    if status_lower == "sufficient":
        return 100.0
    elif status_lower == "tight":
        return 50.0
    elif status_lower == "shortage":
        return 0.0
    return None


def calculate_climate_risk_score(rain_anom_3m: float | None) -> float | None:
    """Calculate climate risk component score R_c (0-100) (SPECS §16).

    Formula: 100 * (1 - min(max(-rain_anom_3m, 0) / 0.50, 1)).
    """
    if rain_anom_3m is None:
        return None
    deficit = max(-rain_anom_3m, 0.0)
    ratio = min(deficit / 0.50, 1.0)
    return round(100.0 * (1.0 - ratio), 2)


@dataclass(frozen=True)
class MarketHealthScoreResult:
    """Composite Market Health Score and components (SPECS §16)."""

    score_stability: float | None
    score_affordability: float | None
    score_availability: float | None
    score_climate: float | None
    available_components: list[str]
    coverage: float
    composite_score: float | None


WEIGHT_STABILITY = 0.30
WEIGHT_AFFORDABILITY = 0.25
WEIGHT_AVAILABILITY = 0.25
WEIGHT_CLIMATE = 0.20


def calculate_market_health_score(
    vol_12: float | None = None,
    chg_12m: float | None = None,
    stock_status: str | None = None,
    rain_anom_3m: float | None = None,
    # Direct component scores override if already computed:
    score_stability: float | None = None,
    score_affordability: float | None = None,
    score_availability: float | None = None,
    score_climate: float | None = None,
) -> MarketHealthScoreResult:
    """Calculate composite Market Health Score (0-100) with weight renormalization and coverage threshold.

    Rules (SPECS §16):
    - Weights: Stability (0.30), Affordability (0.25), Availability (0.25), Climate (0.20).
    - If coverage < 0.50, composite_score MUST be None.
    - If coverage >= 0.50, composite_score = (sum of component * weight) / coverage.
    """
    s_p = (
        score_stability if score_stability is not None else calculate_price_stability_score(vol_12)
    )
    a_f = (
        score_affordability
        if score_affordability is not None
        else calculate_affordability_score(chg_12m)
    )
    a_v = (
        score_availability
        if score_availability is not None
        else calculate_availability_score(stock_status)
    )
    r_c = score_climate if score_climate is not None else calculate_climate_risk_score(rain_anom_3m)

    available_components: list[str] = []
    total_coverage = 0.0
    weighted_sum = 0.0

    if s_p is not None:
        available_components.append("stability")
        total_coverage += WEIGHT_STABILITY
        weighted_sum += s_p * WEIGHT_STABILITY

    if a_f is not None:
        available_components.append("affordability")
        total_coverage += WEIGHT_AFFORDABILITY
        weighted_sum += a_f * WEIGHT_AFFORDABILITY

    if a_v is not None:
        available_components.append("availability")
        total_coverage += WEIGHT_AVAILABILITY
        weighted_sum += a_v * WEIGHT_AVAILABILITY

    if r_c is not None:
        available_components.append("climate")
        total_coverage += WEIGHT_CLIMATE
        weighted_sum += r_c * WEIGHT_CLIMATE

    total_coverage = round(total_coverage, 2)

    composite: float | None = None
    if total_coverage >= 0.50 and total_coverage > 0:
        composite = round(weighted_sum / total_coverage, 2)

    return MarketHealthScoreResult(
        score_stability=s_p,
        score_affordability=a_f,
        score_availability=a_v,
        score_climate=r_c,
        available_components=available_components,
        coverage=total_coverage,
        composite_score=composite,
    )
