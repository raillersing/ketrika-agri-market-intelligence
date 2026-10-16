"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Activity, CheckCircle2, Download, Layers, RefreshCw, Search, Table, TrendingUp } from "lucide-react";
import { formatMonthYear, formatPrice } from "@/lib/formatters";
import { ValueKindBadge } from "@/components/ui/ValueKindBadge";
import { SourceBadge } from "@/components/ui/SourceBadge";
import { ProvenanceLink } from "@/components/ui/ProvenanceLink";
import { PriceChart, type PriceDataPoint } from "@/components/charts/PriceChart";

interface PriceRow {
  month: string;
  productCode: string;
  locationName: string;
  actorLevel: string;
  medianPrice: number;
  minPrice?: number | null;
  maxPrice?: number | null;
  valueKind: string;
  sourceId?: string;
  observationId?: string;
}

interface SeriesCoverageGaps {
  product_code: string;
  location_pcode: string;
  location_name?: string | null;
  actor_level: string;
  expected_months: number;
  observed_months: number;
  missing_months: number;
  coverage_ratio: number;
  missing_months_list: string[];
  source_families: string[];
  is_pilot_candidate: boolean;
}

function PricesContent() {
  const searchParams = useSearchParams();
  const product = searchParams.get("product") || "rice_milled";
  const region = searchParams.get("region") || "";
  const actor = searchParams.get("actor") || "";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartData, setChartData] = useState<PriceDataPoint[]>([]);
  const [tableData, setTableData] = useState<PriceRow[]>([]);
  const [coverageGaps, setCoverageGaps] = useState<SeriesCoverageGaps | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    async function fetchPrices() {
      setLoading(true);
      setError(null);
      try {
        const apiUrl = "/api";
        const params = new URLSearchParams();
        if (product) params.set("product", product);
        if (region) params.set("location", region);
        if (actor) params.set("actor_level", actor);

        const [res, gapsRes] = await Promise.all([
          fetch(`${apiUrl}/v1/prices?${params.toString()}`, { credentials: "include" }),
          fetch(
            `${apiUrl}/v1/market/coverage/gaps?product=${encodeURIComponent(
              product
            )}&location=${encodeURIComponent(region || "MDG11")}&actor_level=${encodeURIComponent(
              actor || "retail"
            )}`,
            { credentials: "include" }
          ).catch(() => null),
        ]);

        if (!res.ok) {
          throw new Error(`Erreur API: ${res.statusText}`);
        }

        const data = await res.json();
        const rows: PriceRow[] = data.map((item: any) => ({
          month: item.month,
          productCode: item.product_code,
          locationName: item.location_name || "National",
          actorLevel: item.actor_level || "retail",
          medianPrice: item.median_price,
          minPrice: item.min_price,
          maxPrice: item.max_price,
          valueKind: item.value_kind || "observed",
          sourceId: item.sources?.[0] || item.source_id,
        }));

        setTableData(rows);

        const chartPts: PriceDataPoint[] = rows.map((r) => ({
          month: r.month,
          medianPrice: r.medianPrice,
          minPrice: r.minPrice,
          maxPrice: r.maxPrice,
          valueKind: r.valueKind,
          sourceId: r.sourceId,
        }));
        setChartData(chartPts);

        if (gapsRes && gapsRes.ok) {
          const gapsData: SeriesCoverageGaps = await gapsRes.json();
          setCoverageGaps(gapsData);
        } else {
          setCoverageGaps(null);
        }
      } catch (err: any) {
        setError(err.message || "Impossible de charger les données de prix");
      } finally {
        setLoading(false);
      }
    }

    fetchPrices();
  }, [product, region, actor]);

  const handleExportCsv = () => {
    const apiUrl = "/api";
    const params = new URLSearchParams();
    if (product) params.set("product", product);
    if (region) params.set("location", region);
    if (actor) params.set("actor_level", actor);
    params.set("format", "csv");
    window.open(`${apiUrl}/v1/prices?${params.toString()}`, "_blank");
  };

  const filteredTableData = tableData.filter((row) =>
    row.locationName.toLowerCase().includes(searchTerm.toLowerCase()) ||
    row.month.includes(searchTerm) ||
    row.actorLevel.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight text-white flex items-center gap-2.5">
              <TrendingUp className="w-6 h-6 text-emerald-400" />
              Explorateur des prix vivriers
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
              {tableData.length} observations
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Historique mensuel des prix nominaux, dispersion géographique et traçabilité certifiée.
          </p>
        </div>

        <button
          onClick={handleExportCsv}
          className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-emerald-950/40 transition-all hover:scale-102 self-start sm:self-auto"
        >
          <Download className="w-4 h-4" />
          Exporter CSV
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs flex items-center justify-between">
          <span>{error}</span>
        </div>
      )}

      {/* Series Coverage and Quality Metrics (R2.4, R2.10) */}
      {coverageGaps && (
        <div className="glass-card rounded-2xl p-4 border border-white/[0.08] bg-slate-900/40">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-400" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-white font-mono">
                Couverture de Série & Audit des Lacunes Calendaires (R2.4)
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono border ${
                  coverageGaps.is_pilot_candidate
                    ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                    : "bg-slate-800 text-slate-400 border-white/[0.05]"
                }`}
              >
                {coverageGaps.is_pilot_candidate ? "✓ Candidat Pilote ML" : "Série Hors Pilote"}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
            <div className="bg-slate-950/60 p-2.5 rounded-xl border border-white/[0.04]">
              <span className="text-[10px] font-mono text-slate-400 block">Complétude</span>
              <span className="text-base font-bold font-mono text-emerald-400 mt-0.5 block">
                {(coverageGaps.coverage_ratio * 100).toFixed(1)} %
              </span>
            </div>

            <div className="bg-slate-950/60 p-2.5 rounded-xl border border-white/[0.04]">
              <span className="text-[10px] font-mono text-slate-400 block">Continuité</span>
              <span className="text-base font-bold font-mono text-white mt-0.5 block">
                {coverageGaps.observed_months} / {coverageGaps.expected_months} mois
              </span>
            </div>

            <div className="bg-slate-950/60 p-2.5 rounded-xl border border-white/[0.04]">
              <span className="text-[10px] font-mono text-slate-400 block">Lacunes Calendaires</span>
              <span
                className={`text-base font-bold font-mono mt-0.5 block ${
                  coverageGaps.missing_months === 0 ? "text-emerald-400" : "text-amber-400"
                }`}
              >
                {coverageGaps.missing_months} mois
              </span>
            </div>

            <div className="bg-slate-950/60 p-2.5 rounded-xl border border-white/[0.04]">
              <span className="text-[10px] font-mono text-slate-400 block">Familles Sources</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {coverageGaps.source_families.length > 0 ? (
                  coverageGaps.source_families.map((fam) => (
                    <span
                      key={fam}
                      className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-slate-800 text-slate-300 border border-white/[0.05]"
                    >
                      {fam}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-slate-500">—</span>
                )}
              </div>
            </div>
          </div>

          {coverageGaps.missing_months_list.length > 0 && (
            <div className="mt-3 pt-2.5 border-t border-white/[0.04] text-[11px] text-amber-300/90 flex items-center gap-1.5 font-mono">
              <span className="font-semibold">Mois manquants sans observation :</span>
              <span>{coverageGaps.missing_months_list.join(", ")}</span>
            </div>
          )}
        </div>
      )}

      {/* Chart View */}
      <PriceChart
        title={`Série temporelle des prix — ${product}`}
        data={chartData}
        productName={product}
      />

      {/* Data Table */}
      <div className="glass-card rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-white/[0.07] flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Table className="w-4 h-4 text-emerald-400" />
            <h2 className="text-sm font-bold text-white">
              Tableau des observations mensuelles
            </h2>
          </div>

          <div className="flex items-center gap-3">
            {/* Search inside table */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Filtrer lieu, date..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="text-xs bg-slate-900 border border-white/[0.08] rounded-lg pl-8 pr-3 py-1.5 text-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500 w-44 sm:w-56"
              />
            </div>
            <span className="text-xs font-mono text-slate-400">
              {filteredTableData.length} lignes
            </span>
          </div>
        </div>

        {loading ? (
          <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
            <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
            Chargement des observations...
          </div>
        ) : filteredTableData.length === 0 ? (
          <div className="p-16 text-center text-xs text-slate-400 font-mono">
            Aucun enregistrement ne correspond aux critères sélectionnés.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-950/60 text-slate-400 border-b border-white/[0.06] uppercase font-mono text-[10px] tracking-wider">
                <tr>
                  <th className="px-4 py-3">Mois</th>
                  <th className="px-4 py-3">Région / Marché</th>
                  <th className="px-4 py-3">Niveau d&apos;acteur</th>
                  <th className="px-4 py-3 text-right">Prix médian</th>
                  <th className="px-4 py-3 text-right">Fourchette</th>
                  <th className="px-4 py-3">Nature</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Traçabilité</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {filteredTableData.map((row, idx) => (
                  <tr key={`${row.month}-${row.locationName}-${idx}`} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-2.5 font-medium text-white">
                      {formatMonthYear(row.month)}
                    </td>
                    <td className="px-4 py-2.5 text-slate-200">{row.locationName}</td>
                    <td className="px-4 py-2.5 capitalize text-slate-400">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-slate-800 text-slate-300 border border-white/[0.05]">
                        {row.actorLevel}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono font-bold text-emerald-400">
                      {formatPrice(row.medianPrice, "kg")}
                    </td>
                    <td className="px-4 py-2.5 text-right text-slate-400 font-mono text-[11px]">
                      {row.minPrice && row.maxPrice
                        ? `${formatPrice(row.minPrice, "kg")} – ${formatPrice(row.maxPrice, "kg")}`
                        : "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <ValueKindBadge kind={row.valueKind} />
                    </td>
                    <td className="px-4 py-2.5">
                      {row.sourceId && <SourceBadge sourceId={row.sourceId} />}
                    </td>
                    <td className="px-4 py-2.5">
                      <ProvenanceLink observationId={row.observationId} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default function PricesPage() {
  return (
    <React.Suspense
      fallback={
        <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
          <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
          Chargement des prix vivriers...
        </div>
      }
    >
      <PricesContent />
    </React.Suspense>
  );
}
