"use client";

import React, { useEffect, useRef, useState } from "react";
import { formatPrice } from "@/lib/formatters";

export interface RegionPriceData {
  pcode: string;
  name: string;
  price?: number | null;
  unit?: string;
  valueKind?: string;
  sourceId?: string;
}

interface ChoroplethMapProps {
  geoJsonData?: any; // GeoJSON FeatureCollection
  regionPrices?: Record<string, RegionPriceData>;
  onRegionSelect?: (pcode: string) => void;
  selectedPcode?: string;
  className?: string;
}

export function ChoroplethMap({
  geoJsonData,
  regionPrices = {},
  onRegionSelect,
  selectedPcode,
  className = "",
}: ChoroplethMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const [hoveredRegion, setHoveredRegion] = useState<RegionPriceData | null>(null);

  // Color generator for choropleth scale (green to amber to red)
  const getColor = (price: number | null | undefined, min: number, max: number) => {
    if (price === null || price === undefined) return "#e2e8f0"; // slate-200
    if (max <= min) return "#10b981";
    const ratio = Math.min(1, Math.max(0, (price - min) / (max - min)));
    if (ratio < 0.33) return "#34d399"; // emerald-400
    if (ratio < 0.66) return "#f59e0b"; // amber-500
    return "#ef4444"; // rose-500
  };

  // Find min and max prices
  const validPrices = Object.values(regionPrices)
    .map((r) => r.price)
    .filter((p): p is number => p !== null && p !== undefined);
  const minPrice = validPrices.length ? Math.min(...validPrices) : 2000;
  const maxPrice = validPrices.length ? Math.max(...validPrices) : 4000;

  return (
    <div className={`relative bg-card rounded-lg border border-border overflow-hidden shadow-sm flex flex-col ${className}`}>
      {/* Map header */}
      <div className="p-4 border-b border-border flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Carte régionale des prix
          </h3>
          <p className="text-xs text-muted-foreground">
            Disparités des prix vivriers par région à Madagascar
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{formatPrice(minPrice, "kg")}</span>
          <div className="flex h-2.5 w-24 rounded overflow-hidden">
            <div className="flex-1 bg-emerald-400" />
            <div className="flex-1 bg-amber-500" />
            <div className="flex-1 bg-rose-500" />
          </div>
          <span>{formatPrice(maxPrice, "kg")}</span>
        </div>
      </div>

      {/* Map display area */}
      <div
        ref={mapContainer}
        className="h-96 w-full relative bg-slate-50 dark:bg-slate-900 flex items-center justify-center p-4"
      >
        {/* Render Region Grid / SVG Map representation */}
        <div className="w-full h-full flex flex-wrap gap-2 overflow-y-auto content-start">
          {Object.entries(regionPrices).map(([pcode, item]) => {
            const color = getColor(item.price, minPrice, maxPrice);
            const isSelected = selectedPcode === pcode;

            return (
              <button
                key={pcode}
                onClick={() => onRegionSelect?.(pcode)}
                onMouseEnter={() => setHoveredRegion(item)}
                onMouseLeave={() => setHoveredRegion(null)}
                style={{ borderColor: isSelected ? "#059669" : undefined }}
                className={`flex-1 min-w-[130px] p-2.5 rounded border text-left transition-all ${
                  isSelected
                    ? "bg-emerald-50 dark:bg-emerald-950 border-emerald-600 ring-2 ring-emerald-500"
                    : "bg-background border-border hover:border-slate-400"
                }`}
              >
                <div className="flex items-center justify-between gap-1">
                  <span className="text-xs font-semibold truncate text-foreground">
                    {item.name}
                  </span>
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: color }}
                  />
                </div>
                <div className="text-xs font-medium text-emerald-700 dark:text-emerald-400 mt-1">
                  {formatPrice(item.price, item.unit || "kg")}
                </div>
              </button>
            );
          })}
        </div>

        {/* Floating tooltip */}
        {hoveredRegion && (
          <div className="absolute bottom-4 left-4 bg-popover text-popover-foreground p-3 rounded-md border border-border shadow-md text-xs pointer-events-none z-20">
            <div className="font-semibold">{hoveredRegion.name}</div>
            <div className="text-muted-foreground mt-0.5">
              Prix médian :{" "}
              <strong className="text-foreground">
                {formatPrice(hoveredRegion.price, hoveredRegion.unit || "kg")}
              </strong>
            </div>
            {hoveredRegion.sourceId && (
              <div className="text-[11px] text-muted-foreground mt-0.5">
                Source : {hoveredRegion.sourceId}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
