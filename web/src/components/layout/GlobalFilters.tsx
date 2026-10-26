"use client";

import React, { useTransition, useEffect, useState } from "react";
import { DEFAULT_PRODUCT } from "@/lib/market-overview";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Check,
  ChevronDown,
  Filter,
  MapPin,
  RotateCcw,
  Tag,
  Users,
  Wheat,
} from "lucide-react";



const ACTORS = [
  { code: "", label: "Tous les niveaux" },
  { code: "retail", label: "Détail (Consommateur)" },
  { code: "wholesale", label: "Gros / Demi-gros" },
  { code: "producer", label: "Producteur (Bord champ)" },
];

export function GlobalFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const [products, setProducts] = useState<{ code: string; label: string }[]>([]);
  const [regions, setRegions] = useState<{ pcode: string; label: string }[]>([]);
  const [referenceError, setReferenceError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const responses = await Promise.all([fetch("/api/v1/products", { signal: controller.signal }), fetch("/api/v1/locations?level=1", { signal: controller.signal })]);
        if (responses.some((response) => !response.ok)) throw new Error("Référentiels indisponibles");
        const [ps, ls] = await Promise.all(responses.map((response) => response.json()));
        if (!controller.signal.aborted) {
          setProducts(ps.map((p: { product_code: string; canonical_name_fr: string }) => ({ code: p.product_code, label: p.canonical_name_fr })));
          setRegions(ls.filter((l: { pcode: string | null }) => l.pcode).map((l: { pcode: string; name: string }) => ({ pcode: l.pcode, label: l.name })));
        }
      } catch { if (!controller.signal.aborted) setReferenceError(true); }
    }
    void load();
    return () => controller.abort();
  }, []);

  const currentProduct = searchParams.get("product") || DEFAULT_PRODUCT;
  const currentRegion = searchParams.get("region") || "";
  const currentActor = searchParams.get("actor") || "";

  const updateParam = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    startTransition(() => {
      router.push(`${pathname}?${params.toString()}`);
    });
  };

  const resetFilters = () => {
    const params = new URLSearchParams();
    params.set("product", DEFAULT_PRODUCT);
    startTransition(() => {
      router.push(`${pathname}?${params.toString()}`);
    });
  };

  const isCustom = currentProduct !== DEFAULT_PRODUCT || currentRegion !== "" || currentActor !== "";

  return (
    <div className="bg-background/60 border-b border-border px-3 md:px-6 py-2.5 flex flex-wrap items-center justify-between gap-3 sticky top-16 z-10 backdrop-blur-md [&_select]:max-w-full">
      <div className="flex min-w-0 max-w-full flex-wrap items-center gap-2.5">
        {/* Label */}
        <div className="flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider text-muted-foreground mr-1">
          <Filter className="w-3.5 h-3.5 text-primary-readable" />
          <span>Filtres :</span>
        </div>

        {/* Produit Selector Pill */}
        <div className="relative inline-flex max-w-full items-center">
          <Wheat className="w-3.5 h-3.5 text-primary-readable absolute left-3 pointer-events-none" />
          <select
            value={currentProduct}
            onChange={(e) => updateParam("product", e.target.value)}
            disabled={isPending}
            className="text-xs font-medium bg-card/90 text-foreground border border-border hover:border-emerald-500/40 rounded-xl pl-8 pr-7 py-1.5 shadow-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer transition-all appearance-none"
          >
            {!products.some((p) => p.code === currentProduct) && <option value={currentProduct}>{currentProduct}</option>}
            {products.map((p) => (
              <option key={p.code} value={p.code} className="bg-card text-foreground">
                {p.label}
              </option>
            ))}
          </select>
          <ChevronDown className="w-3 h-3 text-muted-foreground absolute right-2.5 pointer-events-none" />
        </div>

        {/* Région Selector Pill */}
        <div className="relative inline-flex max-w-full items-center">
          <MapPin className="w-3.5 h-3.5 text-sky-700 dark:text-sky-400 absolute left-3 pointer-events-none" />
          <select
            value={currentRegion}
            onChange={(e) => updateParam("region", e.target.value)}
            disabled={isPending}
            className="text-xs font-medium bg-card/90 text-foreground border border-border hover:border-sky-500/40 rounded-xl pl-8 pr-7 py-1.5 shadow-sm focus:outline-none focus:ring-1 focus:ring-sky-500 cursor-pointer transition-all appearance-none"
          >
            {<option value="">Toutes les zones</option>}
            {currentRegion && !regions.some((r) => r.pcode === currentRegion) && <option value={currentRegion}>{currentRegion}</option>}
            {regions.map((r) => (
              <option key={r.pcode} value={r.pcode} className="bg-card text-foreground">
                {r.label}
              </option>
            ))}
          </select>
          <ChevronDown className="w-3 h-3 text-muted-foreground absolute right-2.5 pointer-events-none" />
        </div>

        {/* Niveau Acteur Selector Pill */}
        <div className="relative inline-flex max-w-full items-center">
          <Users className="w-3.5 h-3.5 text-purple-700 dark:text-purple-400 absolute left-3 pointer-events-none" />
          <select
            value={currentActor}
            onChange={(e) => updateParam("actor", e.target.value)}
            disabled={isPending}
            className="text-xs font-medium bg-card/90 text-foreground border border-border hover:border-purple-500/40 rounded-xl pl-8 pr-7 py-1.5 shadow-sm focus:outline-none focus:ring-1 focus:ring-purple-500 cursor-pointer transition-all appearance-none"
          >
            {ACTORS.map((a) => (
              <option key={a.code} value={a.code} className="bg-card text-foreground">
                {a.label}
              </option>
            ))}
          </select>
          <ChevronDown className="w-3 h-3 text-muted-foreground absolute right-2.5 pointer-events-none" />
        </div>

        {/* Loading indicator */}
        {referenceError && <span role="alert" className="text-xs text-amber-700 dark:text-amber-300">Référentiels indisponibles</span>}
        {isPending && (
          <span className="text-[11px] text-primary-readable flex items-center gap-1.5 animate-pulse pl-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Actualisation...
          </span>
        )}
      </div>

      {/* Right: Reset Action */}
      <div className="flex items-center gap-2">
        {isCustom && (
          <button
            onClick={resetFilters}
            disabled={isPending}
            className="inline-flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground hover:text-foreground px-2.5 py-1 rounded-lg hover:bg-foreground/[0.06] transition-colors"
            title="Réinitialiser tous les filtres"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Réinitialiser</span>
          </button>
        )}
      </div>
    </div>
  );
}
