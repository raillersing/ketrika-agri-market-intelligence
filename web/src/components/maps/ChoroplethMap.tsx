"use client";

import React from "react";
import { formatPrice } from "../../lib/formatters";
import { ValueKindBadge } from "../ui/ValueKindBadge";
import { SourceBadge } from "../ui/SourceBadge";

export interface RegionPriceData {
  pcode: string;
  name: string;
  price: number | null;
  unit: string;
  currency: string;
  valueKind: string;
  sources: string[];
}

interface ChoroplethMapProps {
  regionPrices?: RegionPriceData[];
  onRegionSelect?: (pcode: string) => void;
  selectedPcode?: string;
  className?: string;
}

export function ChoroplethMap({
  regionPrices = [],
  onRegionSelect,
  selectedPcode,
  className = "",
}: ChoroplethMapProps) {
  return (
    <div role="region" aria-label="Points régionaux disponibles" className={`rounded-2xl border border-border bg-card p-4 ${className}`}>
      <p className="mb-3 text-sm text-muted-foreground">
        Points à leur niveau enregistré ; cette grille ne représente pas des frontières géographiques.
      </p>
      {!regionPrices.length ? (
        <p role="status" className="text-sm text-muted-foreground">Aucun point régional disponible pour cette sélection.</p>
      ) : (
        <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {regionPrices.map((item, index) => (
            <button
              key={`${item.pcode}-${index}`}
              type="button"
              aria-pressed={selectedPcode === item.pcode}
              onClick={() => onRegionSelect?.(item.pcode)}
              className="min-w-0 space-y-2 break-words rounded-xl border border-border p-3 text-left hover:border-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring aria-pressed:border-primary"
            >
              <span className="block text-sm font-semibold text-foreground">{item.name}</span>
              <span className="block text-xs text-muted-foreground">{item.pcode}</span>
              <span className="block font-mono text-sm text-foreground">
                {formatPrice(item.price, item.unit || "Unité non renseignée", item.currency === "MGA" ? "Ar" : item.currency || "Devise non renseignée")}
              </span>
              <ValueKindBadge kind={item.valueKind} />
              <span className="flex flex-wrap gap-1 text-xs text-muted-foreground">
                {item.sources.length ? item.sources.map((source) => <SourceBadge key={source} sourceId={source} />) : "Source non renseignée"}
              </span>
            </button>
          ))}
        </div>
      )}
      <p className="mt-3 text-xs text-muted-foreground">Aucun diagnostic territorial déduit de cette vue.</p>
    </div>
  );
}
