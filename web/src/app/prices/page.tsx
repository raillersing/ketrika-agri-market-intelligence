"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Download, TrendingUp, Layers, Sparkles, SlidersHorizontal } from "lucide-react";
import { DEFAULT_PRODUCT, summarizePrices, type MarketPrice } from "@/lib/market-overview";
import { DQ_SELECTION_MESSAGE, isLegacyDQProduct, saleStageLabel } from "@/lib/market-filters";
import { formatMonthYear, formatPrice } from "@/lib/formatters";
import { PriceChart, type PriceDataPoint } from "@/components/charts/PriceChart";
import { ValueKindBadge } from "@/components/ui/ValueKindBadge";
import { SourceBadge } from "@/components/ui/SourceBadge";

type Coverage = { expected_months: number; observed_months: number; missing_months: number; coverage_ratio: number; missing_months_list: string[] };
type Forecast = { product_code: string; location_pcode: string; actor_level: string; currency: string; unit: string; target_period: string; p50: number; p10: number | null; p90: number | null; horizon: number; model_requested: string; model_effective: string; is_baseline: boolean; is_calibrated: boolean; calibration_sample_size: number; fallback_reason: string | null; dataset_fingerprint: string };
type Abstention = { product_code: string; location_pcode: string; actor_level: string; reason: string; points_count: number };

type ModelTrajectory = {
  model_name: string;
  is_baseline: boolean;
  predictions: number[];
  p10: number[] | null;
  p90: number[] | null;
  historical_wape: number | null;
  historical_mae: number | null;
};

type MultiModelExtrapolations = {
  product_code: string;
  product_name: string | null;
  location_pcode: string;
  unit: string;
  currency: string;
  data_cutoff: string;
  last_observed_price: number;
  horizons: number[];
  target_periods: string[];
  winning_model: string | null;
  models: Record<string, ModelTrajectory>;
};

function selectionQuery(product: string, region: string, actor: string) {
  const params = new URLSearchParams({ product });
  if (region) params.set("location", region);
  if (actor) params.set("actor_level", actor);
  return params;
}

const MODEL_LABELS: Record<string, { label: string; badge: string; desc: string; icon: string }> = {
  winning: { label: "Modèle Sélectionné", badge: "Gagnant Backtest", desc: "Certifié au meilleur WAPE par validation temporelle étanche", icon: "⭐" },
  ConsensusEnsemble: { label: "Consensus Multi-Modèles", badge: "Ensemble IA", desc: "Synthèse pondérée par l'inverse de l'erreur (Bates-Granger) combinant toutes les techniques", icon: "🌟" },
  CausalAgriculturalModel: { label: "Causal Multivarié", badge: "Économie & Climat", desc: "Intègre le cycle de soudure phénologique, devises BFM, carburants OMH et météo", icon: "🌾" },
  AutoARIMA: { label: "AutoARIMA", badge: "Séries temporelles", desc: "Modélisation autorégressive des cycles passés avec saisonnalité annuelle", icon: "📈" },
  AutoETS: { label: "AutoETS", badge: "Lissage exponentiel", desc: "Espace d'états avec lissage exponentiel des variations saisonnières", icon: "📉" },
  SeasonalNaive: { label: "SeasonalNaive", badge: "Référence S-12", desc: "Répète à l'identique les variations calendaires de l'année précédente", icon: "🔄" },
  NaiveLast: { label: "NaiveLast", badge: "Persistance plate", desc: "Prolongation constante du dernier prix observé sans variation", icon: "➖" },
};

function PricesContent() {
  const params = useSearchParams();
  const product = params.get("product") || DEFAULT_PRODUCT;
  const region = params.get("region") || "";
  const actor = params.get("actor") || "";
  const [rows, setRows] = useState<MarketPrice[]>([]);
  const [forecasts, setForecasts] = useState<Forecast[]>([]);
  const [forecastAvailable, setForecastAvailable] = useState(false);
  const [extrapolations, setExtrapolations] = useState<MultiModelExtrapolations | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>("winning");
  const [horizon, setHorizon] = useState<number>(12);
  const [showMatrix, setShowMatrix] = useState<boolean>(true);
  const [abstentions, setAbstentions] = useState<Abstention[]>([]);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const options = { credentials: "include" as const, signal: controller.signal };
    setLoading(true); setError(null); setRows([]); setForecasts([]); setCoverage(null); setAbstentions([]); setForecastAvailable(false); setExtrapolations(null);
    async function load() {
      try {
        if (isLegacyDQProduct(product)) throw new Error(DQ_SELECTION_MESSAGE);
        const query = selectionQuery(product, region, actor);
        const extraQuery = new URLSearchParams({ product, horizon: String(horizon) });
        if (region) extraQuery.set("location", region);

        const [priceResponse, forecastResponse, abstentionResponse, coverageResponse, extraResponse] = await Promise.all([
          fetch(`/api/v1/prices?${query}`, options),
          fetch(`/api/v1/forecasts?${query}`, options).catch(() => null),
          fetch(`/api/v1/forecasts/abstentions?${new URLSearchParams({ product })}`, options).catch(() => null),
          region && actor ? fetch(`/api/v1/market/coverage/gaps?${new URLSearchParams({ product, location: region, actor_level: actor })}`, options).catch(() => null) : Promise.resolve(null),
          fetch(`/api/v1/forecasts/extrapolations?${extraQuery}`, options).catch(() => null),
        ]);
        if (!priceResponse.ok) throw new Error(`Les prix sont indisponibles (HTTP ${priceResponse.status}).`);
        const data: MarketPrice[] = await priceResponse.json();
        const future: Forecast[] = forecastResponse?.ok ? await forecastResponse.json() : [];
        const refused: Abstention[] = abstentionResponse?.ok ? await abstentionResponse.json() : [];
        const gaps: Coverage | null = coverageResponse?.ok ? await coverageResponse.json() : null;
        const extras: MultiModelExtrapolations | null = extraResponse?.ok ? await extraResponse.json() : null;

        if (!controller.signal.aborted) {
          setRows(data);
          setForecasts(future);
          setAbstentions(refused);
          setCoverage(gaps);
          setForecastAvailable(!!forecastResponse?.ok);
          setExtrapolations(extras);
        }
      } catch (failure) { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Les prix sont indisponibles."); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load(); return () => controller.abort();
  }, [product, region, actor, horizon]);

  const { latest, series } = summarizePrices(rows);
  const comparableForecasts = latest
    ? forecasts.filter(
        (row) =>
          row.product_code.toUpperCase() === latest.product_code.toUpperCase() &&
          (row.location_pcode === latest.location_pcode || (!row.location_pcode && !latest.location_pcode) || (row.location_pcode === "MDG" && !latest.location_pcode)) &&
          (row.actor_level === latest.actor_level || row.actor_level === "unknown" || latest.actor_level === "unknown") &&
          row.target_period > latest.month
      )
    : [];

  // Determine active trajectory to display on the chart
  const activeTrajectory = (selectedModel !== "winning" && extrapolations?.models[selectedModel])
    ? extrapolations.models[selectedModel]
    : null;

  const effectiveForecastPoints: PriceDataPoint[] = activeTrajectory && extrapolations
    ? extrapolations.target_periods.map((period, i) => ({
        month: period,
        medianPrice: activeTrajectory.predictions[i] ?? 0,
        p10Price: activeTrajectory.p10?.[i] ?? null,
        p90Price: activeTrajectory.p90?.[i] ?? null,
        valueKind: "forecast" as const,
        sourceId: `ml.${activeTrajectory.model_name}`,
        horizon: i + 1,
        modelEffective: activeTrajectory.model_name,
        modelRequested: activeTrajectory.model_name,
        isBaseline: activeTrajectory.is_baseline,
        isCalibrated: true,
        calibrationSampleSize: 12,
      }))
    : comparableForecasts.map(row => ({
        month: row.target_period,
        medianPrice: row.p50,
        p10Price: row.p10,
        p90Price: row.p90,
        valueKind: "forecast" as const,
        sourceId: `ml.${row.model_effective}`,
        horizon: row.horizon,
        modelEffective: row.model_effective,
        modelRequested: row.model_requested,
        isBaseline: row.is_baseline,
        isCalibrated: row.is_calibrated,
        calibrationSampleSize: row.calibration_sample_size,
        fallbackReason: row.fallback_reason || undefined,
        datasetFingerprint: row.dataset_fingerprint,
      }));

  const chart: PriceDataPoint[] = [
    ...series.map(row => ({ month: row.month, medianPrice: row.median_price, minPrice: row.min_price, maxPrice: row.max_price, valueKind: row.value_kind, sourceId: row.sources?.[0] })),
    ...effectiveForecastPoints,
  ];

  const abstention = abstentions.find(row => row.product_code === product && (!region || row.location_pcode === region) && (!actor || row.actor_level === actor));
  const exportCsv = () => {
    if (isLegacyDQProduct(product)) return;
    const query = selectionQuery(product, region, actor); query.set("format", "csv");
    window.open(`/api/v1/prices?${query}`, "_blank", "noopener,noreferrer");
  };

  const currentWinningModel = extrapolations?.winning_model || comparableForecasts[0]?.model_effective || "Inconnu";
  const displayedModelName = selectedModel === "winning" ? currentWinningModel : selectedModel;
  const activeLabelInfo = MODEL_LABELS[displayedModelName] || { label: displayedModelName, badge: "Modèle", desc: "", icon: "📊" };

  // Calculate spread across models at the final horizon
  let spreadMin = 0;
  let spreadMax = 0;
  if (extrapolations && Object.keys(extrapolations.models).length > 0) {
    const endVals = Object.values(extrapolations.models)
      .map(m => m.predictions[m.predictions.length - 1])
      .filter((v): v is number => typeof v === "number" && !isNaN(v));
    if (endVals.length > 0) {
      spreadMin = Math.min(...endVals);
      spreadMax = Math.max(...endVals);
    }
  }

  return <div className="space-y-6">
    <header className="flex flex-wrap items-start justify-between gap-4"><div className="space-y-2"><h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold"><TrendingUp aria-hidden="true" className="h-6 w-6 shrink-0 text-primary-readable" />Explorateur des prix vivriers</h1><p className="max-w-3xl text-sm leading-6 text-muted-foreground">Consultez les points mensuels disponibles. Une estimation, une observation et une prévision restent des valeurs de nature différente.</p></div><button type="button" disabled={loading || !!error || !rows.length} onClick={exportCsv} className="inline-flex min-h-[44px] items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"><Download aria-hidden="true" className="h-4 w-4" />Exporter la sélection CSV</button></header>
    {loading ? <p role="status" className="text-sm text-muted-foreground">Chargement des points de prix…</p> : error ? <p role="alert" className="rounded-xl border border-rose-500/20 p-4 text-sm text-rose-700 dark:text-rose-300">{error}</p> : <>
      {!rows.length ? <section className="rounded-xl border border-border bg-card p-6"><h2 className="font-medium">Aucun point de prix pour cette sélection</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">Les filtres sont conservés. Un autre produit, une autre zone ou un autre stade peut disposer de données. Cette absence ne signifie pas un prix nul.</p></section> : <>
        {latest && (
          <section aria-label="Série affichée" className="space-y-5">
            {/* MULTI-MODEL EXTRAPOLATION & PROJECTION CONTROLLER */}
            {extrapolations ? (
              <div className="rounded-xl border border-orange-500/30 bg-orange-500/5 p-5 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                      <Sparkles aria-hidden="true" className="h-5 w-5 text-orange-600 dark:text-orange-400" />
                      Extrapolations & Projections jusqu'à 1 An (Multi-Modèles)
                    </h2>
                    <p className="text-xs text-muted-foreground mt-1">
                      Sélectionnez la technique de modélisation pour projeter la trajectoire de prix sur le graphique et comparer les scénarios.
                    </p>
                  </div>
                  
                  {/* Horizon selector: 3m, 6m, 9m, 1 an & Matrix toggle button */}
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground font-medium flex items-center gap-1">
                        <SlidersHorizontal className="h-3.5 w-3.5" /> Horizon :
                      </span>
                      <div className="inline-flex rounded-lg border border-border bg-card p-0.5 text-xs">
                        {[
                          { val: 3, label: "3 mois" },
                          { val: 6, label: "6 mois" },
                          { val: 9, label: "9 mois" },
                          { val: 12, label: "1 an (12m)" },
                        ].map(({ val, label }) => (
                          <button
                            key={val}
                            type="button"
                            onClick={() => setHorizon(val)}
                            className={`px-3 py-1 rounded-md font-medium transition-colors ${
                              horizon === val
                                ? "bg-orange-500 text-white shadow-sm font-bold"
                                : "text-muted-foreground hover:text-foreground"
                            }`}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Prominent Matrice Comparative Button in Header */}
                    <button
                      type="button"
                      onClick={() => setShowMatrix(!showMatrix)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border shadow-sm ${
                        showMatrix
                          ? "bg-orange-500 text-white border-orange-600 font-bold"
                          : "bg-card text-foreground border-border hover:border-orange-500/50 hover:bg-orange-500/10"
                      }`}
                    >
                      <Layers className="h-3.5 w-3.5" />
                      {showMatrix ? "Matrice comparative (Affichée)" : "Afficher la matrice comparative"}
                    </button>
                  </div>
                </div>

                {/* Model Selector Tabs */}
                <div className="space-y-2">
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Technique de projection active :
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2.5">
                    {/* Winning Model Option */}
                    <button
                      type="button"
                      onClick={() => setSelectedModel("winning")}
                      className={`flex flex-col items-start p-3 rounded-lg border text-left transition-all ${
                        selectedModel === "winning"
                          ? "border-orange-500 bg-card shadow-sm ring-2 ring-orange-500/30"
                          : "border-border bg-card/60 hover:bg-card hover:border-orange-500/30"
                      }`}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span className="font-semibold text-sm text-foreground">
                          ⭐ Sélection Recommandée
                        </span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-500/30">
                          Vainqueur
                        </span>
                      </div>
                      <span className="text-xs text-muted-foreground mt-1">
                        Technique : <strong>{currentWinningModel}</strong>
                      </span>
                    </button>

                    {/* Consensus Ensemble Option */}
                    {extrapolations.models["ConsensusEnsemble"] && (
                      <button
                        type="button"
                        onClick={() => setSelectedModel("ConsensusEnsemble")}
                        className={`flex flex-col items-start p-3 rounded-lg border text-left transition-all ${
                          selectedModel === "ConsensusEnsemble"
                            ? "border-orange-500 bg-card shadow-sm ring-2 ring-orange-500/30"
                            : "border-border bg-card/60 hover:bg-card hover:border-orange-500/30"
                        }`}
                      >
                        <div className="flex items-center justify-between w-full">
                          <span className="font-semibold text-sm text-foreground">
                            🌟 Consensus Multi-Modèles
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-700 dark:text-purple-300 font-bold border border-purple-500/30">
                            Ensemble
                          </span>
                        </div>
                        <span className="text-xs text-muted-foreground mt-1 line-clamp-1">
                          Synthèse pondérée de toutes les approches
                        </span>
                      </button>
                    )}

                    {/* Individual Candidate Models */}
                    {Object.entries(extrapolations.models)
                      .filter(([mName]) => mName !== "ConsensusEnsemble")
                      .map(([mName, traj]) => {
                        const info = MODEL_LABELS[mName] || { label: mName, badge: "Modèle", desc: "", icon: "📊" };
                        const isSelected = selectedModel === mName;
                        return (
                          <button
                            key={mName}
                            type="button"
                            onClick={() => setSelectedModel(mName)}
                            className={`flex flex-col items-start p-3 rounded-lg border text-left transition-all ${
                              isSelected
                                ? "border-orange-500 bg-card shadow-sm ring-2 ring-orange-500/30"
                                : "border-border bg-card/60 hover:bg-card hover:border-orange-500/30"
                            }`}
                          >
                            <div className="flex items-center justify-between w-full">
                              <span className="font-semibold text-sm text-foreground flex items-center gap-1.5">
                                <span>{info.icon}</span> {info.label}
                              </span>
                              {traj.historical_wape !== null && (
                                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                                  WAPE {(traj.historical_wape * 100).toFixed(1)}%
                                </span>
                              )}
                            </div>
                            <span className="text-xs text-muted-foreground mt-1 line-clamp-1">
                              {info.desc}
                            </span>
                          </button>
                        );
                      })}
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-border/50 text-xs text-muted-foreground">
                  <p>
                    Courbe : <strong>{latest.location_name || latest.location_pcode || "Zone non renseignée"}</strong> · {saleStageLabel(latest.actor_level)} · {latest.currency}/{latest.unit}. Projection : <strong className="text-foreground">{activeLabelInfo.icon} {activeLabelInfo.label}</strong> ({horizon} mois).
                  </p>
                  {spreadMin > 0 && spreadMax > 0 && (
                    <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-card border border-border">
                      Dispersion à {horizon} mois : <strong>{Math.round(spreadMin).toLocaleString("fr-FR")} Ar</strong> ➔ <strong>{Math.round(spreadMax).toLocaleString("fr-FR")} Ar</strong>
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-sm leading-6 text-muted-foreground">
                Courbe : {latest.location_name || latest.location_pcode || "Zone non renseignée"} · {saleStageLabel(latest.actor_level)} · {latest.currency}/{latest.unit}. Projection affichée : <strong className="text-foreground">{activeLabelInfo.icon} {activeLabelInfo.label}</strong> ({horizon} mois).
              </p>
            )}

            {/* INTERACTIVE PRICE CHART WITH SELECTED MODEL AND HORIZON */}
            <PriceChart
              title="Trajectoire et Extrapolation Prédictive"
              data={chart}
              productName={product}
              unit={latest.unit}
              currency={latest.currency}
              forecastLabel={`Projection ${activeLabelInfo.label} (${horizon} mois)`}
            />

            {/* MONTHLY PROJECTIONS CARDS & MATRIX */}
            {extrapolations && (
              <div className="space-y-4 pt-1">
                {/* Active Model Forecast Points Grid */}
                <div className="space-y-2">
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Points mensuels projetés ({activeLabelInfo.label} · {horizon} mois) :
                  </span>
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
                    {effectiveForecastPoints.map((fc) => (
                      <div key={fc.month} className="rounded-xl border border-orange-500/20 bg-card p-3 text-center space-y-1 shadow-sm hover:border-orange-500/40 transition-colors">
                        <div className="text-[11px] font-medium text-muted-foreground">
                          {formatMonthYear(fc.month)} <span className="font-mono text-[10px] text-orange-600 dark:text-orange-400 font-bold">(h={fc.horizon})</span>
                        </div>
                        <div className="text-base font-extrabold text-orange-600 dark:text-orange-400 font-mono tracking-tight">
                          {formatPrice(fc.medianPrice, extrapolations.unit, extrapolations.currency === "MGA" ? "Ar" : extrapolations.currency)}
                        </div>
                        {fc.p10Price !== null && fc.p90Price !== null && (
                          <div className="text-[10px] text-orange-700/80 dark:text-orange-300/80 font-mono">
                            [{Math.round(fc.p10Price).toLocaleString("fr-FR")} – {Math.round(fc.p90Price).toLocaleString("fr-FR")}]
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Comparative Matrix Table Toggle */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowMatrix(!showMatrix)}
                    className={`inline-flex items-center gap-2 rounded-lg border px-3.5 py-2 text-xs font-semibold transition-all shadow-sm ${
                      showMatrix
                        ? "border-orange-500 bg-orange-500/10 text-orange-900 dark:text-orange-200"
                        : "border-orange-500 bg-orange-500 text-white hover:bg-orange-600"
                    }`}
                  >
                    <Layers aria-hidden="true" className="h-4 w-4" />
                    {showMatrix ? "Masquer la matrice comparative des extrapolations" : "Afficher la matrice comparative de tous les modèles"}
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${showMatrix ? "bg-orange-500/20" : "bg-black/25 text-white"}`}>
                      {showMatrix ? "Tableau ouvert" : "Cliquer pour ouvrir le tableau"}
                    </span>
                  </button>
                  <span className="text-xs text-muted-foreground">
                    {showMatrix ? "Comparaison détaillée de toutes les projections mois par mois" : "Affiche la matrice complète côte à côte"}
                  </span>
                </div>

                {/* Comparative Matrix Table */}
                {showMatrix && (
                  <div className="rounded-lg border border-border bg-card p-4 space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                        <Layers className="h-4 w-4 text-orange-500" />
                        Matrice comparative des extrapolations par technique (Ar/{extrapolations.unit})
                      </h3>
                      <span className="text-xs text-muted-foreground">
                        Dernier prix observé : <strong>{formatPrice(extrapolations.last_observed_price, extrapolations.unit, "Ar")}</strong> ({formatMonthYear(extrapolations.data_cutoff)})
                      </span>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="text-muted-foreground border-b border-border">
                          <tr>
                            <th className="p-2 font-medium">Technique / Modèle</th>
                            <th className="p-2 font-medium">Nature</th>
                            <th className="p-2 font-medium">Erreur WAPE</th>
                            {extrapolations.target_periods.map((p) => (
                              <th key={p} className="p-2 font-medium text-right font-mono whitespace-nowrap">
                                {formatMonthYear(p)}
                              </th>
                            ))}
                            <th className="p-2 font-medium text-center">Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(extrapolations.models).map(([mName, traj]) => {
                            const info = MODEL_LABELS[mName] || { label: mName, badge: "Modèle", desc: "", icon: "📊" };
                            const isCurrent = selectedModel === mName || (selectedModel === "winning" && mName === currentWinningModel);
                            const isConsensus = mName === "ConsensusEnsemble";
                            return (
                              <tr
                                key={mName}
                                className={`border-b border-border/50 hover:bg-muted/40 transition-colors ${
                                  isCurrent
                                    ? "bg-orange-500/10 font-semibold"
                                    : isConsensus
                                    ? "bg-purple-500/5 font-medium"
                                    : ""
                                }`}
                              >
                                <td className="p-2 font-medium text-foreground whitespace-nowrap">
                                  <span className="mr-1">{info.icon}</span> {info.label} {mName === currentWinningModel && "⭐"}
                                </td>
                                <td className="p-2 text-muted-foreground whitespace-nowrap">{info.badge}</td>
                                <td className="p-2 font-mono whitespace-nowrap">
                                  {traj.historical_wape !== null ? `${(traj.historical_wape * 100).toFixed(2)}%` : "N/A"}
                                </td>
                                {traj.predictions.map((val, i) => (
                                  <td key={i} className="p-2 text-right font-mono text-foreground whitespace-nowrap">
                                    {Math.round(val).toLocaleString("fr-FR")}
                                  </td>
                                ))}
                                <td className="p-2 text-center whitespace-nowrap">
                                  <button
                                    type="button"
                                    onClick={() => setSelectedModel(mName)}
                                    className={`px-2.5 py-0.5 rounded text-[11px] font-medium transition-colors ${
                                      isCurrent
                                        ? "bg-orange-500 text-white font-bold"
                                        : "bg-muted text-muted-foreground hover:bg-orange-500/20 hover:text-orange-700"
                                    }`}
                                  >
                                    {isCurrent ? "Actif" : "Afficher"}
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {/* HISTORICAL POINTS TABLE */}
        <section className="rounded-xl border border-border bg-card p-5">
          <h2 className="text-lg font-medium">Points mensuels de la sélection</h2>
          <p className="mt-2 text-sm text-muted-foreground">{rows.length} points disponibles · L’export reprend ces filtres.</p>
          <div className="mt-4 max-h-[420px] overflow-y-auto overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Période, zone, stade de vente, prix et nature pour {product}</caption>
              <thead className="sticky top-0 bg-card text-muted-foreground border-b border-border shadow-sm">
                <tr>
                  {["Période", "Zone", "Stade de vente", "Prix", "Nature", "Source"].map(title => (
                    <th key={title} scope="col" className="p-3 font-medium bg-card">{title}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={`${row.month}-${row.location_pcode}-${row.actor_level}-${index}`} className="border-t border-border hover:bg-muted/30">
                    <td className="whitespace-nowrap p-3">{formatMonthYear(row.month)}</td>
                    <th scope="row" className="p-3 font-medium">{row.location_name || row.location_pcode || "Non renseignée"}</th>
                    <td className="p-3">{saleStageLabel(row.actor_level)}</td>
                    <td className="whitespace-nowrap p-3">{row.currency === "MGA" ? formatPrice(row.median_price, row.unit) : `${row.median_price} ${row.currency}/${row.unit}`}</td>
                    <td className="p-3"><ValueKindBadge kind={row.value_kind} /></td>
                    <td className="p-3">{row.sources?.length ? row.sources.map(source => <SourceBadge key={source} sourceId={source} />) : "Source non renseignée"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </>}

      <section className="rounded-xl border border-border bg-card p-5"><h2 className="font-medium">Disponibilité de la série</h2>{coverage ? <><dl className="mt-3 grid gap-4 text-sm sm:grid-cols-3"><div><dt className="text-muted-foreground">Complétude</dt><dd>{(coverage.coverage_ratio * 100).toFixed(1)} %</dd></div><div><dt className="text-muted-foreground">Mois renseignés</dt><dd>{coverage.observed_months} / {coverage.expected_months}</dd></div><div><dt className="text-muted-foreground">Mois manquants</dt><dd>{coverage.missing_months}</dd></div></dl>{coverage.missing_months_list.length > 0 && <p className="mt-3 break-words text-xs text-muted-foreground">Périodes manquantes : {coverage.missing_months_list.join(", ")}</p>}</> : <p className="mt-2 text-sm leading-6 text-muted-foreground">{region && actor ? "La mesure de couverture est indisponible pour cette sélection." : "Choisissez une zone et un stade de vente pour consulter la mesure de couverture correspondante."}</p>}</section>
      <section className="rounded-xl border border-border bg-card p-5"><h2 className="font-medium">Prévisions et limites</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">{comparableForecasts.length ? "Les prévisions renvoyées pour la série affichée sont distinguées dans le graphique. Leur présence ne suffit pas à qualifier leur précision." : !forecastAvailable ? "Les informations de prévision sont indisponibles. Aucun résultat n’est déduit de cette absence." : forecasts.length ? "Les prévisions reçues ne correspondent pas à une période future et au périmètre exact de la série affichée. Elles ne sont pas ajoutées à la courbe." : "Aucune prévision n’est disponible dans cette réponse pour la sélection."}</p>{abstention && <p className="mt-3 break-words text-sm text-muted-foreground">Abstention enregistrée : {abstention.reason} · {abstention.points_count} points.</p>}</section>
    </>}
  </div>;
}
export default function PricesPage() { return <React.Suspense fallback={<p role="status">Chargement de l’explorateur…</p>}><PricesContent /></React.Suspense>; }
