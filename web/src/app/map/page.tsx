"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Compass, Layers, Map, RefreshCw, Route, ShieldCheck } from "lucide-react";
import { ChoroplethMap, type RegionPriceData } from "@/components/maps/ChoroplethMap";
import { formatPrice } from "@/lib/formatters";

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
        const apiUrl = "/api";
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
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight text-white flex items-center gap-2.5">
              <Compass className="w-6 h-6 text-emerald-400" />
              Cartographie des marchés vivriers
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-sky-500/10 text-sky-300 border border-sky-500/20">
              23 Régions COD-AB
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Analyse spatiale des disparités territoriales et des corridors d&apos;acheminement à Madagascar.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono px-3.5 py-1.5 glass-panel rounded-xl text-slate-300">
          <Layers className="w-3.5 h-3.5 text-emerald-400" />
          <span>Niveau administratif : Région (Admin-1)</span>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs">
          {error}
        </div>
      )}

      {/* Main Map Card */}
      {loading ? (
        <div className="h-96 flex items-center justify-center glass-panel rounded-2xl text-xs text-slate-400 font-mono gap-2">
          <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
          Chargement de la géométrie et des cotations régionales...
        </div>
      ) : (
        <ChoroplethMap
          regionPrices={regionPrices}
          selectedPcode={selectedPcode}
          onRegionSelect={(pcode) => setSelectedPcode(pcode)}
          className="min-h-[500px]"
        />
      )}

      {/* Corridor Intelligence Ribbon */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-card p-4 rounded-xl space-y-1.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-emerald-300">
            <Route className="w-4 h-4 text-emerald-400" />
            <span>Corridor RN2 (Toamasina - Tana)</span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Axe logistique principal d&apos;importation (riz blanc, huile, farine). Transmission rapide des cours portuaires vers la capitale.
          </p>
        </div>

        <div className="glass-card p-4 rounded-xl space-y-1.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-300">
            <Route className="w-4 h-4 text-amber-400" />
            <span>Corridor RN7 (Tana - Fianar - Toliara)</span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Gradient de prix croissant vers le Sud. Surcoût de transport estimé à +25% à l&apos;arrivée à Toliara.
          </p>
        </div>

        <div className="glass-card p-4 rounded-xl space-y-1.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-sky-300">
            <Route className="w-4 h-4 text-sky-400" />
            <span>Corridor RN44 (Alaotra-Mangoro)</span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Bassin de production excédentaire (Grenier de Madagascar). Prix au producteur les plus bas du territoire national.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function MapPage() {
  return (
    <React.Suspense
      fallback={
        <div className="h-96 flex items-center justify-center glass-panel rounded-2xl text-xs text-slate-400 font-mono gap-2">
          <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
          Chargement de la carte...
        </div>
      }
    >
      <MapContent />
    </React.Suspense>
  );
}
