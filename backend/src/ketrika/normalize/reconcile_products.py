"""Reconcile legacy lowercase product codes into canonical uppercase PPN taxonomy (ADR-140).

Transfers active price, stock, and trade observations from legacy test codes
(maize, cassava_fresh, oil_edible, flour_wheat, dry_beans, sugar, rice_imported, rice_milled, cassava_dry)
to the canonical products (MAIZE_GRAIN, CASSAVA_FRESH, VEG_OIL, etc.) via immutable supersession (Rule 4.3).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ketrika.core.db import get_session
from ketrika.core.models.db import PriceObservation, Product, StockObservation, TradeFlow
from ketrika.gold.refresh import refresh_gold_views

logger = logging.getLogger("ketrika.reconcile_products")

CODE_MAPPING: dict[str, str] = {
    "maize": "MAIZE_GRAIN",
    "cassava_fresh": "CASSAVA_FRESH",
    "cassava_dry": "CASSAVA_DRIED",
    "oil_edible": "VEG_OIL",
    "flour_wheat": "WHEAT_FLOUR",
    "dry_beans": "BEANS_DRY",
    "sugar": "SUGAR",
    "rice_imported": "RICE_WHITE_IMPORTED",
    "rice_milled": "RICE_WHITE_LOCAL",
}


def reconcile_products(session: Session) -> dict[str, int]:
    """Reconcile legacy observations by superseding them with canonical product references."""
    # 1. Load canonical products map
    canonical_products = (
        session.execute(
            select(Product).where(Product.product_code.in_(set(CODE_MAPPING.values())))
        )
        .scalars()
        .all()
    )
    canonical_by_code: dict[str, Product] = {p.product_code: p for p in canonical_products}

    legacy_products = (
        session.execute(
            select(Product).where(Product.product_code.in_(set(CODE_MAPPING.keys())))
        )
        .scalars()
        .all()
    )
    legacy_by_code: dict[str, Product] = {p.product_code: p for p in legacy_products}

    reconciled_prices = 0
    reconciled_stocks = 0
    reconciled_trades = 0

    # Cache existing active natural keys to prevent unique violation
    active_price_nks: dict[str, uuid.UUID] = {
        row[0]: row[1]
        for row in session.execute(
            select(PriceObservation.natural_key, PriceObservation.observation_id).where(
                PriceObservation.superseded_by.is_(None)
            )
        ).all()
    }

    # 2. Reconcile Price Observations
    for legacy_code, target_code in CODE_MAPPING.items():
        legacy_prod = legacy_by_code.get(legacy_code)
        target_prod = canonical_by_code.get(target_code)
        if not legacy_prod or not target_prod:
            continue

        stmt = select(PriceObservation).where(
            PriceObservation.product_id == legacy_prod.product_id,
            PriceObservation.superseded_by.is_(None),
        )
        legacy_obs = list(session.execute(stmt).scalars().all())

        for old_obs in legacy_obs:
            nk_parts = (old_obs.natural_key or "").split("|")
            if nk_parts and len(nk_parts) >= 4:
                new_nk = f"{target_code}|{nk_parts[1]}|{nk_parts[2]}|{nk_parts[3]}"
            else:
                new_nk = f"{target_code}|{old_obs.location_id}|{old_obs.actor_level}|{old_obs.period_start}"

            if new_nk in active_price_nks:
                # Existing active canonical row already present; supersede legacy to it
                old_obs.superseded_by = active_price_nks[new_nk]
                reconciled_prices += 1
                continue

            new_id = uuid.uuid4()
            ev = dict(old_obs.evidence or {})
            ev["reconciled_from"] = legacy_code
            ev["reconciliation_adr"] = "ADR-140"

            old_obs.superseded_by = new_id
            active_price_nks[new_nk] = new_id

            new_obs = PriceObservation(
                observation_id=new_id,
                source_record_id=old_obs.source_record_id,
                natural_key=new_nk,
                product_raw=old_obs.product_raw,
                product_id=target_prod.product_id,
                variety=old_obs.variety,
                quality_grade=old_obs.quality_grade,
                location_raw=old_obs.location_raw,
                location_id=old_obs.location_id,
                market_name=old_obs.market_name,
                actor_level=old_obs.actor_level,
                period_start=old_obs.period_start,
                period_end=old_obs.period_end,
                published_at=old_obs.published_at,
                ingested_at=old_obs.ingested_at,
                price_raw=old_obs.price_raw,
                price_value=old_obs.price_value,
                currency_raw=old_obs.currency_raw,
                unit_raw=old_obs.unit_raw,
                package_quantity=old_obs.package_quantity,
                package_unit=old_obs.package_unit,
                price_mga_per_base=old_obs.price_mga_per_base,
                base_unit=old_obs.base_unit or target_prod.base_unit,
                conversion_status=old_obs.conversion_status,
                observed_or_imputed=old_obs.observed_or_imputed,
                missing_code=old_obs.missing_code,
                extraction_method=old_obs.extraction_method,
                evidence=ev,
                confidence=old_obs.confidence,
                review_status=old_obs.review_status,
                superseded_by=None,
            )
            session.add(new_obs)
            reconciled_prices += 1

    # Cache active stock keys: (natural_key, target)
    active_stock_keys: dict[tuple[str, str], uuid.UUID] = {
        (row[0], row[1]): row[2]
        for row in session.execute(
            select(StockObservation.natural_key, StockObservation.target, StockObservation.observation_id).where(
                StockObservation.superseded_by.is_(None)
            )
        ).all()
    }

    # 3. Reconcile Stock Observations
    for legacy_code, target_code in CODE_MAPPING.items():
        legacy_prod = legacy_by_code.get(legacy_code)
        target_prod = canonical_by_code.get(target_code)
        if not legacy_prod or not target_prod:
            continue

        stmt_s = select(StockObservation).where(
            StockObservation.product_id == legacy_prod.product_id,
            StockObservation.superseded_by.is_(None),
        )
        legacy_stocks = list(session.execute(stmt_s).scalars().all())

        for old_stk in legacy_stocks:
            nk_parts = (old_stk.natural_key or "").split("|")
            if nk_parts and len(nk_parts) >= 3:
                new_nk = f"{target_code}|{nk_parts[1]}|{nk_parts[2]}"
            else:
                new_nk = f"{target_code}|{old_stk.location_id}|{old_stk.period_start}"

            stk_key = (new_nk, old_stk.target)
            if stk_key in active_stock_keys:
                old_stk.superseded_by = active_stock_keys[stk_key]
                reconciled_stocks += 1
                continue

            new_id = uuid.uuid4()
            ev = dict(old_stk.evidence or {})
            ev["reconciled_from"] = legacy_code
            ev["reconciliation_adr"] = "ADR-140"
            old_stk.superseded_by = new_id
            active_stock_keys[stk_key] = new_id

            new_stk = StockObservation(
                observation_id=new_id,
                source_record_id=old_stk.source_record_id,
                natural_key=new_nk,
                product_raw=old_stk.product_raw,
                product_id=target_prod.product_id,
                location_raw=old_stk.location_raw,
                location_id=old_stk.location_id,
                period_start=old_stk.period_start,
                period_end=old_stk.period_end,
                published_at=old_stk.published_at,
                ingested_at=old_stk.ingested_at,
                quantity_raw=old_stk.quantity_raw,
                quantity_value=old_stk.quantity_value,
                unit_raw=old_stk.unit_raw,
                quantity_base=old_stk.quantity_base,
                base_unit=old_stk.base_unit or target_prod.base_unit,
                stock_status=old_stk.stock_status,
                coverage_days=old_stk.coverage_days,
                target=old_stk.target,
                measurement_mode=old_stk.measurement_mode,
                market_type=old_stk.market_type,
                market_code=old_stk.market_code,
                extraction_method=old_stk.extraction_method,
                evidence=ev,
                confidence=old_stk.confidence,
                review_status=old_stk.review_status,
                superseded_by=None,
            )
            session.add(new_stk)
            reconciled_stocks += 1

    # Cache active trade keys
    active_trade_nks: dict[str, uuid.UUID] = {
        row[0]: row[1]
        for row in session.execute(
            select(TradeFlow.natural_key, TradeFlow.observation_id).where(
                TradeFlow.superseded_by.is_(None)
            )
        ).all()
    }

    # 4. Reconcile Trade Flow Observations
    for legacy_code, target_code in CODE_MAPPING.items():
        legacy_prod = legacy_by_code.get(legacy_code)
        target_prod = canonical_by_code.get(target_code)
        if not legacy_prod or not target_prod:
            continue

        stmt_t = select(TradeFlow).where(
            TradeFlow.product_id == legacy_prod.product_id,
            TradeFlow.superseded_by.is_(None),
        )
        legacy_trades = list(session.execute(stmt_t).scalars().all())

        for old_tr in legacy_trades:
            nk_parts = (old_tr.natural_key or "").split("|")
            if nk_parts and len(nk_parts) >= 4:
                new_nk = f"{target_code}|{nk_parts[1]}|{nk_parts[2]}|{nk_parts[3]}"
            else:
                new_nk = f"{target_code}|{old_tr.flow}|{old_tr.partner_iso3}|{old_tr.period_start}"

            if new_nk in active_trade_nks:
                old_tr.superseded_by = active_trade_nks[new_nk]
                reconciled_trades += 1
                continue

            new_id = uuid.uuid4()
            ev = dict(old_tr.evidence or {})
            ev["reconciled_from"] = legacy_code
            ev["reconciliation_adr"] = "ADR-140"
            old_tr.superseded_by = new_id
            active_trade_nks[new_nk] = new_id

            new_tr = TradeFlow(
                observation_id=new_id,
                source_record_id=old_tr.source_record_id,
                natural_key=new_nk,
                flow=old_tr.flow,
                hs_code=old_tr.hs_code,
                product_raw=old_tr.product_raw,
                product_id=target_prod.product_id,
                partner_raw=old_tr.partner_raw,
                partner_iso3=old_tr.partner_iso3,
                period_start=old_tr.period_start,
                period_end=old_tr.period_end,
                published_at=old_tr.published_at,
                ingested_at=old_tr.ingested_at,
                value_raw=old_tr.value_raw,
                value_mga=old_tr.value_mga,
                value_usd=old_tr.value_usd,
                weight_raw=old_tr.weight_raw,
                weight_kg=old_tr.weight_kg,
                extraction_method=old_tr.extraction_method,
                evidence=ev,
                confidence=old_tr.confidence,
                review_status=old_tr.review_status,
                superseded_by=None,
            )
            session.add(new_tr)
            reconciled_trades += 1

    session.flush()
    return {
        "prices_reconciled": reconciled_prices,
        "stocks_reconciled": reconciled_stocks,
        "trades_reconciled": reconciled_trades,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with get_session() as session:
        with session.begin():
            stats = reconcile_products(session)
            print(f"Reconciliation completed successfully: {stats}")


if __name__ == "__main__":
    main()
