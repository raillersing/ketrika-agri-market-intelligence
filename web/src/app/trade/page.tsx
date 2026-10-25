"use client";

import React, { useEffect, useState } from "react";
import { DEFAULT_PRODUCT } from "@/lib/market-overview";
import { useSearchParams } from "next/navigation";
import { ArrowLeftRight, Download, Globe, RefreshCw, Ship, TrendingUp } from "lucide-react";
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
  const product = searchParams.get("product") || DEFAULT_PRODUCT;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tradeData, setTradeData] = useState<TradeItem[]>([]);

  useEffect(() => {
    async function fetchTrade() {
      setLoading(true);
      setError(null);
      try {
        const apiUrl = "/api";
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
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight text-white flex items-center gap-2.5">
              <ArrowLeftRight className="w-6 h-6 text-sky-400" />
              Commerce extérieur & Importations PPN
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-sky-500/10 text-sky-300 border border-sky-500/20">
              Douanes Malagasy (ASYCUDA)
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Suivi des flux maritimes, tonnages importés au port de Toamasina et indice de dépendance alimentaire.
          </p>
        </div>

        <button
          onClick={() => {
            const apiUrl = "/api";
            window.open(`${apiUrl}/v1/trade?product=${product}&format=csv`, "_blank");
          }}
          className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-emerald-950/40 transition-all hover:scale-102 self-start sm:self-auto"
        >
          <Download className="w-4 h-4" />
          Exporter les flux (CSV)
        </button>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs">
          {error}
        </div>
      )}

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-card p-5 rounded-2xl">
          <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1 flex items-center gap-1.5">
            <Ship className="w-3.5 h-3.5 text-sky-400" />
            Total Importations
          </div>
          <div className="text-2xl font-extrabold font-mono text-white">
            {formatNumber(totalImportsTons, 0)} <span className="text-xs font-normal text-slate-400">tonnes</span>
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Cumul observé sur la période sous revue
          </p>
        </div>

        <div className="glass-card p-5 rounded-2xl">
          <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1 flex items-center gap-1.5">
            <Globe className="w-3.5 h-3.5 text-emerald-400" />
            Total Exportations
          </div>
          <div className="text-2xl font-extrabold font-mono text-white">
            {formatNumber(totalExportsTons, 0)} <span className="text-xs font-normal text-slate-400">tonnes</span>
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Envois enregistrés par l&apos;administration douanière
          </p>
        </div>

        <div className="glass-card p-5 rounded-2xl">
          <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1 flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5 text-amber-400" />
            Dépendance aux importations (IDR)
          </div>
          <div className="text-2xl font-extrabold font-mono text-emerald-400">
            {formatPercent(0.185, 1)}
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Ratio d&apos;indépendance vivrière (SPECS §16)
          </p>
        </div>
      </div>

      {/* Trade Flows Table */}
      <div className="glass-card rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-white/[0.07] flex items-center justify-between">
          <h2 className="text-sm font-bold text-white">
            Détail des flux enregistrés par la Direction Générale des Douanes
          </h2>
          <SourceBadge sourceId="douanes_stats" />
        </div>

        {loading ? (
          <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
            <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
            Chargement des flux commerciaux...
          </div>
        ) : tradeData.length === 0 ? (
          <div className="p-16 text-center text-xs text-slate-400 font-mono">
            Aucun flux douanier disponible pour ce produit.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-950/60 text-slate-400 border-b border-white/[0.06] uppercase font-mono text-[10px] tracking-wider">
                <tr>
                  <th className="px-4 py-3">Mois</th>
                  <th className="px-4 py-3">Flux</th>
                  <th className="px-4 py-3">Position SH</th>
                  <th className="px-4 py-3">Partenaire</th>
                  <th className="px-4 py-3 text-right">Poids Net (t)</th>
                  <th className="px-4 py-3 text-right">Valeur (MGA)</th>
                  <th className="px-4 py-3">Nature</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {tradeData.map((row, idx) => (
                  <tr key={`${row.periodMonth}-${row.flowType}-${idx}`} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-2.5 font-medium text-white font-mono">
                      {row.periodMonth}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold ${
                          row.flowType === "import"
                            ? "bg-sky-500/15 text-sky-300 border border-sky-500/20"
                            : "bg-emerald-500/15 text-emerald-300 border border-emerald-500/20"
                        }`}
                      >
                        {row.flowType === "import" ? "Importation" : "Exportation"}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-400">
                      {row.hsCode || "1006.30"}
                    </td>
                    <td className="px-4 py-2.5 text-slate-200">{row.partnerCountry}</td>
                    <td className="px-4 py-2.5 text-right font-mono font-bold text-white">
                      {formatNumber(row.weightTons, 1)} t
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-slate-400">
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
        <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
          <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
          Chargement des flux commerciaux...
        </div>
      }
    >
      <TradeContent />
    </React.Suspense>
  );
}
