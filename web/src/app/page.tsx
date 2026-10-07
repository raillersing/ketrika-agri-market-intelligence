"use client";

import React from "react";
import { KpiCard } from "@/components/ui/KpiCard";
import { PriceChart } from "@/components/charts/PriceChart";
import { ChoroplethMap } from "@/components/maps/ChoroplethMap";

export default function OverviewPage() {
  // Sample demonstration data matching synthetic gold dataset
  const kpis = [
    {
      title: "Prix médian national",
      value: "2 850",
      unit: "Ar/kg",
      variation: 0.042,
      variationPeriod: "m/m",
      valueKind: "observed",
      sources: ["miasa_odr", "wfp_hdx_mdg"],
      subtitle: "Riz blanc local (makalioka), détail",
    },
    {
      title: "Score de santé du marché",
      value: "74,0",
      unit: "/ 100",
      variation: -0.015,
      variationPeriod: "m/m",
      valueKind: "composite",
      sources: ["gold.kpi"],
      subtitle: "Approvisionnement régulier, légère tension prix",
    },
    {
      title: "Alertes actives",
      value: "3",
      unit: "alertes",
      variation: null,
      valueKind: "observed",
      sources: ["ops.alert"],
      subtitle: "1 sévérité haute (Atsimo-Andrefana), 2 modérées",
    },
    {
      title: "Disponibilité des stocks",
      value: "Suffisant",
      unit: "21j",
      variation: null,
      valueKind: "observed",
      sources: ["mincc_ppn"],
      subtitle: "Couverture régionale moyenne déclarée",
    },
  ];

  const chartData = [
    { month: "2026-04-01", medianPrice: 2600, minPrice: 2400, maxPrice: 2800, valueKind: "observed", sourceId: "miasa_odr" },
    { month: "2026-05-01", medianPrice: 2650, minPrice: 2450, maxPrice: 2850, valueKind: "observed", sourceId: "miasa_odr" },
    { month: "2026-06-01", medianPrice: 2700, minPrice: 2500, maxPrice: 2900, valueKind: "observed", sourceId: "wfp_hdx_mdg" },
    { month: "2026-07-01", medianPrice: 2720, minPrice: 2550, maxPrice: 2950, valueKind: "observed", sourceId: "wfp_hdx_mdg" },
    { month: "2026-08-01", medianPrice: 2780, minPrice: 2600, maxPrice: 3000, valueKind: "observed", sourceId: "miasa_odr" },
    { month: "2026-09-01", medianPrice: 2850, minPrice: 2650, maxPrice: 3100, valueKind: "observed", sourceId: "miasa_odr" },
    { month: "2026-10-01", medianPrice: 2920, minPrice: 2700, maxPrice: 3200, valueKind: "forecast", sourceId: "ml.price_forecast" },
  ];

  const regionPrices = {
    MG11: { pcode: "MG11", name: "Analamanga", price: 2850, valueKind: "observed", sourceId: "miasa_odr" },
    MG12: { pcode: "MG12", name: "Vakinankaratne", price: 2700, valueKind: "observed", sourceId: "miasa_odr" },
    MG13: { pcode: "MG13", name: "Itasy", price: 2650, valueKind: "observed", sourceId: "miasa_odr" },
    MG21: { pcode: "MG21", name: "Haute Matsiatra", price: 2800, valueKind: "observed", sourceId: "wfp_hdx_mdg" },
    MG31: { pcode: "MG31", name: "Atsinanana", price: 3100, valueKind: "observed", sourceId: "mincc_ppn" },
    MG33: { pcode: "MG33", name: "Alaotra-Mangoro", price: 2450, valueKind: "observed", sourceId: "miasa_odr" },
    MG41: { pcode: "MG41", name: "Boeny", price: 2950, valueKind: "observed", sourceId: "wfp_hdx_mdg" },
    MG51: { pcode: "MG51", name: "Atsimo-Andrefana", price: 3400, valueKind: "observed", sourceId: "mincc_ppn" },
    MG61: { pcode: "MG61", name: "DIANA", price: 3300, valueKind: "observed", sourceId: "wfp_hdx_mdg" },
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Vue d&apos;ensemble du marché vivrier
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Indicateurs clés, dynamique des prix et disparités territoriales des produits de première nécessité (PPN).
        </p>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.title} {...kpi} />
        ))}
      </div>

      {/* Charts & Maps Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PriceChart
          title="Évolution du prix (série observée et prévision)"
          productName="Riz blanc local (makalioka)"
          data={chartData}
        />
        <ChoroplethMap regionPrices={regionPrices} />
      </div>
    </div>
  );
}
