"""Supply balance engine with mass conservation and non-double-counting (R5.6, ADR-092, SPECS §27).

This module constructs strict supply balances for Madagascar food commodities:
1. Physical mass conservation: Stock_end = Stock_start + Inflows - Outflows - Sales - Losses.
2. Formal prevention of customs trade flows double-counting with physical wholesale market arrivals.
3. Strict separation: static inventory stocks are never summed with periodic inflow arrivals.
4. Metrological principle: UNKNOWN COMPONENT REMAINS UNKNOWN (unobserved sales/losses prevent false completeness).
5. Distinct typology: Observed Partial Balance (facts only) vs Scenario Simulation (explicit versioned assumptions).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ketrika.connectors.records import StockRecord, TradeFlowRecord
from ketrika.core.models.db import StockObservation, TradeFlow
from ketrika.supply.contracts import QuantityTarget


class BalanceType(StrEnum):
    """Typology distinguishing purely observed facts from simulated scenarios."""

    OBSERVED_PARTIAL = "observed_partial"
    SCENARIO_SIMULATION = "scenario_simulation"


class BalanceTerm(BaseModel):
    """Individual term in the physical supply balance."""

    model_config = ConfigDict(frozen=True)

    term_name: str
    quantity_kg: float | None = None
    is_observed: bool
    source_record_id: str | None = None
    assumption_id: str | None = None
    notes: str | None = None


class ScenarioAssumption(BaseModel):
    """Versioned explicit hypothesis for missing supply components."""

    model_config = ConfigDict(frozen=True)

    assumption_id: str
    parameter_name: str
    parameter_value: float
    unit: str
    rationale: str
    author: str = "analyst_simulation"


class SupplyBalanceReport(BaseModel):
    """Comprehensive mass-conserving supply balance report."""

    model_config = ConfigDict(frozen=True)

    market_or_basin_code: str
    product_raw: str
    period_start: date
    period_end: date
    balance_type: BalanceType
    terms: dict[str, BalanceTerm]
    has_unobserved_terms: bool
    observed_inflows_total_kg: float
    observed_outflows_total_kg: float
    net_inflow_surplus_kg: float | None = None
    initial_stock_kg: float | None = None
    final_stock_kg: float | None = None
    delta_stock_kg: float | None = None
    mass_conservation_holds: bool | None = None
    mass_discrepancy_kg: float | None = None
    double_counting_alerts: list[str] = Field(default_factory=list)
    methodology_summary: str


class SupplyBalanceEngine:
    """Scientific supply balance engine strictly enforcing mass conservation and non-double-counting."""

    @staticmethod
    def _extract_stock_attrs(rec: StockRecord | StockObservation) -> dict[str, Any]:
        """Extract standardized attributes from StockRecord or DB StockObservation."""
        if isinstance(rec, StockRecord):
            return {
                "target": rec.target or QuantityTarget.STOCK_INVENTORY.value,
                "market_code": rec.market_code or "UNKNOWN",
                "product_raw": rec.product_raw,
                "period_start": rec.period_start,
                "period_end": rec.period_end,
                "quantity_value": rec.quantity_value,
                "source_record_id": None,
            }
        return {
            "target": getattr(rec, "target", None) or QuantityTarget.STOCK_INVENTORY.value,
            "market_code": getattr(rec, "market_code", None) or "UNKNOWN",
            "product_raw": rec.product_raw,
            "period_start": rec.period_start,
            "period_end": rec.period_end,
            "quantity_value": float(rec.quantity_value) if rec.quantity_value is not None else None,
            "source_record_id": str(rec.source_record_id) if getattr(rec, "source_record_id", None) else None,
        }

    def check_customs_vs_market_double_count(
        self,
        market_arrivals: Sequence[StockRecord | StockObservation],
        customs_imports: Sequence[TradeFlowRecord | TradeFlow],
    ) -> list[str]:
        """Detect and forbid summing national customs imports with local wholesale market arrivals."""
        alerts: list[str] = []
        if market_arrivals and customs_imports:
            alerts.append(
                "DOUBLE_COUNT_HAZARD: Combining national customs trade flows with physical market arrivals. "
                "Imported food commodities cleared at port (e.g. Toamasina) already constitute the cargo of wholesale "
                "trucks arriving at destination markets (e.g. Anosibe). They must NOT be summed together."
            )
        return alerts

    def compute_observed_partial_balance(
        self,
        market_or_basin_code: str,
        product_raw: str,
        period_start: date,
        period_end: date,
        records: Sequence[StockRecord | StockObservation],
        customs_records: Sequence[TradeFlowRecord | TradeFlow] | None = None,
    ) -> SupplyBalanceReport:
        """Compute verified observed partial supply balance strictly using empirical facts.

        Any component not surveyed (e.g. retail sales, post-harvest losses) is left as None.
        Unknown component remains unknown.
        """
        double_count_alerts = self.check_customs_vs_market_double_count(
            records, customs_records or []
        )

        inflows_kg = 0.0
        outflows_kg = 0.0
        initial_stock: float | None = None
        final_stock: float | None = None

        initial_stock_id: str | None = None
        final_stock_id: str | None = None

        # Filter relevant records
        relevant: list[dict[str, Any]] = []
        for r in records:
            attrs = self._extract_stock_attrs(r)
            if attrs["market_code"] != market_or_basin_code:
                continue
            if product_raw.lower() not in attrs["product_raw"].lower():
                continue
            relevant.append(attrs)

        stock_records: list[dict[str, Any]] = []
        for attrs in relevant:
            q = attrs["quantity_value"] or 0.0
            tgt = attrs["target"]
            p_s = attrs["period_start"]
            p_e = attrs["period_end"]

            if tgt in (QuantityTarget.INFLOW_ARRIVAL.value, QuantityTarget.HARVEST_VOLUME.value):
                if p_s <= period_end and p_e >= period_start:
                    inflows_kg += q
            elif tgt == QuantityTarget.OUTFLOW_SALES.value:
                if p_s <= period_end and p_e >= period_start:
                    outflows_kg += q
            elif tgt == QuantityTarget.STOCK_INVENTORY.value:
                stock_records.append(attrs)

        # Identify initial stock: inventory record closest to period_start (at or before period_start)
        best_init: dict[str, Any] | None = None
        initial_candidates = [
            s for s in stock_records
            if s["period_start"] <= period_start or s["period_end"] <= period_start
        ]
        if initial_candidates:
            initial_candidates.sort(key=lambda s: abs((s["period_end"] - period_start).days))
            best_init = initial_candidates[0]
            initial_stock = best_init["quantity_value"]
            initial_stock_id = best_init["source_record_id"]

        # Identify final stock: inventory record closest to period_end
        final_candidates = [
            s for s in stock_records
            if s is not best_init and (s["period_end"] >= period_end or s["period_start"] >= period_start)
        ]
        if final_candidates:
            final_candidates.sort(key=lambda s: abs((s["period_end"] - period_end).days))
            best_final = final_candidates[0]
            final_stock = best_final["quantity_value"]
            final_stock_id = best_final["source_record_id"]

        terms: dict[str, BalanceTerm] = {
            "initial_stock": BalanceTerm(
                term_name="initial_stock",
                quantity_kg=initial_stock,
                is_observed=initial_stock is not None,
                source_record_id=initial_stock_id,
                notes="Observed baseline physical stock inventory at period start",
            ),
            "inflow_arrivals": BalanceTerm(
                term_name="inflow_arrivals",
                quantity_kg=inflows_kg,
                is_observed=True,
                notes=f"Sum of observed physical market inflows over interval ({inflows_kg:,.1f} kg)",
            ),
            "outflow_sales": BalanceTerm(
                term_name="outflow_sales",
                quantity_kg=outflows_kg if outflows_kg > 0 else None,
                is_observed=outflows_kg > 0,
                notes="Observed formal commercial market sales" if outflows_kg > 0 else "Unobserved: informal retail sales not surveyed",
            ),
            "post_harvest_losses": BalanceTerm(
                term_name="post_harvest_losses",
                quantity_kg=None,  # STRICT: never guess losses in observed balance
                is_observed=False,
                notes="Unobserved: post-harvest physical spoilage not directly measured on market",
            ),
            "final_stock": BalanceTerm(
                term_name="final_stock",
                quantity_kg=final_stock,
                is_observed=final_stock is not None,
                source_record_id=final_stock_id,
                notes="Observed ending stock inventory at period end",
            ),
        }

        has_unobserved = any(not t.is_observed for t in terms.values())

        # Net surplus of observed flows
        net_surplus = (inflows_kg - outflows_kg) if outflows_kg > 0 else None

        # Check mass conservation only if both stocks and flows are fully observed
        mass_holds: bool | None = None
        discrepancy: float | None = None
        delta_stock: float | None = None

        if initial_stock is not None and final_stock is not None:
            delta_stock = final_stock - initial_stock
            if outflows_kg > 0:
                expected_delta = inflows_kg - outflows_kg
                discrepancy = abs(delta_stock - expected_delta)
                mass_holds = discrepancy <= 1e-2

        return SupplyBalanceReport(
            market_or_basin_code=market_or_basin_code,
            product_raw=product_raw,
            period_start=period_start,
            period_end=period_end,
            balance_type=BalanceType.OBSERVED_PARTIAL,
            terms=terms,
            has_unobserved_terms=has_unobserved,
            observed_inflows_total_kg=round(inflows_kg, 2),
            observed_outflows_total_kg=round(outflows_kg, 2),
            net_inflow_surplus_kg=round(net_surplus, 2) if net_surplus is not None else None,
            initial_stock_kg=initial_stock,
            final_stock_kg=final_stock,
            delta_stock_kg=round(delta_stock, 2) if delta_stock is not None else None,
            mass_conservation_holds=mass_holds,
            mass_discrepancy_kg=round(discrepancy, 2) if discrepancy is not None else None,
            double_counting_alerts=double_count_alerts,
            methodology_summary=(
                "Pure empirical balance based on verified physical records. "
                "Unobserved terms (post-harvest losses, unmonitored retail sales) are strictly left empty."
            ),
        )

    def simulate_scenario_balance(
        self,
        market_or_basin_code: str,
        product_raw: str,
        period_start: date,
        period_end: date,
        records: Sequence[StockRecord | StockObservation],
        assumptions: Sequence[ScenarioAssumption],
    ) -> SupplyBalanceReport:
        """Simulate complete supply balance under explicit parameterized scenario assumptions.

        Strictly tagged as SCENARIO_SIMULATION, clearly distinguishing models from observations.
        """
        # Start from observed facts
        partial = self.compute_observed_partial_balance(
            market_or_basin_code, product_raw, period_start, period_end, records
        )

        inflows_kg = partial.observed_inflows_total_kg
        initial_stock_kg = partial.initial_stock_kg or 0.0

        # Extract assumption parameters
        loss_rate_pct = 0.0
        daily_sales_kg = 0.0
        assump_map = {a.parameter_name: a for a in assumptions}

        if "post_harvest_loss_rate_pct" in assump_map:
            loss_rate_pct = assump_map["post_harvest_loss_rate_pct"].parameter_value
        if "daily_market_sales_kg" in assump_map:
            daily_sales_kg = assump_map["daily_market_sales_kg"].parameter_value

        duration_days = (period_end - period_start).days + 1
        simulated_sales_kg = daily_sales_kg * duration_days
        simulated_losses_kg = inflows_kg * (loss_rate_pct / 100.0)

        # Theoretical ending stock under mass conservation:
        # Stock_end = Stock_start + Inflows - Sales - Losses
        simulated_final_stock_kg = max(
            0.0,
            initial_stock_kg + inflows_kg - simulated_sales_kg - simulated_losses_kg,
        )

        sim_terms: dict[str, BalanceTerm] = {
            "initial_stock": BalanceTerm(
                term_name="initial_stock",
                quantity_kg=initial_stock_kg,
                is_observed=partial.initial_stock_kg is not None,
                notes="Observed initial stock or simulated default 0 kg",
            ),
            "inflow_arrivals": BalanceTerm(
                term_name="inflow_arrivals",
                quantity_kg=inflows_kg,
                is_observed=True,
                notes="Empirical observed inflows",
            ),
            "outflow_sales": BalanceTerm(
                term_name="outflow_sales",
                quantity_kg=round(simulated_sales_kg, 2),
                is_observed=False,
                assumption_id=assump_map.get("daily_market_sales_kg", ScenarioAssumption(
                    assumption_id="default_sales",
                    parameter_name="daily_market_sales_kg",
                    parameter_value=daily_sales_kg,
                    unit="kg/day",
                    rationale="Assumed daily consumption rate",
                )).assumption_id,
                notes=f"Simulated sales ({daily_sales_kg:,.0f} kg/day over {duration_days} days)",
            ),
            "post_harvest_losses": BalanceTerm(
                term_name="post_harvest_losses",
                quantity_kg=round(simulated_losses_kg, 2),
                is_observed=False,
                assumption_id=assump_map.get("post_harvest_loss_rate_pct", ScenarioAssumption(
                    assumption_id="default_losses",
                    parameter_name="post_harvest_loss_rate_pct",
                    parameter_value=loss_rate_pct,
                    unit="percent",
                    rationale="Standard FAO post-harvest loss rate",
                )).assumption_id,
                notes=f"Simulated loss rate ({loss_rate_pct:.1f}% of inflows)",
            ),
            "final_stock": BalanceTerm(
                term_name="final_stock",
                quantity_kg=round(simulated_final_stock_kg, 2),
                is_observed=False,
                notes="Calculated theoretical ending stock enforcing physical mass conservation",
            ),
        }

        delta_stock = simulated_final_stock_kg - initial_stock_kg
        expected_delta = inflows_kg - simulated_sales_kg - simulated_losses_kg
        discrepancy = abs(delta_stock - expected_delta)
        mass_holds = discrepancy <= 1e-2

        return SupplyBalanceReport(
            market_or_basin_code=market_or_basin_code,
            product_raw=product_raw,
            period_start=period_start,
            period_end=period_end,
            balance_type=BalanceType.SCENARIO_SIMULATION,
            terms=sim_terms,
            has_unobserved_terms=True,
            observed_inflows_total_kg=round(inflows_kg, 2),
            observed_outflows_total_kg=round(simulated_sales_kg, 2),
            net_inflow_surplus_kg=round(inflows_kg - simulated_sales_kg, 2),
            initial_stock_kg=round(initial_stock_kg, 2),
            final_stock_kg=round(simulated_final_stock_kg, 2),
            delta_stock_kg=round(delta_stock, 2),
            mass_conservation_holds=mass_holds,
            mass_discrepancy_kg=round(discrepancy, 2),
            double_counting_alerts=partial.double_counting_alerts,
            methodology_summary=(
                "Scenario simulation model explicitly parameterized with versioned assumptions. "
                "Enforces mass conservation equation: Stock_end = Stock_start + Inflows - Sales - Losses."
            ),
        )
