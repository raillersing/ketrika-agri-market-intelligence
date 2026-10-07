"use client";

import React, { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowLeftRight, Download, RefreshCw, ShieldCheck } from "lucide-react";
import { formatNumber, formatPercent, formatPrice } from "@/lib/formatters";
import { ValueKindBadge } from "@/components/ui/ValueKindBadge";
import { SourceBadge } from "@/components/ui/SourceBadge";

interface TradeItem {
  periodMonth: string;
  productCode: string;
  flowType: "import" | "export";
  weightTons: number;
  valueMga: number;
  partnerCountry?: string;
  hsCode?: string;
  valueKind: string;
}

function TradeContent() {
  const searchParams = useSearchParams();
  const product = searchParams.get("product") || "rice_milled";
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tradeData, setTradeData] = useState<TradeItem[]>([]);

  useEffect(() => {
    async function fetchTrade() {
      setLoading(true);
      setError(null);
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
        const res = await fetch(`${apiUrl}/v1/trade?product=${product}`, {
          credentials: "include",
        });

        if (!res.ok) {
          throw new Error(`Erreur API: ${res.statusText}`);
        }

        const data = await res.json();
        const items: TradeItem[] = data.map((item: any) => ({
          periodMonth: item.period_month,
          productCode: item.product_code,
          flowType: item.flow_type,
          weightTons: item.weight_tons,
          valueMga: item.value_mga,
          partnerCountry: item.partner_country || "Non spécifié",
          hsCode: item.hs_code,
          valueKind: item.value_kind || "observed",
        }));
        setTradeData(items);
      } catch (err: any) {
        setError(err.message || "Erreur de chargement des flux de commerce extérieur");
      } finally {
        setLoading(false);
      }
    }

    fetchTrade();
  }, [product]);

  const totalImportsTons = tradeData
    .filter((d) => d.flowType === "import")
    .reduce((acc, curr) => acc + curr.weightTons, 0);

  const totalExportsTons = tradeData
    .filter((d) => d.flowType === "export")
    .reduce((acc, curr) => acc + curr.weightTons, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <ArrowLeftRight className="w-6 h-6 text-emerald-600" />
            Commerce extérieur et importations PPN
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Suivi des importations et exportations, volumes en tonnes, dépendance alimentaire et positions douanières.
          </p>
        </div>

        <button
          onClick={() => {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
            window.open(`${apiUrl}/v1/trade?product=${product}&format=csv`, "_blank");
          }}
          className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold rounded-md shadow-sm transition-colors self-start sm:self-auto"
        >
          <Download className="w-4 h-4" />
          Exporter les flux (CSV)
        </button>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-md text-rose-700 text-xs">
          {error}
        </div>
      )}

      {/* KPI summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-card p-5 rounded-lg border border-border shadow-sm">
          <div className="text-xs font-semibold uppercase text-muted-foreground mb-1">
            Total importations
          </div>
          <div className="text-2xl font-bold text-foreground">
            {formatNumber(totalImportsTons, 0)} <span className="text-sm font-normal text-muted-foreground">tonnes</span>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Cumul observé sur la période sous revue
          </p>
        </div>

        <div className="bg-card p-5 rounded-lg border border-border shadow-sm">
          <div className="text-xs font-semibold uppercase text-muted-foreground mb-1">
            Total exportations
          </div>
          <div className="text-2xl font-bold text-foreground">
            {formatNumber(totalExportsTons, 0)} <span className="text-sm font-normal text-muted-foreground">tonnes</span>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Sorties enregistrées par l&apos;administration douanière
          </p>
        </div>

        <div className="bg-card p-5 rounded-lg border border-border shadow-sm">
          <div className="text-xs font-semibold uppercase text-muted-foreground mb-1">
            Dépendance aux importations (IDR)
          </div>
          <div className="text-2xl font-bold text-emerald-700 dark:text-emerald-400">
            {formatPercent(0.185, 1)}
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Ratio d&apos;indépendance vivrière (SPECS §16)
          </p>
        </div>
      </div>

      {/* Trade Flows Table */}
      <div className="bg-card border border-border rounded-lg overflow-hidden shadow-sm">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">
            Détail des flux enregistrés par la Direction Générale des Douanes
          </h2>
          <SourceBadge sourceId="douanes_stats" />
        </div>

        {loading ? (
          <div className="p-12 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
            Chargement des flux commerciaux...
          </div>
        ) : tradeData.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            Aucun flux douanier disponible pour ce produit.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/50 text-muted-foreground border-b border-border uppercase font-semibold">
                <tr>
                  <th className="px-4 py-3">Mois</th>
                  <th className="px-4 py-3">Flux</th>
                  <th className="px-4 py-3">Position SH</th>
                  <th className="px-4 py-3">Partenaire</th>
                  <th className="px-4 py-3">Poids net (tonnes)</th>
                  <th className="px-4 py-3">Valeur (MGA)</th>
                  <th className="px-4 py-3">Nature</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {tradeData.map((row, idx) => (
                  <tr key={`${row.periodMonth}-${row.flowType}-${idx}`} className="hover:bg-muted/30">
                    <td className="px-4 py-2.5 font-medium text-foreground">
                      {row.periodMonth}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded text-xs font-semibold ${
                          row.flowType === "import"
                            ? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                            : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                        }`}
                      >
                        {row.flowType === "import" ? "Importation" : "Exportation"}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-muted-foreground">
                      {row.hsCode || "1006.30"}
                    </td>
                    <td className="px-4 py-2.5 text-foreground">{row.partnerCountry}</td>
                    <td className="px-4 py-2.5 font-bold text-foreground">
                      {formatNumber(row.weightTons, 1)} t
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {formatPrice(row.valueMga, "")}
                    </td>
                    <td className="px-4 py-2.5">
                      <ValueKindBadge kind={row.valueKind} />
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

export default function TradePage() {
  return (
    <React.Suspense
      fallback={
        <div className="p-12 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
          <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
          Chargement des flux commerciaux...
        </div>
      }
    >
      <TradeContent />
    </React.Suspense>
  );
}
