"use client";

import React, { useEffect, useState } from "react";
import { Activity, AlertCircle, CheckCircle, Database, RefreshCw } from "lucide-react";
import { formatMonthYear } from "@/lib/formatters";

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
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
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
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Activity className="w-6 h-6 text-emerald-600" />
          Cockpit DataOps et SLA des sources de collecte
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Surveillance en temps réel de la santé des collecteurs, SLA de fraîcheur et alertes de retard.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-md text-rose-700 text-xs">
          {error}
        </div>
      )}

      {/* Sources Table */}
      <div className="bg-card border border-border rounded-lg overflow-hidden shadow-sm">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-emerald-600" />
            <h2 className="text-sm font-semibold text-foreground">
              Registre des 10 sources officielles connectées
            </h2>
          </div>
          <span className="text-xs text-muted-foreground">
            {sources.length} sources actives
          </span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
            Vérification de la santé des connecteurs...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/50 text-muted-foreground border-b border-border uppercase font-semibold">
                <tr>
                  <th className="px-4 py-3">Identifiant</th>
                  <th className="px-4 py-3">Intitulé de la source</th>
                  <th className="px-4 py-3">Organisme émetteur</th>
                  <th className="px-4 py-3">Fréquence</th>
                  <th className="px-4 py-3">SLA Fraîcheur</th>
                  <th className="px-4 py-3">État du collecteur</th>
                  <th className="px-4 py-3">Conformité SLA</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sources.map((s) => (
                  <tr key={s.sourceId} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-mono font-bold text-foreground">
                      {s.sourceId}
                    </td>
                    <td className="px-4 py-3 font-medium text-foreground">{s.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{s.institution}</td>
                    <td className="px-4 py-3 capitalize text-muted-foreground">
                      {s.frequency}
                    </td>
                    <td className="px-4 py-3 font-mono text-foreground">
                      {s.freshnessSlaDays} jours
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded text-[11px] font-semibold uppercase ${
                          s.status.toLowerCase() === "failed" || s.status.toLowerCase() === "error"
                            ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                            : s.status.toLowerCase() === "running"
                            ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                            : "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                        }`}
                      >
                        {s.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {s.isStale ? (
                        <span className="inline-flex items-center gap-1 text-rose-700 dark:text-rose-400 font-semibold">
                          <AlertCircle className="w-3.5 h-3.5" />
                          Retard (DATA_STALE)
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400 font-semibold">
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
