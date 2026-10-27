"use client";

import React, { useId, useTransition, useEffect, useState } from "react";
import { DEFAULT_PRODUCT } from "@/lib/market-overview";
import { businessProducts, DQ_SELECTION_MESSAGE, filterFieldsForPath, isLegacyDQProduct, resetVisibleFilters, SALE_STAGES, type ProductReference } from "@/lib/market-filters";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { RotateCcw } from "lucide-react";

export function GlobalFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const [products, setProducts] = useState<ProductReference[]>([]);
  const [regions, setRegions] = useState<{ pcode: string; name: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [referenceError, setReferenceError] = useState(false);
  const id = useId();
  const fields = filterFieldsForPath(pathname);
  const showProduct = fields.includes("product");
  const showRegion = fields.includes("region");
  const showActor = fields.includes("actor");

  useEffect(() => {
    if (!showProduct) return;
    const controller = new AbortController();
    setLoading(true); setReferenceError(false);
    async function load() {
      try {
        const responses = await Promise.all([
          fetch("/api/v1/products", { signal: controller.signal }),
          ...(showRegion ? [fetch("/api/v1/locations?level=1", { signal: controller.signal })] : []),
        ]);
        if (responses.some(response => !response.ok)) throw new Error("Référentiels indisponibles");
        const data = await Promise.all(responses.map(response => response.json()));
        if (!controller.signal.aborted) {
          setProducts(businessProducts(data[0]));
          setRegions(showRegion ? data[1].filter((row: { pcode: string | null }) => row.pcode) : []);
        }
      } catch { if (!controller.signal.aborted) setReferenceError(true); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load();
    return () => controller.abort();
  }, [showProduct, showRegion]);

  if (!fields.length) return null;
  const product = searchParams.get("product") || DEFAULT_PRODUCT;
  const region = searchParams.get("region") || "";
  const actor = searchParams.get("actor") || "";
  const dqSelected = isLegacyDQProduct(product);
  const update = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value); else params.delete(key);
    startTransition(() => router.push(`${pathname}${params.size ? `?${params}` : ""}`));
  };
  const reset = () => {
    const params = resetVisibleFilters(searchParams.toString(), fields);
    startTransition(() => router.push(`${pathname}${params.size ? `?${params}` : ""}`));
  };
  const customized = product !== DEFAULT_PRODUCT || (showRegion && !!region) || (showActor && !!actor);
  const control = "min-h-[44px] w-full max-w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60";

  return <section aria-label="Filtres de cette page" aria-busy={isPending || loading} className="border-b border-border bg-header px-4 py-3 md:px-8">
    <div className="flex flex-wrap items-end gap-3">
      <label className="flex min-w-0 max-w-full flex-col gap-1 text-xs text-muted-foreground"><span>Produit</span>
        <select value={dqSelected ? "" : product} onChange={event => update("product", event.target.value)} disabled={isPending || loading} className={control}>
          {dqSelected && <option value="" disabled>Choisissez un produit</option>}
          {!dqSelected && !products.some(row => row.product_code === product) && <option value={product}>{loading ? "Chargement du catalogue…" : `Sélection non reconnue : ${product}`}</option>}
          {products.map(row => <option key={row.product_code} value={row.product_code}>{row.canonical_name_fr}</option>)}
        </select>
      </label>
      {showRegion && <label className="flex min-w-0 max-w-full flex-col gap-1 text-xs text-muted-foreground"><span>Zone</span>
        <select value={region} onChange={event => update("region", event.target.value)} disabled={isPending || loading} className={control}>
          <option value="">Toutes les zones</option>
          {region && !regions.some(row => row.pcode === region) && <option value={region}>Sélection non reconnue : {region}</option>}
          {regions.map(row => <option key={row.pcode} value={row.pcode}>{row.name}</option>)}
        </select>
      </label>}
      {showActor && <label className="flex min-w-0 max-w-full flex-col gap-1 text-xs text-muted-foreground"><span>Stade de vente</span>
        <select value={actor} aria-describedby={`${id}-stages`} onChange={event => update("actor", event.target.value)} disabled={isPending} className={control}>
          {!SALE_STAGES.some(stage => stage.code === actor) && <option value={actor}>Stade non reconnu : {actor}</option>}
          {SALE_STAGES.map(stage => <option key={stage.code} value={stage.code}>{stage.label}</option>)}
        </select>
      </label>}
      {customized && <button type="button" onClick={reset} disabled={isPending} className="inline-flex min-h-[44px] items-center gap-2 rounded-lg px-3 text-sm text-muted-foreground hover:bg-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"><RotateCcw aria-hidden="true" className="h-4 w-4" />Réinitialiser les filtres</button>}
    </div>
    {showActor && <p id={`${id}-stages`} className="mt-2 text-xs leading-5 text-muted-foreground">Le stade distingue le prix au producteur, en gros et au détail. « Non renseigné » conserve les prix dont le stade est inconnu.</p>}
    <p className="mt-1 text-xs leading-5 text-muted-foreground">Le catalogue liste les produits suivis. La disponibilité des données dépend de votre sélection.</p>
    {dqSelected && <p role="alert" className="mt-2 text-sm text-amber-700 dark:text-amber-300">{DQ_SELECTION_MESSAGE}</p>}
    {referenceError && <p role="alert" className="mt-2 text-sm text-amber-700 dark:text-amber-300">Catalogue indisponible. Les données et la sélection ne sont pas remplacées.</p>}
    {isPending && <p role="status" className="mt-2 text-xs text-muted-foreground">Actualisation de la sélection…</p>}
  </section>;
}
