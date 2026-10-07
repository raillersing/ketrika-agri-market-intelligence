"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Download, RefreshCw, Table, TrendingUp } from "lucide-react";
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

function PricesContent() {
  const searchParams = useSearchParams();
  const product = searchParams.get("product") || "rice_milled";
  const region = searchParams.get("region") || "";
  const actor = searchParams.get("actor") || "";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartData, setChartData] = useState<PriceDataPoint[]>([]);
  const [tableData, setTableData] = useState<PriceRow[]>([]);

  useEffect(() => {
    async function fetchPrices() {
      setLoading(true);
      setError(null);
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
        const params = new URLSearchParams();
        if (product) params.set("product", product);
        if (region) params.set("location", region);
        if (actor) params.set("actor_level", actor);

        const res = await fetch(`${apiUrl}/v1/prices?${params.toString()}`, {
          credentials: "include",
        });

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
      } catch (err: any) {
        setError(err.message || "Impossible de charger les données de prix");
      } finally {
        setLoading(false);
      }
    }

    fetchPrices();
  }, [product, region, actor]);

  const handleExportCsv = () => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
    const params = new URLSearchParams();
    if (product) params.set("product", product);
    if (region) params.set("location", region);
    if (actor) params.set("actor_level", actor);
    params.set("format", "csv");
    window.open(`${apiUrl}/v1/prices?${params.toString()}`, "_blank");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-emerald-600" />
            Explorateur des prix vivriers
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Historique mensuel des prix nominaux, fourchettes de dispersion et traçabilité par source.
          </p>
        </div>

        <button
          onClick={handleExportCsv}
          className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold rounded-md shadow-sm transition-colors self-start sm:self-auto"
        >
          <Download className="w-4 h-4" />
          Exporter les données (CSV)
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-center justify-between">
          <span>{error}</span>
        </div>
      )}

      {/* Chart View */}
      <PriceChart
        title={`Série temporelle des prix — ${product}`}
        data={chartData}
        productName={product}
      />

      {/* Data Table */}
      <div className="bg-card border border-border rounded-lg overflow-hidden shadow-sm">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Table className="w-4 h-4 text-emerald-600" />
            <h2 className="text-sm font-semibold text-foreground">
              Tableau des observations mensuelles
            </h2>
          </div>
          <span className="text-xs text-muted-foreground">
            {tableData.length} enregistrements
          </span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
            Chargement des observations...
          </div>
        ) : tableData.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            Aucun enregistrement ne correspond aux filtres sélectionnés.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/50 text-muted-foreground border-b border-border uppercase font-semibold">
                <tr>
                  <th className="px-4 py-3">Mois</th>
                  <th className="px-4 py-3">Région / Marché</th>
                  <th className="px-4 py-3">Niveau d&apos;acteur</th>
                  <th className="px-4 py-3">Prix médian</th>
                  <th className="px-4 py-3">Fourchette (Min - Max)</th>
                  <th className="px-4 py-3">Nature</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Traçabilité</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {tableData.map((row, idx) => (
                  <tr key={`${row.month}-${row.locationName}-${idx}`} className="hover:bg-muted/30">
                    <td className="px-4 py-2.5 font-medium text-foreground">
                      {formatMonthYear(row.month)}
                    </td>
                    <td className="px-4 py-2.5 text-foreground">{row.locationName}</td>
                    <td className="px-4 py-2.5 capitalize text-muted-foreground">
                      {row.actorLevel}
                    </td>
                    <td className="px-4 py-2.5 font-bold text-foreground">
                      {formatPrice(row.medianPrice, "kg")}
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">
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
        <div className="p-12 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
          <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
          Chargement des prix vivriers...
        </div>
      }
    >
      <PricesContent />
    </React.Suspense>
  );
}
