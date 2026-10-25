"""Supply forecasts use exact references and persisted arrivals (ADR-121)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ketrika.core.db import get_db
from ketrika.core.models.db import Location, Product, StockObservation
from ketrika.geo.contracts import CropCalendarRecord, load_crop_calendar
from ketrika.supply.decision_pilot import (
    DecisionPersona,
    DecisionPilotEngine,
    DecisionPilotReport,
    DecisionScenarioDefinition,
)
from ketrika.supply.peak_forecast import (
    CycleSufficiencyReport,
    SupplyPeakForecastEngine,
    SupplyWindowPrediction,
)

router = APIRouter(prefix="/v1/supply", tags=["supply"])


def _campaign_year(campaign: str) -> int:
    if len(campaign) != 4 or not campaign.isascii() or not campaign.isdigit():
        raise HTTPException(422, "La campagne doit être une année explicite YYYY.")
    year = int(campaign)
    if not 1900 <= year <= 2200:
        raise HTTPException(422, "Année de campagne hors limites.")
    return year


def _calendar(product: str, market: str, zone: str | None = None) -> CropCalendarRecord:
    matches = [
        record
        for record in load_crop_calendar()
        if record.product_code == product
        and (zone is None or record.zone_code == zone)
        and record.is_active
        and record.superseded_by is None
        and any(link.location_code == market for link in record.market_links)
    ]
    if not matches:
        raise HTTPException(404, "Aucun calendrier correspondant au produit, bassin et marché.")
    if len(matches) != 1:
        raise HTTPException(409, "Plusieurs calendriers possibles : sélection de cycle requise.")
    return matches[0]


def _arrivals(session: Session, market: str, product: str, cutoff: date) -> list[StockObservation]:
    """Only normalised physical inflows, never inventory or fuzzy location matches."""
    if session.query(Location).filter(Location.pcode == market).first() is None:
        raise HTTPException(404, "Marché inconnu.")
    if session.query(Product).filter(Product.product_code == product).first() is None:
        raise HTTPException(404, "Produit inconnu.")
    available_before = datetime.combine(cutoff + timedelta(days=1), time.min, tzinfo=UTC)
    return list(
        session.query(StockObservation)
        .join(Product, StockObservation.product_id == Product.product_id)
        .filter(
            Product.product_code == product,
            StockObservation.market_code == market,
            StockObservation.target == "inflow_arrival",
            StockObservation.superseded_by.is_(None),
            StockObservation.review_status == "accepted",
            StockObservation.base_unit == "kg",
            StockObservation.quantity_base.is_not(None),
            StockObservation.quantity_base >= 0,
            StockObservation.period_end <= cutoff,
            StockObservation.published_at < available_before,
            StockObservation.ingested_at < available_before,
        )
        .order_by(StockObservation.period_start)
        .all()
    )


@router.get("/peak-forecast", response_model=SupplyWindowPrediction)
def get_supply_peak_forecast(
    campaign: str = Query(..., description="Explicit campaign year YYYY"),
    crop: str = Query("RICE_PADDY"),
    zone_code: str = Query("ZONE_ALAOTRA"),
    market_code: str = Query("MDG_ANOSIBE"),
    logistics_lag_dekads: int = Query(1, ge=0, le=6),
    as_of_date: date | None = Query(None),
    session: Session = Depends(get_db),
) -> SupplyWindowPrediction:
    """Abstain until a verified calendar and independent validation are received."""
    year = _campaign_year(campaign)
    calendar = _calendar(crop, market_code, zone_code)
    arrivals = _arrivals(session, market_code, crop, as_of_date or date.today())
    # Existing baseline confidence is a heuristic, not a calibrated market forecast.
    # Keep the offline engine testable without publishing it as an operational peak.
    if not arrivals or not calendar.verified:
        raise HTTPException(409, "Arrivages vérifiés et calendrier documenté insuffisants.")
    raise HTTPException(
        409,
        f"Prévision de campagne {year} non qualifiée : validation indépendante requise.",
    )


@router.get("/sufficiency", response_model=CycleSufficiencyReport)
def get_data_sufficiency(
    market_code: str = Query("MDG_ANOSIBE"),
    product: str = Query("RICE_PADDY"),
    as_of_date: date | None = Query(None),
    session: Session = Depends(get_db),
) -> CycleSufficiencyReport:
    """Inspect one product and market using real columns; database errors propagate."""
    records = _arrivals(session, market_code, product, as_of_date or date.today())
    report = SupplyPeakForecastEngine().assess_data_sufficiency(records, min_cycles=2)
    return report.model_copy(
        update={
            "is_sufficient": False,
            "total_cycles_observed": 0.0,
            "assessment_note": "Cycles complets non établis. Dates et effectifs disponibles seulement ; complétude et validation indépendante non qualifiées.",
        }
    )


@router.get("/scenarios/templates", response_model=dict[str, DecisionScenarioDefinition])
def get_scenario_templates() -> dict[str, DecisionScenarioDefinition]:
    """Return editable hypotheses, not observed market facts."""
    return {
        key.value: value
        for key, value in DecisionPilotEngine().get_default_scenario_templates().items()
    }


@router.post("/scenarios/run", response_model=DecisionPilotReport)
def run_decision_scenario(
    scenario: DecisionScenarioDefinition,
    session: Session = Depends(get_db),
) -> DecisionPilotReport:
    """Reject unproven operational inputs instead of inserting demonstration facts."""
    _campaign_year(scenario.campaign)
    if scenario.persona == DecisionPersona.PUBLIC_REGULATOR:
        _arrivals(session, scenario.market_code, scenario.product_code, date.today())
        raise HTTPException(
            409,
            "Abstention : mois et corpus complet d'arrivages observés requis ; aucune valeur mensuelle implicite.",
        )
    calendar = _calendar(scenario.product_code, scenario.market_code)
    if not calendar.verified:
        raise HTTPException(409, "Calendrier non vérifié.")
    # Generic calendar citations have not yet passed documentary qualification (AU-18).
    # Do not reuse the first calendar or claim its fixed confidence is measured.
    raise HTTPException(
        409,
        "Scénario non qualifié : preuve documentaire du calendrier et validation des entrées requises.",
    )
