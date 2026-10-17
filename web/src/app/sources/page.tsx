"use client";

import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  CheckCircle,
  Database,
  ExternalLink,
  Layers,
  RefreshCw,
  Server,
  ShieldCheck,
} from "lucide-react";

interface SourceItem {
  sourceId: string;
  name: string;
  institution: string;
  frequency: string;
  freshnessSlaDays: number;
  freshnessDays?: number;
  isStale?: boolean;
  status: string;
}

export default function SourcesPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<SourceItem[]>([]);

  useEffect(() => {
    async function fetchSources() {
      setLoading(true);
      setError(null);
      try {
        const apiUrl = "/api";
        const res = await fetch(`${apiUrl}/v1/sources`, {
          credentials: "include",
        });

        if (!res.ok) {
          throw new Error(`Erreur API: ${res.statusText}`);
        }

        const data = await res.json();
        const items: SourceItem[] = data.map((s: any) => ({
          sourceId: s.source_id,
          name: s.name,
          institution: s.institution || "Institution officielle",
          frequency: s.frequency || "Mensuel",
          freshnessSlaDays: s.freshness_sla_days || 30,
          freshnessDays: s.freshness_days,
          isStale: s.is_stale,
          status: s.latest_run_status || s.status || "active",
        }));
        setSources(items);
      } catch (err: any) {
        setError(err.message || "Erreur de chargement des sources");
      } finally {
        setLoading(false);
      }
    }

    fetchSources();
  }, []);

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight text-white flex items-center gap-2.5">
              <Activity className="w-6 h-6 text-emerald-400" />
              Cockpit DataOps & Surveillance des sources
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
              10 sources officielles
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Monitoring en temps réel de la fraîcheur, des SLAs d&apos;ingestion et de l&apos;immuabilité Bronze (MinIO).
          </p>
        </div>

        <a
          href="http://localhost:3010"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 text-purple-300 text-xs font-semibold rounded-xl shadow-lg shadow-purple-950/40 transition-all self-start sm:self-auto"
        >
          <Server className="w-4 h-4" />
          <span>Ouvrir Dagster Cockpit</span>
          <ExternalLink className="w-3.5 h-3.5 ml-0.5" />
        </a>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs">
          {error}
        </div>
      )}

      {/* Sources Table */}
      <div className="glass-card rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-white/[0.07] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-emerald-400" />
            <h2 className="text-sm font-bold text-white">
              Registre des connecteurs de collecte
            </h2>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            {sources.length} connecteurs configurés
          </span>
        </div>

        {loading ? (
          <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
            <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
            Contrôle des connecteurs et de la fraîcheur...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-950/60 text-slate-400 border-b border-white/[0.06] uppercase font-mono text-[10px] tracking-wider">
                <tr>
                  <th className="px-5 py-3">Identifiant</th>
                  <th className="px-5 py-3">Intitulé de la source</th>
                  <th className="px-5 py-3">Organisme émetteur</th>
                  <th className="px-5 py-3">Fréquence</th>
                  <th className="px-5 py-3 text-right">SLA Fraîcheur</th>
                  <th className="px-5 py-3">État du collecteur</th>
                  <th className="px-5 py-3">Conformité SLA</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {sources.map((s) => (
                  <tr key={s.sourceId} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-5 py-3.5 font-mono font-bold text-white">
                      {s.sourceId}
                    </td>
                    <td className="px-5 py-3.5 font-medium text-slate-200">{s.name}</td>
                    <td className="px-5 py-3.5 text-slate-400">{s.institution}</td>
                    <td className="px-5 py-3.5 capitalize text-slate-300 font-mono text-[11px]">
                      {s.frequency}
                    </td>
                    <td className="px-5 py-3.5 font-mono text-right text-slate-300">
                      {s.freshnessSlaDays}j
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold uppercase border ${
                          s.status.toLowerCase() === "failed" || s.status.toLowerCase() === "error"
                            ? "bg-rose-500/15 text-rose-300 border-rose-500/25"
                            : s.status.toLowerCase() === "running"
                            ? "bg-amber-500/15 text-amber-300 border-amber-500/25"
                            : s.status.toLowerCase() === "disabled" || s.status.toLowerCase() === "planned"
                            ? "bg-slate-500/15 text-slate-400 border-slate-500/25"
                            : "bg-emerald-500/15 text-emerald-300 border-emerald-500/25"
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            s.status.toLowerCase() === "failed" || s.status.toLowerCase() === "error"
                              ? "bg-rose-400"
                              : s.status.toLowerCase() === "running"
                              ? "bg-amber-400 animate-spin"
                              : s.status.toLowerCase() === "disabled" || s.status.toLowerCase() === "planned"
                              ? "bg-slate-400"
                              : "bg-emerald-400"
                          }`}
                        />
                        {s.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      {s.status.toLowerCase() === "disabled" ? (
                        <span className="inline-flex items-center gap-1.5 text-slate-400 font-mono text-[11px]">
                          <AlertCircle className="w-3.5 h-3.5 text-slate-500" />
                          Désactivée (PolicyStop)
                        </span>
                      ) : s.isStale ? (
                        <span className="inline-flex items-center gap-1.5 text-rose-400 font-mono text-[11px]">
                          <AlertCircle className="w-3.5 h-3.5" />
                          Retard (DATA_STALE)
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-emerald-400 font-mono text-[11px]">
                          <CheckCircle className="w-3.5 h-3.5" />
                          Conforme SLA
                        </span>
                      )}
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
