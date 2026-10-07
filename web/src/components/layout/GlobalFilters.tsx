"use client";

import React, { useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Filter, RotateCcw } from "lucide-react";

const PRODUCTS = [
  { code: "rice_milled", label: "Riz blanc local (makalioka/tsipala)" },
  { code: "rice_paddy", label: "Paddy (riz non usiné)" },
  { code: "rice_imported", label: "Riz importé (stock/parfumé)" },
  { code: "maize_grain", label: "Maïs grain jaune/blanc" },
  { code: "cassava_fresh", label: "Manioc frais / cossettes" },
  { code: "oil_edible", label: "Huile végétale alimentaire" },
  { code: "sugar_refined", label: "Sucre blanc raffiné" },
];

const REGIONS = [
  { pcode: "", label: "Toutes les régions (National)" },
  { pcode: "MG11", label: "Analamanga (Antananarivo)" },
  { pcode: "MG12", label: "Vakinankaratne (Antsirabe)" },
  { pcode: "MG13", label: "Itasy (Miarinarivo)" },
  { pcode: "MG14", label: "Bongolava (Tsiroanomandidy)" },
  { pcode: "MG21", label: "Haute Matsiatra (Fianarantsoa)" },
  { pcode: "MG22", label: "Amoron'i Mania (Ambositra)" },
  { pcode: "MG23", label: "Vatovavy (Mananjary)" },
  { pcode: "MG24", label: "Fitovinany (Manakara)" },
  { pcode: "MG25", label: "Atsimo-Atsinanana (Farafangana)" },
  { pcode: "MG26", label: "Ihorombe (Ihosy)" },
  { pcode: "MG31", label: "Atsinanana (Toamasina)" },
  { pcode: "MG32", label: "Analanjirofo (Fénérive-Est)" },
  { pcode: "MG33", label: "Alaotra-Mangoro (Ambatondrazaka)" },
  { pcode: "MG41", label: "Boeny (Mahajanga)" },
  { pcode: "MG42", label: "Sofia (Antsohihy)" },
  { pcode: "MG43", label: "Betsiboka (Maevatanana)" },
  { pcode: "MG44", label: "Melaky (Maintirano)" },
  { pcode: "MG51", label: "Atsimo-Andrefana (Toliara)" },
  { pcode: "MG52", label: "Androy (Ambovombe)" },
  { pcode: "MG53", label: "Anosy (Taolagnaro)" },
  { pcode: "MG54", label: "Menabe (Morondava)" },
  { pcode: "MG61", label: "DIANA (Antsiranana)" },
  { pcode: "MG62", label: "SAVA (Sambava)" },
];

const ACTORS = [
  { code: "", label: "Tous niveaux" },
  { code: "retail", label: "Détail (Consommateur)" },
  { code: "wholesale", label: "Gros / Demi-gros" },
  { code: "producer", label: "Producteur (Bord champ)" },
];

export function GlobalFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const currentProduct = searchParams.get("product") || "rice_milled";
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
    params.set("product", "rice_milled");
    startTransition(() => {
      router.push(`${pathname}?${params.toString()}`);
    });
  };

  return (
    <div className="bg-card border-b border-border px-6 py-3 flex flex-wrap items-center justify-between gap-4 sticky top-0 z-10 backdrop-blur-sm bg-card/95">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground mr-1">
          <Filter className="w-3.5 h-3.5 text-emerald-600" />
          <span>Filtres :</span>
        </div>

        {/* Produit selector */}
        <select
          value={currentProduct}
          onChange={(e) => updateParam("product", e.target.value)}
          disabled={isPending}
          className="text-xs font-medium bg-background text-foreground border border-input rounded-md px-2.5 py-1.5 shadow-sm focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
        >
          {PRODUCTS.map((p) => (
            <option key={p.code} value={p.code}>
              {p.label}
            </option>
          ))}
        </select>

        {/* Région selector */}
        <select
          value={currentRegion}
          onChange={(e) => updateParam("region", e.target.value)}
          disabled={isPending}
          className="text-xs font-medium bg-background text-foreground border border-input rounded-md px-2.5 py-1.5 shadow-sm focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
        >
          {REGIONS.map((r) => (
            <option key={r.pcode} value={r.pcode}>
              {r.label}
            </option>
          ))}
        </select>

        {/* Niveau d'acteur selector */}
        <select
          value={currentActor}
          onChange={(e) => updateParam("actor", e.target.value)}
          disabled={isPending}
          className="text-xs font-medium bg-background text-foreground border border-input rounded-md px-2.5 py-1.5 shadow-sm focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
        >
          {ACTORS.map((a) => (
            <option key={a.code} value={a.code}>
              {a.label}
            </option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-2">
        {(currentRegion || currentActor || currentProduct !== "rice_milled") && (
          <button
            onClick={resetFilters}
            disabled={isPending}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded"
            title="Réinitialiser les filtres"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Réinitialiser</span>
          </button>
        )}
      </div>
    </div>
  );
}
