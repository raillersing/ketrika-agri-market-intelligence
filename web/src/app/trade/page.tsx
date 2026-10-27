"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowLeftRight } from "lucide-react";
import { DEFAULT_PRODUCT } from "@/lib/market-overview";
import { DQ_SELECTION_MESSAGE, isLegacyDQProduct } from "@/lib/market-filters";
import { formatMonthYear, formatNumber } from "@/lib/formatters";
import { SourceBadge } from "@/components/ui/SourceBadge";
import { ValueKindBadge } from "@/components/ui/ValueKindBadge";

type Trade = { product_code: string; flow: string; month: string; weight_tons: number; value_mga: number | null; value_usd: number | null; value_kind: string; sources: string[] };
function TradeContent() {
  const product = useSearchParams().get("product") || DEFAULT_PRODUCT;
  const [rows, setRows] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setRows([]); setError(null); setLoading(true);
    async function load() {
      try {
        if (isLegacyDQProduct(product)) throw new Error(DQ_SELECTION_MESSAGE);
        const response = await fetch(`/api/v1/trade?${new URLSearchParams({ product })}`, { credentials: "include", signal: controller.signal });
        if (!response.ok) throw new Error(`Les échanges sont indisponibles (HTTP ${response.status}).`);
        const data: Trade[] = await response.json();
        if (!controller.signal.aborted) setRows(data);
      } catch (failure) { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Les échanges sont indisponibles."); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load(); return () => controller.abort();
  }, [product]);
  const total = (flow: string) => { const selected = rows.filter(row => row.flow === flow); return selected.length ? selected.reduce((sum, row) => sum + row.weight_tons, 0) : null; };
  return <div className="space-y-6"><header className="space-y-2"><h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold"><ArrowLeftRight aria-hidden="true" className="h-6 w-6 shrink-0 text-primary-readable" />Commerce extérieur</h1><p className="max-w-3xl text-sm leading-6 text-muted-foreground">Flux mensuels disponibles pour le produit sélectionné. Les dates et les sources sont conservées ; ces données ne mesurent pas les stocks des marchés.</p></header>
    {loading ? <p role="status" className="text-sm text-muted-foreground">Chargement des échanges…</p> : error ? <p role="alert" className="rounded-xl border border-rose-500/20 p-4 text-sm text-rose-700 dark:text-rose-300">{error}</p> : !rows.length ? <section className="rounded-xl border border-border bg-card p-6"><h2 className="font-medium">Aucun flux disponible pour ce produit</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">Une absence de données ne signifie pas que les importations ou les exportations sont nulles.</p></section> : <>
      <div className="grid gap-3 sm:grid-cols-2">{[["Importations enregistrées", total("import")], ["Exportations enregistrées", total("export")]].map(([label, value]) => <div key={String(label)} className="rounded-xl border border-border bg-card p-5"><h2 className="text-sm text-muted-foreground">{label}</h2><p className="mt-2 text-2xl font-semibold">{value === null ? "Non renseigné" : `${formatNumber(Number(value), 1)} tonnes`}</p><p className="mt-2 text-xs leading-5 text-muted-foreground">Somme des lignes disponibles dans la réponse ; ne mesure pas une couverture exhaustive.</p></div>)}</div>
      <section className="rounded-xl border border-border bg-card p-5"><h2 className="font-medium">Flux mensuels enregistrés</h2><div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">Échanges mensuels pour {product}</caption><thead className="text-muted-foreground"><tr>{["Période", "Flux", "Poids", "Valeur MGA", "Valeur USD", "Nature", "Sources"].map(title => <th key={title} scope="col" className="p-3 font-medium">{title}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={`${row.month}-${row.flow}-${index}`} className="border-t border-border"><th scope="row" className="whitespace-nowrap p-3 font-medium">{formatMonthYear(row.month)}</th><td className="p-3">{row.flow === "import" ? "Importation" : row.flow === "export" ? "Exportation" : "Flux non renseigné"}</td><td className="whitespace-nowrap p-3">{formatNumber(row.weight_tons, 1)} t</td><td className="p-3">{formatNumber(row.value_mga)}</td><td className="p-3">{formatNumber(row.value_usd)}</td><td className="p-3"><ValueKindBadge kind={row.value_kind} /></td><td className="p-3">{row.sources?.length ? row.sources.map(source => <SourceBadge key={source} sourceId={source} />) : "Source non renseignée"}</td></tr>)}</tbody></table></div></section>
    </>}
    <p className="text-sm leading-6 text-muted-foreground">La dépendance aux importations n’est pas calculée dans cette vue. Les flux seuls ne suffisent pas à établir ce ratio.</p>
  </div>;
}
export default function TradePage() { return <React.Suspense fallback={<p role="status">Chargement du commerce extérieur…</p>}><TradeContent /></React.Suspense>; }
