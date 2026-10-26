"use client";

import React, { useRef, useState } from "react";
import { formatPrice } from "@/lib/formatters";
import { Compass, MapPin, TrendingUp } from "lucide-react";

export interface RegionPriceData {
  pcode: string;
  name: string;
  price?: number | null;
  unit?: string;
  valueKind?: string;
  sourceId?: string;
}

interface ChoroplethMapProps {
  geoJsonData?: any;
  regionPrices?: Record<string, RegionPriceData>;
  onRegionSelect?: (pcode: string) => void;
  selectedPcode?: string;
  className?: string;
}

export function ChoroplethMap({
  regionPrices = {},
  onRegionSelect,
  selectedPcode,
  className = "",
}: ChoroplethMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const [hoveredRegion, setHoveredRegion] = useState<RegionPriceData | null>(null);

  const getColor = (price: number | null | undefined, min: number, max: number) => {
    if (price === null || price === undefined) return "#334155";
    if (max <= min) return "#10b981";
    const ratio = Math.min(1, Math.max(0, (price - min) / (max - min)));
    if (ratio < 0.33) return "#10b981"; // emerald-500
    if (ratio < 0.66) return "#f59e0b"; // amber-500
    return "#f43f5e"; // rose-500
  };

  const validPrices = Object.values(regionPrices)
    .map((r) => r.price)
    .filter((p): p is number => p !== null && p !== undefined);
  const minPrice = validPrices.length ? Math.min(...validPrices) : 0;
  const maxPrice = validPrices.length ? Math.max(...validPrices) : 0;
  const spreadPercent = minPrice > 0 ? Math.round(((maxPrice - minPrice) / minPrice) * 100) : 0;

  return (
    <div className={`glass-card rounded-2xl overflow-hidden flex flex-col justify-between ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-border flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
              <Compass className="w-4 h-4 text-primary-readable" />
              Répartition des points disponibles
            </h3>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-primary-readable border border-emerald-500/20">
              {validPrices.length > 1 ? `Écart: ${spreadPercent}%` : "Écart non évalué"}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Points de la sélection ; la couverture géographique reste à qualifier
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-2 text-[11px] font-mono text-muted-foreground">
          <span className="text-primary-readable">{validPrices.length ? formatPrice(minPrice, "kg") : "—"}</span>
          <div className="flex h-2 w-20 rounded-full overflow-hidden bg-muted border border-border">
            <div className="flex-1 bg-emerald-500" />
            <div className="flex-1 bg-amber-500" />
            <div className="flex-1 bg-rose-500" />
          </div>
          <span className="text-rose-700 dark:text-rose-400">{validPrices.length ? formatPrice(maxPrice, "kg") : "—"}</span>
        </div>
      </div>

      {/* Grid Display */}
      <div
        ref={mapContainer}
        className="h-88 w-full relative bg-background/40 p-4 flex flex-col justify-between"
      >
        <div className="w-full max-h-76 overflow-y-auto pr-1 flex flex-wrap gap-2 content-start">
          {Object.entries(regionPrices).map(([pcode, item]) => {
            const color = getColor(item.price, minPrice, maxPrice);
            const isSelected = selectedPcode === pcode;

            return (
              <button
                key={pcode}
                onClick={() => onRegionSelect?.(pcode)}
                onMouseEnter={() => setHoveredRegion(item)}
                onMouseLeave={() => setHoveredRegion(null)}
                style={{ borderColor: isSelected ? "#10b981" : undefined }}
                className={`flex-1 min-w-[135px] p-2.5 rounded-xl border text-left transition-all ${
                  isSelected
                    ? "bg-emerald-500/20 border-emerald-500 shadow-md shadow-emerald-950/40"
                    : "bg-card/60 border-border hover:border-emerald-500/40 hover:bg-card/90"
                }`}
              >
                <div className="flex items-center justify-between gap-1 mb-1">
                  <span className="text-xs font-semibold truncate text-foreground">
                    {item.name}
                  </span>
                  <span
                    className="w-2 h-2 rounded-full shrink-0 shadow-sm"
                    style={{ backgroundColor: color }}
                  />
                </div>
                <div className="text-xs font-mono font-bold text-foreground flex items-center justify-between">
                  <span>{formatPrice(item.price, item.unit || "kg")}</span>
                  <span className="text-[9px] text-muted-foreground font-normal">{pcode}</span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Floating tooltip */}
        {hoveredRegion && (
          <div className="absolute bottom-4 left-4 bg-card/95 text-foreground p-3 rounded-xl border border-emerald-500/30 shadow-2xl backdrop-blur-xl text-xs pointer-events-none z-20 animate-in fade-in duration-150">
            <div className="font-bold flex items-center gap-1.5 text-primary-readable">
              <MapPin className="w-3.5 h-3.5" />
              {hoveredRegion.name} ({hoveredRegion.pcode})
            </div>
            <div className="text-muted-foreground mt-1 font-mono">
              Prix médian : <strong className="text-foreground">{formatPrice(hoveredRegion.price, hoveredRegion.unit || "kg")}</strong>
            </div>
            {hoveredRegion.sourceId && (
              <div className="text-[10px] text-muted-foreground mt-1 font-mono">
                Source : {hoveredRegion.sourceId}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Disparity summary footer */}
      <div className="px-4 py-2 border-t border-border bg-background/60 flex items-center justify-between text-[11px] text-muted-foreground font-mono">
        <span>Aucun diagnostic territorial déduit de cette vue</span>
        <span>{validPrices.length} points disponibles</span>
      </div>
    </div>
  );
}
