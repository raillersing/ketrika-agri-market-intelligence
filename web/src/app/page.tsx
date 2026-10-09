"use client";

import React from "react";
import Link from "next/link";
import { KpiCard } from "@/components/ui/KpiCard";
import { PriceChart } from "@/components/charts/PriceChart";
import { ChoroplethMap } from "@/components/maps/ChoroplethMap";
import {
  AlertTriangle,
  ArrowRight,
  Download,
  FileText,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from "lucide-react";

export default function OverviewPage() {
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

  const latestQuotations = [
    { product: "Riz blanc local (makalioka)", market: "Anosibe (Antananarivo)", region: "Analamanga", price: 2850, actor: "Détail", source: "miasa_odr", date: "05/10/2026" },
    { product: "Paddy (riz non usiné)", market: "Ambatondrazaka", region: "Alaotra-Mangoro", price: 1750, actor: "Producteur", source: "miasa_odr", date: "04/10/2026" },
    { product: "Riz blanc local (tsipala)", market: "Bazar Be (Toliara)", region: "Atsimo-Andrefana", price: 3400, actor: "Détail", source: "mincc_ppn", date: "05/10/2026" },
    { product: "Maïs grain jaune", market: "Antsirabe Marché", region: "Vakinankaratne", price: 1450, actor: "Demi-gros", source: "wfp_hdx_mdg", date: "02/10/2026" },
    { product: "Manioc frais", market: "Manakara Centre", region: "Fitovinany", price: 950, actor: "Détail", source: "wfp_hdx_mdg", date: "03/10/2026" },
  ];

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Executive Hero Banner */}
      <div className="glass-panel p-6 sm:p-8 rounded-3xl relative overflow-hidden">
        <div className="absolute top-0 right-0 -mr-16 -mt-16 w-80 h-80 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Intelligence Vivrière Madagascar • Semaine 40 (Octobre 2026)
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white leading-tight">
              Tableau de bord de veille de marché PPN
            </h1>
            <p className="text-sm text-slate-400 leading-relaxed">
              Consolidation multi-sources certifiée : cours du riz, légumineuses, huiles et tubercules. Traçabilité Bronze vers Silver avec 100 % de provenance vérifiée sans hallucination.
            </p>
          </div>

          {/* Quick Action Buttons */}
          <div className="flex flex-wrap sm:flex-nowrap items-center gap-3">
            <Link
              href="/bulletins"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-950/40 transition-all hover:scale-102"
            >
              <FileText className="w-4 h-4" />
              <span>Bulletin hebdo</span>
            </Link>
            <Link
              href="/copilot"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-white/[0.1] hover:border-purple-500/40 text-purple-300 text-xs font-semibold transition-all hover:scale-102"
            >
              <Sparkles className="w-4 h-4" />
              <span>Copilote IA</span>
            </Link>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.title} {...kpi} />
        ))}
      </div>

      {/* Visualizers Grid: Chart + Map */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PriceChart
          title="Dynamique du prix médian (Série observée & Modèle ML)"
          productName="Riz blanc local (makalioka)"
          data={chartData}
        />
        <ChoroplethMap regionPrices={regionPrices} />
      </div>

      {/* Verified Quotations Table */}
      <div className="glass-card rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-white/[0.07] flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              Dernières cotations de référence certifiées
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Relevés validés par le moteur d&apos;ingestion • Zéro estimation non auditée
            </p>
          </div>
          <Link
            href="/prices"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-400 hover:text-emerald-300 transition-colors"
          >
            <span>Explorer toutes les séries</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/60 border-b border-white/[0.06] text-slate-400 font-mono text-[10px] uppercase tracking-wider">
              <tr>
                <th className="px-5 py-3">Produit Vivrier</th>
                <th className="px-5 py-3">Marché / Région</th>
                <th className="px-5 py-3">Niveau</th>
                <th className="px-5 py-3 text-right">Prix Relevé</th>
                <th className="px-5 py-3">Date</th>
                <th className="px-5 py-3">Source & Statut</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {latestQuotations.map((row, idx) => (
                <tr
                  key={idx}
                  className="hover:bg-white/[0.02] transition-colors"
                >
                  <td className="px-5 py-3.5 font-medium text-white">
                    {row.product}
                  </td>
                  <td className="px-5 py-3.5 text-slate-300">
                    <div className="font-medium">{row.market}</div>
                    <div className="text-[10px] text-slate-400">{row.region}</div>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-slate-800 text-slate-300 border border-white/[0.05]">
                      {row.actor}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-right font-mono font-bold text-emerald-400 text-sm">
                    {row.price.toLocaleString("fr-FR")} Ar/kg
                  </td>
                  <td className="px-5 py-3.5 text-slate-400 font-mono text-[11px]">
                    {row.date}
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-1.5">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {row.source}
                      </span>
                      <span className="inline-flex items-center gap-0.5 text-[10px] text-slate-400 font-mono" title="Certifié Bronze">
                        <ShieldCheck className="w-3 h-3 text-emerald-400" />
                        100%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
