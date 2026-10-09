"use client";

import React, { useTransition } from "react";
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
  { code: "", label: "Tous niveaux (Agrégé)" },
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

  const isCustom = currentProduct !== "rice_milled" || currentRegion !== "" || currentActor !== "";

  return (
    <div className="bg-slate-950/60 border-b border-white/[0.07] px-6 py-2.5 flex flex-wrap items-center justify-between gap-3 sticky top-16 z-10 backdrop-blur-md">
      <div className="flex flex-wrap items-center gap-2.5">
        {/* Label */}
        <div className="flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider text-slate-400 mr-1">
          <Filter className="w-3.5 h-3.5 text-emerald-400" />
          <span>Filtres :</span>
        </div>

        {/* Produit Selector Pill */}
        <div className="relative inline-flex items-center">
          <Wheat className="w-3.5 h-3.5 text-emerald-400 absolute left-3 pointer-events-none" />
          <select
            value={currentProduct}
            onChange={(e) => updateParam("product", e.target.value)}
            disabled={isPending}
            className="text-xs font-medium bg-slate-900/90 text-slate-200 border border-white/[0.1] hover:border-emerald-500/40 rounded-xl pl-8 pr-7 py-1.5 shadow-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer transition-all appearance-none"
          >
            {PRODUCTS.map((p) => (
              <option key={p.code} value={p.code} className="bg-slate-900 text-slate-200">
                {p.label}
              </option>
            ))}
          </select>
          <ChevronDown className="w-3 h-3 text-slate-400 absolute right-2.5 pointer-events-none" />
        </div>

        {/* Région Selector Pill */}
        <div className="relative inline-flex items-center">
          <MapPin className="w-3.5 h-3.5 text-sky-400 absolute left-3 pointer-events-none" />
          <select
            value={currentRegion}
            onChange={(e) => updateParam("region", e.target.value)}
            disabled={isPending}
            className="text-xs font-medium bg-slate-900/90 text-slate-200 border border-white/[0.1] hover:border-sky-500/40 rounded-xl pl-8 pr-7 py-1.5 shadow-sm focus:outline-none focus:ring-1 focus:ring-sky-500 cursor-pointer transition-all appearance-none"
          >
            {REGIONS.map((r) => (
              <option key={r.pcode} value={r.pcode} className="bg-slate-900 text-slate-200">
                {r.label}
              </option>
            ))}
          </select>
          <ChevronDown className="w-3 h-3 text-slate-400 absolute right-2.5 pointer-events-none" />
        </div>

        {/* Niveau Acteur Selector Pill */}
        <div className="relative inline-flex items-center">
          <Users className="w-3.5 h-3.5 text-purple-400 absolute left-3 pointer-events-none" />
          <select
            value={currentActor}
            onChange={(e) => updateParam("actor", e.target.value)}
            disabled={isPending}
            className="text-xs font-medium bg-slate-900/90 text-slate-200 border border-white/[0.1] hover:border-purple-500/40 rounded-xl pl-8 pr-7 py-1.5 shadow-sm focus:outline-none focus:ring-1 focus:ring-purple-500 cursor-pointer transition-all appearance-none"
          >
            {ACTORS.map((a) => (
              <option key={a.code} value={a.code} className="bg-slate-900 text-slate-200">
                {a.label}
              </option>
            ))}
          </select>
          <ChevronDown className="w-3 h-3 text-slate-400 absolute right-2.5 pointer-events-none" />
        </div>

        {/* Loading indicator */}
        {isPending && (
          <span className="text-[11px] text-emerald-400 flex items-center gap-1.5 animate-pulse pl-1">
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
            className="inline-flex items-center gap-1.5 text-[11px] font-medium text-slate-400 hover:text-white px-2.5 py-1 rounded-lg hover:bg-white/[0.06] transition-colors"
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
