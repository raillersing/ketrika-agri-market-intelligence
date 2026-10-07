"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Map, Layers, RefreshCw } from "lucide-react";
import { ChoroplethMap, type RegionPriceData } from "@/components/maps/ChoroplethMap";

function MapContent() {
  const searchParams = useSearchParams();
  const product = searchParams.get("product") || "rice_milled";
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [regionPrices, setRegionPrices] = useState<Record<string, RegionPriceData>>({});
  const [selectedPcode, setSelectedPcode] = useState<string>("");

  useEffect(() => {
    async function fetchLatestPrices() {
      setLoading(true);
      setError(null);
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
        const res = await fetch(`${apiUrl}/v1/prices/latest?product=${product}&level=1`, {
          credentials: "include",
        });

        if (!res.ok) {
          throw new Error(`Erreur API: ${res.statusText}`);
        }

        const data = await res.json();
        const mapData: Record<string, RegionPriceData> = {};

        data.forEach((item: any) => {
          mapData[item.location_pcode] = {
            pcode: item.location_pcode,
            name: item.location_name,
            price: item.median_price,
            unit: item.unit || "kg",
            valueKind: item.value_kind || "observed",
            sourceId: item.sources?.[0],
          };
        });

        setRegionPrices(mapData);
      } catch (err: any) {
        setError(err.message || "Erreur de chargement des prix cartographiques");
      } finally {
        setLoading(false);
      }
    }

    fetchLatestPrices();
  }, [product]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Map className="w-6 h-6 text-emerald-600" />
            Cartographie des marchés et disparités régionales
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Visualisation géographique des prix des PPN sur les 23 régions de Madagascar.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 bg-card border border-border rounded-md shadow-sm">
          <Layers className="w-3.5 h-3.5 text-emerald-600" />
          <span>Découpage administratif : 23 Régions officielles (OCHA COD-AB)</span>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-md text-rose-700 text-xs">
          {error}
        </div>
      )}

      {loading ? (
        <div className="h-96 flex items-center justify-center bg-card border border-border rounded-lg text-sm text-muted-foreground gap-2">
          <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
          Chargement de la carte et des données géographiques...
        </div>
      ) : (
        <ChoroplethMap
          regionPrices={regionPrices}
          selectedPcode={selectedPcode}
          onRegionSelect={(pcode) => setSelectedPcode(pcode)}
          className="min-h-[500px]"
        />
      )}
    </div>
  );
}

export default function MapPage() {
  return (
    <React.Suspense
      fallback={
        <div className="h-96 flex items-center justify-center bg-card border border-border rounded-lg text-sm text-muted-foreground gap-2">
          <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
          Chargement de la carte...
        </div>
      }
    >
      <MapContent />
    </React.Suspense>
  );
}
