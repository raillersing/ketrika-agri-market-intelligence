"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { KpiCard } from "@/components/ui/KpiCard";
import { ValueKindBadge } from "@/components/ui/ValueKindBadge";
import { PriceChart } from "@/components/charts/PriceChart";
import { DEFAULT_PRODUCT, summarizePrices, type MarketPrice } from "@/lib/market-overview";
import { DQ_SELECTION_MESSAGE, isLegacyDQProduct, saleStageLabel } from "@/lib/market-filters";
import { formatMonthYear } from "@/lib/formatters";

interface MarketAlert { product_code: string | null; location_pcode: string | null; }

function OverviewContent() {
  const params = useSearchParams();
  const product = params.get("product") || DEFAULT_PRODUCT;
  const region = params.get("region") || "";
  const actor = params.get("actor") || "";
  const [rows, setRows] = useState<MarketPrice[]>([]);
  const [alerts, setAlerts] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [alertError, setAlertError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    const options = { credentials: "include" as const, signal: controller.signal };
    const query = new URLSearchParams({ product });
    if (region) query.set("location", region);
    if (actor) query.set("actor_level", actor);
    setLoading(true); setError(null); setRows([]); setAlerts(null); setAlertError(false);
    if (isLegacyDQProduct(product)) {
      setError(DQ_SELECTION_MESSAGE); setLoading(false);
      return () => controller.abort();
    }
    async function loadPrices() {
      try {
        const response = await fetch(`/api/v1/prices?${query}`, options);
        if (!response.ok) throw new Error(`Prix indisponibles (HTTP ${response.status}).`);
        const data: MarketPrice[] = await response.json();
        if (!controller.signal.aborted) setRows(data);
      } catch (err) {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Prix indisponibles.");
      } finally { if (!controller.signal.aborted) setLoading(false); }
    }
    async function loadAlerts() {
      try {
        const response = await fetch("/api/v1/alerts?state=open", options);
        if (!response.ok) throw new Error("Alertes indisponibles");
        const data: MarketAlert[] = await response.json();
        if (!controller.signal.aborted) setAlerts(data.filter((a) => a.product_code === product && (!region || a.location_pcode === region)).length);
      } catch { if (!controller.signal.aborted) setAlertError(true); }
    }
    void loadPrices(); void loadAlerts();
    return () => controller.abort();
  }, [product, region, actor]);

  const { latest, series, sources } = summarizePrices(rows);
  const scope = latest ? `${latest.location_name || latest.location_pcode} · ${saleStageLabel(latest.actor_level)} · ${formatMonthYear(latest.month)}` : "Aucune série disponible";
  const query = new URLSearchParams(params.toString());
  query.set("product", product);
  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="glass-panel p-6 sm:p-8 rounded-3xl space-y-3">
        <h1 className="text-2xl sm:text-3xl font-extrabold text-foreground">Tableau de bord de veille de marché PPN</h1>
        <p className="text-sm text-muted-foreground">Données disponibles pour {product}. Les estimations sont distinguées des observations ; les sources et dates restent à examiner.</p>
        <div className="flex flex-wrap gap-4 text-sm text-primary-readable">
          <Link href={`/prices?${query}`}>Explorer les prix</Link>
          <Link href="/sources">Consulter les sources</Link>
          <Link href="/bulletins">Bulletins</Link>
          <Link href="/copilot">Copilote</Link>
        </div>
      </div>
      {loading && <p role="status" className="text-muted-foreground">Chargement des données…</p>}
      {error && <p role="alert" className="rounded-xl p-4 bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">{error}</p>}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <KpiCard title="Dernier point disponible" value={latest?.median_price.toLocaleString("fr-FR")} unit={latest ? `${latest.currency}/${latest.unit}` : undefined} valueKind={latest?.value_kind} sources={latest?.sources} subtitle={scope} />
        <KpiCard title="Points mensuels disponibles" value={loading || error ? null : rows.length} sources={sources} subtitle="Dans la sélection ; ce compte ne mesure pas la couverture nationale." />
        <KpiCard title="Alertes ouvertes enregistrées" value={alerts} subtitle={alertError ? "Historique indisponible." : "Produit et zone sélectionnés ; tous stades de vente. Ces alertes ne constituent pas un diagnostic validé."} />
        <KpiCard title="Couverture des stocks" value={null} subtitle="Non évaluée ici : aucun nombre de jours de couverture n’est déduit des prix." />
      </div>
      {!loading && !error && <PriceChart title={`Une série comparable — ${scope}`} productName={product} unit={latest?.unit} currency={latest?.currency} data={series.map((r) => ({ month: r.month, medianPrice: r.median_price, minPrice: r.min_price, maxPrice: r.max_price, valueKind: r.value_kind, sourceId: r.sources[0] }))} />}
      <div className="glass-card rounded-2xl p-4 space-y-3">
        <h2 className="text-foreground font-semibold">Derniers points de la sélection</h2>
        {!loading && !error && !rows.length && <p className="text-muted-foreground">Aucune donnée disponible pour ces filtres.</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-muted-foreground">
            <thead><tr><th className="p-2">Mois</th><th className="p-2">Zone / stade</th><th className="p-2">Prix médian</th><th className="p-2">Nature</th><th className="p-2">Sources</th></tr></thead>
            <tbody>{[...rows].sort((a, b) => b.month.localeCompare(a.month)).slice(0, 10).map((r, i) => <tr key={`${r.month}-${r.location_pcode}-${r.actor_level}-${i}`}>
              <td className="p-2 whitespace-nowrap">{formatMonthYear(r.month)}</td><td className="p-2">{r.location_name || r.location_pcode} · {saleStageLabel(r.actor_level)}</td><td className="p-2 whitespace-nowrap">{r.median_price.toLocaleString("fr-FR")} {r.currency}/{r.unit}</td><td className="p-2"><ValueKindBadge kind={r.value_kind} /></td><td className="p-2">{r.sources.join(", ") || "Non renseignées"}</td>
            </tr>)}</tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function OverviewPage() {
  return <React.Suspense fallback={<p role="status">Chargement…</p>}><OverviewContent /></React.Suspense>;
}
