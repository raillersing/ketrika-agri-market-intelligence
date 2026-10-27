"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { MapPin, RefreshCw } from "lucide-react";
import { DEFAULT_PRODUCT } from "@/lib/market-overview";
import { DQ_SELECTION_MESSAGE, isLegacyDQProduct } from "@/lib/market-filters";
import { formatMonthYear, formatPrice } from "@/lib/formatters";
import { ValueKindBadge } from "@/components/ui/ValueKindBadge";
import { SourceBadge } from "@/components/ui/SourceBadge";

type TerritorialPrice = { product_code: string; location_pcode: string; location_name: string | null; month: string; median_price: number; currency: string; unit: string; value_kind: string; sources: string[] };
function MapContent() {
  const searchParams = useSearchParams();
  const product = searchParams.get("product") || DEFAULT_PRODUCT;
  const [rows, setRows] = useState<TerritorialPrice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(null); setRows([]);
    async function load() {
      try {
        if (isLegacyDQProduct(product)) throw new Error(DQ_SELECTION_MESSAGE);
        const response = await fetch(`/api/v1/prices/latest?${new URLSearchParams({ product, level: "1" })}`, { credentials: "include", signal: controller.signal });
        if (!response.ok) throw new Error(`Les prix par territoire sont indisponibles (HTTP ${response.status}).`);
        const data: TerritorialPrice[] = await response.json();
        if (!controller.signal.aborted) setRows(data);
      } catch (failure) { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Les prix par territoire sont indisponibles."); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load();
    return () => controller.abort();
  }, [product]);
  return <div className="space-y-6">
    <header className="space-y-2"><h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold text-foreground"><MapPin aria-hidden="true" className="h-6 w-6 shrink-0 text-primary-readable" />Prix par territoire</h1><p className="text-sm leading-6 text-muted-foreground">Les derniers points disponibles par zone, avec leur date et leur source.</p></header>
    <section aria-labelledby="map-availability" className="rounded-xl border border-border bg-card p-5">
      <h2 id="map-availability" className="font-medium text-foreground">Carte géographique en préparation</h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">Les limites géographiques doivent être vérifiées avant affichage. Consultez les données disponibles dans le tableau ci-dessous.</p>
    </section>
    {error && <p role="alert" className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4 text-sm text-rose-700 dark:text-rose-300">{error}</p>}
    {loading ? <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><RefreshCw aria-hidden="true" className="h-4 w-4 animate-spin" />Chargement des prix par territoire…</p> : !error && <section className="rounded-xl border border-border bg-card p-5">
      <h2 className="text-lg font-medium">Derniers points par zone</h2>
      <p className="my-3 text-sm leading-6 text-muted-foreground">Les dates peuvent différer selon les zones : ce tableau ne constitue pas un classement de prix à une même date. Le stade de vente n’est pas communiqué dans cette vue.</p>
      {!rows.length ? <p role="status" className="py-6 text-sm text-muted-foreground">Aucun point territorial disponible pour ce produit. Cela ne signifie pas que son prix est nul.</p> : <div className="relative overflow-x-auto"><table className="w-full text-left text-sm">
        <caption className="sr-only">Prix par territoire, périodes et sources pour {product}</caption>
        <thead className="text-muted-foreground"><tr>{["Zone", "Période", "Prix", "Nature", "Source", "Historique"].map(title => <th key={title} scope="col" className="p-3 font-medium">{title}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => <tr key={`${row.location_pcode}-${index}`} className="border-t border-border">
          <th scope="row" className="p-3 font-medium">{row.location_name || row.location_pcode || "Zone non renseignée"}</th><td className="whitespace-nowrap p-3">{formatMonthYear(row.month)}</td>
          <td className="whitespace-nowrap p-3">{row.currency === "MGA" ? formatPrice(row.median_price, row.unit) : `${row.median_price} ${row.currency}/${row.unit}`}</td><td className="p-3"><ValueKindBadge kind={row.value_kind} /></td>
          <td className="p-3">{row.sources?.length ? row.sources.map(source => <SourceBadge key={source} sourceId={source} />) : "Source non renseignée"}</td>
          <td className="p-3"><Link className="inline-flex min-h-[44px] items-center rounded px-2 text-primary-readable underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring" href={`/prices?${new URLSearchParams({ product, ...(row.location_pcode ? { region: row.location_pcode } : {}) })}`}>Voir la série<span className="sr-only"> — {row.location_name || row.location_pcode}</span></Link></td>
        </tr>)}</tbody></table></div>}
    </section>}
  </div>;
}
export default function MapPage() { return <React.Suspense fallback={<p role="status">Chargement de la vue territoriale…</p>}><MapContent /></React.Suspense>; }
