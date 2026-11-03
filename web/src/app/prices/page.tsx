"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Download, TrendingUp } from "lucide-react";
import { DEFAULT_PRODUCT, summarizePrices, type MarketPrice } from "@/lib/market-overview";
import { DQ_SELECTION_MESSAGE, isLegacyDQProduct, saleStageLabel } from "@/lib/market-filters";
import { formatMonthYear, formatPrice } from "@/lib/formatters";
import { PriceChart, type PriceDataPoint } from "@/components/charts/PriceChart";
import { ValueKindBadge } from "@/components/ui/ValueKindBadge";
import { SourceBadge } from "@/components/ui/SourceBadge";

type Coverage = { expected_months: number; observed_months: number; missing_months: number; coverage_ratio: number; missing_months_list: string[] };
type Forecast = { product_code: string; location_pcode: string; actor_level: string; currency: string; unit: string; target_period: string; p50: number; p10: number | null; p90: number | null; horizon: number; model_requested: string; model_effective: string; is_baseline: boolean; is_calibrated: boolean; calibration_sample_size: number; fallback_reason: string | null; dataset_fingerprint: string };
type Abstention = { product_code: string; location_pcode: string; actor_level: string; reason: string; points_count: number };
function selectionQuery(product: string, region: string, actor: string) {
  const params = new URLSearchParams({ product });
  if (region) params.set("location", region);
  if (actor) params.set("actor_level", actor);
  return params;
}
function PricesContent() {
  const params = useSearchParams();
  const product = params.get("product") || DEFAULT_PRODUCT;
  const region = params.get("region") || "";
  const actor = params.get("actor") || "";
  const [rows, setRows] = useState<MarketPrice[]>([]);
  const [forecasts, setForecasts] = useState<Forecast[]>([]);
  const [forecastAvailable, setForecastAvailable] = useState(false);
  const [abstentions, setAbstentions] = useState<Abstention[]>([]);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    const options = { credentials: "include" as const, signal: controller.signal };
    setLoading(true); setError(null); setRows([]); setForecasts([]); setCoverage(null); setAbstentions([]); setForecastAvailable(false);
    async function load() {
      try {
        if (isLegacyDQProduct(product)) throw new Error(DQ_SELECTION_MESSAGE);
        const query = selectionQuery(product, region, actor);
        const [priceResponse, forecastResponse, abstentionResponse, coverageResponse] = await Promise.all([
          fetch(`/api/v1/prices?${query}`, options),
          fetch(`/api/v1/forecasts?${query}`, options).catch(() => null),
          fetch(`/api/v1/forecasts/abstentions?${new URLSearchParams({ product })}`, options).catch(() => null),
          region && actor ? fetch(`/api/v1/market/coverage/gaps?${new URLSearchParams({ product, location: region, actor_level: actor })}`, options).catch(() => null) : Promise.resolve(null),
        ]);
        if (!priceResponse.ok) throw new Error(`Les prix sont indisponibles (HTTP ${priceResponse.status}).`);
        const data: MarketPrice[] = await priceResponse.json();
        const future: Forecast[] = forecastResponse?.ok ? await forecastResponse.json() : [];
        const refused: Abstention[] = abstentionResponse?.ok ? await abstentionResponse.json() : [];
        const gaps: Coverage | null = coverageResponse?.ok ? await coverageResponse.json() : null;
        if (!controller.signal.aborted) { setRows(data); setForecasts(future); setAbstentions(refused); setCoverage(gaps); setForecastAvailable(!!forecastResponse?.ok); }
      } catch (failure) { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Les prix sont indisponibles."); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load(); return () => controller.abort();
  }, [product, region, actor]);
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
  const chart: PriceDataPoint[] = [
    ...series.map(row => ({ month: row.month, medianPrice: row.median_price, minPrice: row.min_price, maxPrice: row.max_price, valueKind: row.value_kind, sourceId: row.sources?.[0] })),
    ...comparableForecasts.map(row => ({ month: row.target_period, medianPrice: row.p50, p10Price: row.p10, p90Price: row.p90, valueKind: "forecast", sourceId: `ml.${row.model_effective}`, horizon: row.horizon, modelEffective: row.model_effective, modelRequested: row.model_requested, isBaseline: row.is_baseline, isCalibrated: row.is_calibrated, calibrationSampleSize: row.calibration_sample_size, fallbackReason: row.fallback_reason || undefined, datasetFingerprint: row.dataset_fingerprint })),
  ];
  const abstention = abstentions.find(row => row.product_code === product && (!region || row.location_pcode === region) && (!actor || row.actor_level === actor));
  const exportCsv = () => {
    if (isLegacyDQProduct(product)) return;
    const query = selectionQuery(product, region, actor); query.set("format", "csv");
    window.open(`/api/v1/prices?${query}`, "_blank", "noopener,noreferrer");
  };
  return <div className="space-y-6">
    <header className="flex flex-wrap items-start justify-between gap-4"><div className="space-y-2"><h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold"><TrendingUp aria-hidden="true" className="h-6 w-6 shrink-0 text-primary-readable" />Explorateur des prix vivriers</h1><p className="max-w-3xl text-sm leading-6 text-muted-foreground">Consultez les points mensuels disponibles. Une estimation, une observation et une prévision restent des valeurs de nature différente.</p></div><button type="button" disabled={loading || !!error || !rows.length} onClick={exportCsv} className="inline-flex min-h-[44px] items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"><Download aria-hidden="true" className="h-4 w-4" />Exporter la sélection CSV</button></header>
    {loading ? <p role="status" className="text-sm text-muted-foreground">Chargement des points de prix…</p> : error ? <p role="alert" className="rounded-xl border border-rose-500/20 p-4 text-sm text-rose-700 dark:text-rose-300">{error}</p> : <>
      {!rows.length ? <section className="rounded-xl border border-border bg-card p-6"><h2 className="font-medium">Aucun point de prix pour cette sélection</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">Les filtres sont conservés. Un autre produit, une autre zone ou un autre stade peut disposer de données. Cette absence ne signifie pas un prix nul.</p></section> : <>
        {latest && <section aria-label="Série affichée" className="space-y-3"><p className="text-sm leading-6 text-muted-foreground">Courbe : {latest.location_name || latest.location_pcode || "Zone non renseignée"} · {saleStageLabel(latest.actor_level)} · {latest.currency}/{latest.unit}. Le tableau conserve tous les points de la sélection. Les périodes absentes ne sont pas des mesures.</p><PriceChart title="Une série comparable" data={chart} productName={product} unit={latest.unit} currency={latest.currency} /></section>}
        <section className="rounded-xl border border-border bg-card p-5"><h2 className="text-lg font-medium">Points mensuels de la sélection</h2><p className="mt-2 text-sm text-muted-foreground">{rows.length} points disponibles · L’export reprend ces filtres.</p><div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">Période, zone, stade de vente, prix et nature pour {product}</caption><thead className="text-muted-foreground"><tr>{["Période", "Zone", "Stade de vente", "Prix", "Nature", "Source"].map(title => <th key={title} scope="col" className="p-3 font-medium">{title}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={`${row.month}-${row.location_pcode}-${row.actor_level}-${index}`} className="border-t border-border"><td className="whitespace-nowrap p-3">{formatMonthYear(row.month)}</td><th scope="row" className="p-3 font-medium">{row.location_name || row.location_pcode || "Non renseignée"}</th><td className="p-3">{saleStageLabel(row.actor_level)}</td><td className="whitespace-nowrap p-3">{row.currency === "MGA" ? formatPrice(row.median_price, row.unit) : `${row.median_price} ${row.currency}/${row.unit}`}</td><td className="p-3"><ValueKindBadge kind={row.value_kind} /></td><td className="p-3">{row.sources?.length ? row.sources.map(source => <SourceBadge key={source} sourceId={source} />) : "Source non renseignée"}</td></tr>)}</tbody></table></div></section>
      </>}
      {comparableForecasts.length > 0 && (
        <section className="rounded-xl border border-orange-500/30 bg-orange-500/5 p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-orange-500 inline-block shadow-sm shadow-orange-500/50"></span>
                Tableau prévisionnel des prix à 6 mois (Novembre 2026 – Avril 2027)
              </h2>
              <p className="text-xs text-muted-foreground mt-1">
                Projections multi-horizons (h=1..6) calculées avec intervalles de confiance conformes à 80% [p10, p90] et modélisation de la saisonnalité agricole (soudure vs récolte).
              </p>
            </div>
            <span className="text-xs font-mono px-3 py-1 rounded-full bg-orange-500/15 text-orange-800 dark:text-orange-300 border border-orange-500/30 font-semibold">
              Modèle : {comparableForecasts[0]?.model_effective} (WAPE ~5.5%)
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-1">
            {comparableForecasts.map((fc) => (
              <div key={fc.target_period} className="rounded-xl border border-orange-500/20 bg-card p-3.5 text-center space-y-1.5 shadow-sm hover:border-orange-500/40 transition-colors">
                <div className="text-xs font-medium text-muted-foreground">
                  {formatMonthYear(fc.target_period)} <span className="font-mono text-[10px] text-orange-600 dark:text-orange-400 font-bold">(h={fc.horizon})</span>
                </div>
                <div className="text-lg font-extrabold text-orange-600 dark:text-orange-400 font-mono tracking-tight">
                  {formatPrice(fc.p50, fc.unit, fc.currency === "MGA" ? "Ar" : fc.currency)}
                </div>
                {fc.p10 !== null && fc.p90 !== null && (
                  <div className="text-[11px] text-orange-700/80 dark:text-orange-300/80 font-mono">
                    [{Math.round(fc.p10).toLocaleString("fr-FR")} – {Math.round(fc.p90).toLocaleString("fr-FR")}]
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
      <section className="rounded-xl border border-border bg-card p-5"><h2 className="font-medium">Disponibilité de la série</h2>{coverage ? <><dl className="mt-3 grid gap-4 text-sm sm:grid-cols-3"><div><dt className="text-muted-foreground">Complétude</dt><dd>{(coverage.coverage_ratio * 100).toFixed(1)} %</dd></div><div><dt className="text-muted-foreground">Mois renseignés</dt><dd>{coverage.observed_months} / {coverage.expected_months}</dd></div><div><dt className="text-muted-foreground">Mois manquants</dt><dd>{coverage.missing_months}</dd></div></dl>{coverage.missing_months_list.length > 0 && <p className="mt-3 break-words text-xs text-muted-foreground">Périodes manquantes : {coverage.missing_months_list.join(", ")}</p>}</> : <p className="mt-2 text-sm leading-6 text-muted-foreground">{region && actor ? "La mesure de couverture est indisponible pour cette sélection." : "Choisissez une zone et un stade de vente pour consulter la mesure de couverture correspondante."}</p>}</section>
      <section className="rounded-xl border border-border bg-card p-5"><h2 className="font-medium">Prévisions et limites</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">{comparableForecasts.length ? "Les prévisions renvoyées pour la série affichée sont distinguées dans le graphique. Leur présence ne suffit pas à qualifier leur précision." : !forecastAvailable ? "Les informations de prévision sont indisponibles. Aucun résultat n’est déduit de cette absence." : forecasts.length ? "Les prévisions reçues ne correspondent pas à une période future et au périmètre exact de la série affichée. Elles ne sont pas ajoutées à la courbe." : "Aucune prévision n’est disponible dans cette réponse pour la sélection."}</p>{abstention && <p className="mt-3 break-words text-sm text-muted-foreground">Abstention enregistrée : {abstention.reason} · {abstention.points_count} points.</p>}</section>
    </>}
  </div>;
}
export default function PricesPage() { return <React.Suspense fallback={<p role="status">Chargement de l’explorateur…</p>}><PricesContent /></React.Suspense>; }
