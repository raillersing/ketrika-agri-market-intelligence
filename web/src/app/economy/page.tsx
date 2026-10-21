"use client";

import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Download,
  Fuel,
  Info,
  Layers,
  Percent,
  RefreshCw,
  Scale,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";
import { formatNumber, formatPrice } from "@/lib/formatters";
import { ValueKindBadge } from "@/components/ui/ValueKindBadge";
import { SourceBadge } from "@/components/ui/SourceBadge";
import { ProvenanceLink } from "@/components/ui/ProvenanceLink";

// Types derived from /v1/economic endpoints (ADR-070, ADR-071)
interface EconomicMetricCard {
  metric_id: string;
  dimension: string;
  title: string;
  definition: string;
  formula: string;
  unit: string;
  frequency: string;
  geo_scope: string;
  primary_source: string;
  source_family: string;
  publication_lag_days: number;
  limitations: string;
}

interface IndicatorObservation {
  indicator_code: string;
  dimension: string;
  title: string;
  period: string;
  unit: string;
  value: number | null;
  observed_or_imputed: string;
  is_administered?: boolean;
  published_at?: string | null;
  sources: string[];
  reason_null?: string | null;
  observation_id?: string | null;
}

interface DimensionSummary {
  dimension: string;
  title: string;
  description: string;
  completeness: "complete" | "partial" | "no_data";
  active_indicators_count: number;
  total_indicators_count: number;
  indicators: IndicatorObservation[];
}

interface EconomicDashboardResponse {
  as_of_date: string;
  dimensions: Record<string, DimensionSummary>;
}

interface PilotEconomicContext {
  product_code: string;
  location_pcode: string;
  period: string;
  food_inflation_rate_pct: number | null;
  rice_retail_price_variation_pct: number | null;
  import_unit_cost_mga_per_kg: number | null;
  import_dependency_ratio: number | null;
  methodological_warning: string;
}

const DIMENSION_CONFIG: Record<
  string,
  { label: string; icon: React.ComponentType<{ className?: string }>; color: string }
> = {
  inflation: { label: "Inflation & Prix Conso", icon: Percent, color: "text-amber-400" },
  exchange_rate: { label: "Taux de Change", icon: Scale, color: "text-blue-400" },
  fuel_energy: { label: "Carburants & Énergie", icon: Fuel, color: "text-rose-400" },
  external_trade: { label: "Commerce Extérieur", icon: Layers, color: "text-emerald-400" },
  real_activity: { label: "Activité Réelle", icon: Zap, color: "text-purple-400" },
};

function EconomyContent() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<EconomicDashboardResponse | null>(null);
  const [indicatorsCatalog, setIndicatorsCatalog] = useState<Record<string, EconomicMetricCard>>({});
  const [pilotContext, setPilotContext] = useState<PilotEconomicContext | null>(null);
  const [activeDimension, setActiveDimension] = useState<string>("inflation");
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({});

  useEffect(() => {
    async function loadEconomicData() {
      setLoading(true);
      setError(null);
      try {
        const [dashRes, catalogRes, pilotRes] = await Promise.all([
          fetch("/api/v1/economic/dashboard", { credentials: "include" }),
          fetch("/api/v1/economic/indicators", { credentials: "include" }),
          fetch("/api/v1/economic/pilot-context", { credentials: "include" }),
        ]);

        if (dashRes.ok) {
          const dashData: EconomicDashboardResponse = await dashRes.json();
          setDashboard(dashData);
        } else if (dashRes.status === 503) {
          // Macroeconomic dashboard is in qualified withholding (ADR-070 / R2.8)
          setDashboard(null);
        } else {
          throw new Error("Impossible de charger le tableau économique.");
        }

        if (catalogRes.ok) {
          const catalogData: EconomicMetricCard[] = await catalogRes.json();
          const catalogMap: Record<string, EconomicMetricCard> = {};
          for (const card of catalogData) {
            catalogMap[card.metric_id] = card;
          }
          setIndicatorsCatalog(catalogMap);
        }

        if (pilotRes.ok) {
          const pilotData: PilotEconomicContext = await pilotRes.json();
          setPilotContext(pilotData);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Erreur de chargement des données économiques";
        setError(msg);
      } finally {
        setLoading(false);
      }
    }

    loadEconomicData();
  }, []);

  const handleExportCsv = () => {
    window.open("/api/v1/economic/indicators?format=csv", "_blank");
  };

  const toggleExpand = (code: string) => {
    setExpandedCards((prev) => ({ ...prev, [code]: !prev[code] }));
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="min-w-0 text-2xl font-extrabold tracking-tight text-white flex items-start gap-2.5">
              <BarChart3 className="w-6 h-6 shrink-0 text-emerald-400" />
              Observatoire Économique & Conjoncture
            </h1>
            <span className="hidden sm:inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
              ADR-070
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1 max-w-3xl">
            Tableau économique interprétable par dimension étanche (inflation, change, énergie,
            commerce extérieur, activité). Les indicateurs sont strictement autonomes : aucun
            score global synthétique artificiel n&apos;est calculé.
          </p>
        </div>

        <button
          onClick={handleExportCsv}
          className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-emerald-950/40 transition-all hover:scale-102 self-start sm:self-auto"
          title="Exporter le catalogue des 14 fiches métriques normatives au format CSV"
        >
          <Download className="w-4 h-4" />
          Exporter fiches métriques (CSV)
        </button>
      </div>

      {/* Error State */}
      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Rice Pilot Transmission Context Panel (ADR-070 transmission link) */}
      {pilotContext && (
        <div className="glass-card rounded-2xl p-5 border border-emerald-500/20 bg-gradient-to-br from-emerald-950/30 via-slate-900/60 to-slate-950/80">
          <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-emerald-400 font-mono">
                Contexte Macroéconomique du Pilote Rizicole (R2.4)
              </h2>
            </div>
            <span className="text-[11px] font-mono text-slate-400">
              Période : {pilotContext.period}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
            {/* 1. Food CPI Inflation */}
            <div className="bg-slate-900/80 p-3.5 rounded-xl border border-white/[0.05]">
              <span className="text-[10px] font-mono uppercase text-slate-400">
                Inflation Alimentaire (NIPC)
              </span>
              <div className="text-lg font-bold font-mono text-white mt-1">
                {pilotContext.food_inflation_rate_pct !== null
                  ? `${pilotContext.food_inflation_rate_pct > 0 ? "+" : ""}${pilotContext.food_inflation_rate_pct.toFixed(1)} %`
                  : "Indisponible"}
              </div>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                Variation indice INSTAT NIPC
              </span>
            </div>

            {/* 2. Retail Rice Price Variation */}
            <div className="bg-slate-900/80 p-3.5 rounded-xl border border-white/[0.05]">
              <span className="text-[10px] font-mono uppercase text-slate-400">
                Variation Prix Riz Détail
              </span>
              <div className="text-lg font-bold font-mono text-emerald-400 mt-1">
                {pilotContext.rice_retail_price_variation_pct !== null
                  ? `${pilotContext.rice_retail_price_variation_pct > 0 ? "+" : ""}${pilotContext.rice_retail_price_variation_pct.toFixed(1)} %`
                  : "Indisponible"}
              </div>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                Prix nominal vivrier au kilo
              </span>
            </div>

            {/* 3. Import Unit Cost */}
            <div className="bg-slate-900/80 p-3.5 rounded-xl border border-white/[0.05]">
              <span className="text-[10px] font-mono uppercase text-slate-400">
                Coût Unitaire CAF Import
              </span>
              <div className="text-lg font-bold font-mono text-amber-300 mt-1">
                {pilotContext.import_unit_cost_mga_per_kg !== null
                  ? `${formatNumber(Math.round(pilotContext.import_unit_cost_mga_per_kg))} Ar/kg`
                  : "Indisponible"}
              </div>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                Rapport Valeur CAF / Volume net
              </span>
            </div>

            {/* 4. Import Dependency Ratio */}
            <div className="bg-slate-900/80 p-3.5 rounded-xl border border-white/[0.05]">
              <span className="text-[10px] font-mono uppercase text-slate-400">
                Dépendance aux Importations
              </span>
              <div className="text-lg font-bold font-mono text-blue-300 mt-1">
                {pilotContext.import_dependency_ratio !== null
                  ? `${(pilotContext.import_dependency_ratio * 100).toFixed(1)} %`
                  : "Indisponible"}
              </div>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                Part du riz importé disponible
              </span>
            </div>
          </div>

          <div className="mt-3 text-[11px] text-slate-400 flex items-start gap-1.5 font-sans border-t border-white/[0.05] pt-2.5">
            <Info className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
            <span>
              <strong>Garde ADR-070 :</strong> {pilotContext.methodological_warning}
            </span>
          </div>
        </div>
      )}

      {/* Dimension Selector Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
        {Object.entries(DIMENSION_CONFIG).map(([key, config]) => {
          const Icon = config.icon;
          const isActive = activeDimension === key;
          const dimData = dashboard?.dimensions?.[key];
          const completeness = dimData?.completeness || "no_data";

          return (
            <button
              key={key}
              onClick={() => setActiveDimension(key)}
              className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all border ${
                isActive
                  ? "bg-emerald-600 text-white border-emerald-500 shadow-lg shadow-emerald-950/50"
                  : "bg-slate-900/80 text-slate-300 border-white/[0.07] hover:bg-slate-800/80"
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? "text-white" : config.color}`} />
              <span>{config.label}</span>
              <span
                className={`w-2 h-2 rounded-full ${
                  completeness === "complete"
                    ? "bg-emerald-400"
                    : completeness === "partial"
                    ? "bg-amber-400"
                    : "bg-slate-500"
                }`}
                title={`Complétude: ${completeness}`}
              />
            </button>
          );
        })}
      </div>

      {/* Active Dimension Content */}
      {loading ? (
        <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
          <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
          Chargement du tableau économique...
        </div>
      ) : error ? null : !dashboard || !dashboard.dimensions?.[activeDimension] ? (
        <div className="glass-card rounded-2xl p-12 text-center text-xs text-slate-400 font-mono">
          Aucune donnée disponible pour cette dimension économique.
        </div>
      ) : (
        <div className="space-y-4">
          {/* Dimension Header Summary */}
          {(() => {
            const currentDim = dashboard.dimensions[activeDimension];
            return (
              <div className="glass-card rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <span>{currentDim.title}</span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-mono border ${
                        currentDim.completeness === "complete"
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : currentDim.completeness === "partial"
                          ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                          : "bg-slate-800 text-slate-400 border-white/[0.05]"
                      }`}
                    >
                      Complétude : {currentDim.completeness}
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">{currentDim.description}</p>
                </div>
                <div className="text-xs font-mono text-slate-400">
                  {currentDim.active_indicators_count} / {currentDim.total_indicators_count} séries
                  actives
                </div>
              </div>
            );
          })()}

          {/* Indicators Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {dashboard.dimensions[activeDimension].indicators.map((ind) => {
              const cardMeta = indicatorsCatalog[ind.indicator_code];
              const isExpanded = !!expandedCards[ind.indicator_code];

              return (
                <div
                  key={ind.indicator_code}
                  className="glass-card rounded-2xl p-4 flex flex-col justify-between hover:border-white/[0.12] transition-colors"
                >
                  <div>
                    {/* Header: Indicator title & badges */}
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-xs font-bold text-white leading-tight">
                        {ind.title}
                      </h4>
                      <div className="flex items-center gap-1 shrink-0">
                        {ind.is_administered && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-rose-500/10 text-rose-300 border border-rose-500/20">
                            Administré
                          </span>
                        )}
                        <ValueKindBadge kind={ind.observed_or_imputed} />
                      </div>
                    </div>

                    {/* Value Display */}
                    <div className="mt-3 flex items-baseline gap-2">
                      {ind.value !== null ? (
                        <>
                          <span className="text-2xl font-extrabold font-mono text-white">
                            {formatNumber(ind.value)}
                          </span>
                          <span className="text-xs font-mono text-slate-400">{ind.unit}</span>
                        </>
                      ) : (
                        <div className="flex flex-col gap-0.5">
                          <span className="text-sm font-bold font-mono text-slate-500 italic">
                            Donnée indisponible
                          </span>
                          {ind.reason_null && (
                            <span className="text-[10px] font-mono text-amber-400/80">
                              Raison : {ind.reason_null}
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Meta info: Period, sources & published_at */}
                    <div className="mt-3 pt-2.5 border-t border-white/[0.05] flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
                      <span className="font-mono">Période : {ind.period}</span>
                      <div className="flex items-center gap-1.5">
                        {ind.sources.map((s) => (
                          <SourceBadge key={s} sourceId={s} />
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Normative Metric Card Drawer Toggle */}
                  {cardMeta && (
                    <div className="mt-3 pt-2 border-t border-white/[0.05]">
                      <button
                        onClick={() => toggleExpand(ind.indicator_code)}
                        className="w-full flex items-center justify-between text-[11px] text-slate-400 hover:text-slate-200 transition-colors py-1"
                        aria-expanded={isExpanded}
                      >
                        <span className="flex items-center gap-1">
                          <BookOpen className="w-3 h-3 text-emerald-400" />
                          Fiche normative (formule & limites)
                        </span>
                        {isExpanded ? (
                          <ChevronUp className="w-3.5 h-3.5 text-slate-400" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                        )}
                      </button>

                      {isExpanded && (
                        <div className="mt-2 p-2.5 bg-slate-950/80 rounded-xl border border-white/[0.06] text-[10px] space-y-1.5 text-slate-300">
                          <div>
                            <span className="text-slate-400 font-semibold block">Formule :</span>
                            <code className="text-emerald-300 font-mono text-[9px] block bg-slate-900 px-1.5 py-0.5 rounded mt-0.5">
                              {cardMeta.formula}
                            </code>
                          </div>
                          <div>
                            <span className="text-slate-400 font-semibold block">Définition :</span>
                            <p className="text-slate-300 text-[10px] leading-tight mt-0.5">
                              {cardMeta.definition}
                            </p>
                          </div>
                          <div className="flex justify-between text-slate-400 text-[9px] pt-1 border-t border-white/[0.04]">
                            <span>Lag de publ. : {cardMeta.publication_lag_days} jours</span>
                            <span>Fréquence : {cardMeta.frequency}</span>
                          </div>
                          <div>
                            <span className="text-amber-400/90 font-semibold block">
                              Limitations :
                            </span>
                            <p className="text-slate-400 text-[9px] leading-tight mt-0.5">
                              {cardMeta.limitations}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Provenance Link */}
                  {ind.observation_id && (
                    <div className="mt-2 text-right">
                      <ProvenanceLink observationId={ind.observation_id} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default function EconomyPage() {
  return (
    <React.Suspense
      fallback={
        <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
          <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
          Chargement de l&apos;observatoire économique...
        </div>
      }
    >
      <EconomyContent />
    </React.Suspense>
  );
}
