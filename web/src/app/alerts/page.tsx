"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle,
  Clock,
  Copy,
  Filter,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { formatMonthYear } from "@/lib/formatters";

interface AlertItem {
  alertId: string;
  ruleCode: string;
  dedupeKey: string;
  severity: "high" | "medium" | "low";
  title: string;
  evidence: Record<string, any>;
  state: "open" | "acknowledged" | "resolved";
  firstSeenAt: string;
  lastSeenAt: string;
}

export default function AlertsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);
  const [stateFilter, setStateFilter] = useState<string>("");
  const [actionLoading, setActionLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const apiUrl = "/api";
      const params = new URLSearchParams();
      if (stateFilter) params.set("state", stateFilter);

      const res = await fetch(`${apiUrl}/v1/alerts?${params.toString()}`, {
        credentials: "include",
      });

      if (!res.ok) {
        throw new Error(`Erreur API: ${res.statusText}`);
      }

      const data = await res.json();
      const items: AlertItem[] = data.map((a: any) => ({
        alertId: a.alert_id,
        ruleCode: a.rule_code,
        dedupeKey: a.dedupe_key,
        severity: a.severity,
        title: a.title,
        evidence: a.evidence || {},
        state: a.state,
        firstSeenAt: a.first_seen_at,
        lastSeenAt: a.last_seen_at,
      }));

      setAlerts(items);
      setSelectedAlert((prev) => prev || (items.length > 0 ? items[0] : null));
    } catch (err: any) {
      setError(err.message || "Erreur de chargement des alertes de marché");
    } finally {
      setLoading(false);
    }
  }, [stateFilter]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const handleUpdateState = async (alertId: string, newState: "acknowledged" | "resolved") => {
    setActionLoading(true);
    try {
      const apiUrl = "/api";
      const res = await fetch(`${apiUrl}/v1/alerts/${alertId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ state: newState }),
      });

      if (!res.ok) {
        throw new Error("Action non autorisée ou erreur serveur");
      }

      const updated = await res.json();
      setAlerts((prev) =>
        prev.map((a) => (a.alertId === alertId ? { ...a, state: updated.state } : a))
      );
      if (selectedAlert?.alertId === alertId) {
        setSelectedAlert((prev) => prev ? { ...prev, state: updated.state } : null);
      }
    } catch (err: any) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const copyEvidence = () => {
    if (selectedAlert) {
      navigator.clipboard.writeText(JSON.stringify(selectedAlert.evidence, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const highCount = alerts.filter((a) => a.severity === "high").length;
  const mediumCount = alerts.filter((a) => a.severity === "medium").length;
  const resolvedCount = alerts.filter((a) => a.state === "resolved").length;

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case "high":
        return "bg-rose-500/10 text-rose-400 border-rose-500/20";
      case "medium":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      default:
        return "bg-slate-800 text-slate-300 border-white/10";
    }
  };

  const getStateBadge = (st: string) => {
    switch (st) {
      case "open":
        return "bg-rose-500/15 text-rose-300 border-rose-500/30";
      case "acknowledged":
        return "bg-sky-500/15 text-sky-300 border-sky-500/30";
      case "resolved":
        return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
      default:
        return "bg-slate-800 text-slate-400 border-white/10";
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight text-white flex items-center gap-2.5">
              <AlertTriangle className="w-6 h-6 text-amber-400" />
              Centre d&apos;alertes & Détection de tensions
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-rose-500/10 text-rose-300 border border-rose-500/20">
              {alerts.length} signaux
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Détection algorithmique idempotente des pics de prix, ruptures d&apos;approvisionnement et anomalies spatiales.
          </p>
        </div>

        {/* State filters */}
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            className="text-xs bg-slate-900 border border-white/[0.1] rounded-xl px-3 py-1.5 text-white shadow-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
          >
            <option value="">Tous les états</option>
            <option value="open">Ouvertes (Open)</option>
            <option value="acknowledged">Acquittées (Acknowledged)</option>
            <option value="resolved">Résolues (Resolved)</option>
          </select>
        </div>
      </div>

      {/* KPI Severity Ribbon */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="glass-panel p-3.5 rounded-xl border border-white/[0.08]">
          <span className="text-[10px] font-mono uppercase text-slate-400">Total Alertes</span>
          <div className="text-xl font-bold font-mono text-white mt-0.5">{alerts.length}</div>
        </div>
        <div className="glass-panel p-3.5 rounded-xl border border-rose-500/20 bg-rose-500/5">
          <span className="text-[10px] font-mono uppercase text-rose-400">Sévérité Haute</span>
          <div className="text-xl font-bold font-mono text-rose-300 mt-0.5">{highCount}</div>
        </div>
        <div className="glass-panel p-3.5 rounded-xl border border-amber-500/20 bg-amber-500/5">
          <span className="text-[10px] font-mono uppercase text-amber-400">Sévérité Moyenne</span>
          <div className="text-xl font-bold font-mono text-amber-300 mt-0.5">{mediumCount}</div>
        </div>
        <div className="glass-panel p-3.5 rounded-xl border border-emerald-500/20 bg-emerald-500/5">
          <span className="text-[10px] font-mono uppercase text-emerald-400">Résolues</span>
          <div className="text-xl font-bold font-mono text-emerald-300 mt-0.5">{resolvedCount}</div>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs">
          {error}
        </div>
      )}

      {/* Main Grid: List + Detail */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* List of alerts */}
        <div className="lg:col-span-2 glass-card rounded-2xl overflow-hidden flex flex-col justify-between">
          <div className="p-4 border-b border-white/[0.07] flex items-center justify-between">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 text-emerald-400" />
              Signaux de marché en cours ({alerts.length})
            </h2>
            <button
              onClick={fetchAlerts}
              className="text-xs text-slate-400 hover:text-white flex items-center gap-1.5 transition-colors font-mono"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-emerald-400" : ""}`} />
              Actualiser
            </button>
          </div>

          {loading ? (
            <div className="p-16 text-center text-xs text-slate-400 font-mono">
              Chargement des alertes de marché...
            </div>
          ) : alerts.length === 0 ? (
            <div className="p-16 text-center text-xs text-slate-400 font-mono">
              Aucune alerte active ne correspond à ce filtre.
            </div>
          ) : (
            <div className="divide-y divide-white/[0.04] max-h-[500px] overflow-y-auto">
              {alerts.map((al) => {
                const isSelected = selectedAlert?.alertId === al.alertId;
                return (
                  <button
                    key={al.alertId}
                    onClick={() => setSelectedAlert(al)}
                    className={`w-full p-4 text-left transition-all flex items-start justify-between gap-4 ${
                      isSelected
                        ? "bg-emerald-500/10 border-l-4 border-l-emerald-400"
                        : "hover:bg-white/[0.02]"
                    }`}
                  >
                    <div className="space-y-1.5 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase border ${getSeverityBadge(
                            al.severity
                          )}`}
                        >
                          {al.severity}
                        </span>
                        <span className="font-semibold text-sm text-white truncate">
                          {al.title}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-slate-400 font-mono">
                        <span className="text-emerald-400">{al.ruleCode}</span>
                        <span>•</span>
                        <span>Vu le {formatMonthYear(al.lastSeenAt)}</span>
                      </div>
                    </div>

                    <span
                      className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold border capitalize shrink-0 ${getStateBadge(
                        al.state
                      )}`}
                    >
                      {al.state}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Alert Detail Panel */}
        <div className="glass-card rounded-2xl p-5 space-y-4 flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-bold text-white border-b border-white/[0.07] pb-3 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-emerald-400" />
                Dossier d&apos;alerte
              </span>
              {selectedAlert && (
                <span className="text-[10px] font-mono text-slate-400">
                  {selectedAlert.alertId.slice(0, 8)}...
                </span>
              )}
            </h2>

            {selectedAlert ? (
              <div className="space-y-4 text-xs mt-3">
                <div>
                  <span className="text-[11px] font-mono text-slate-400 block mb-1">
                    Événement détecté :
                  </span>
                  <span className="font-bold text-sm text-white">
                    {selectedAlert.title}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 py-2.5 border-y border-white/[0.06] font-mono text-[11px]">
                  <div>
                    <span className="text-slate-400 block text-[10px]">Règle SPECS §18 :</span>
                    <span className="font-semibold text-emerald-400">
                      {selectedAlert.ruleCode}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px]">Statut :</span>
                    <span className="font-semibold uppercase text-white">
                      {selectedAlert.state}
                    </span>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[11px] font-mono text-slate-400">
                      Preuves & métriques déclenchantes :
                    </span>
                    <button
                      onClick={copyEvidence}
                      className="text-[10px] text-slate-400 hover:text-white flex items-center gap-1 font-mono"
                    >
                      <Copy className="w-3 h-3" />
                      {copied ? "Copié !" : "Copier JSON"}
                    </button>
                  </div>
                  <pre className="p-3 bg-slate-950/80 border border-white/[0.06] rounded-xl font-mono text-[10px] overflow-x-auto text-emerald-300 max-h-48">
                    {JSON.stringify(selectedAlert.evidence, null, 2)}
                  </pre>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-400 py-8 text-center font-mono">
                Sélectionnez une alerte pour afficher ses détails et preuves.
              </p>
            )}
          </div>

          {/* Action buttons (admin) */}
          {selectedAlert && (
            <div className="pt-3 border-t border-white/[0.07] flex gap-2">
              {selectedAlert.state === "open" && (
                <button
                  disabled={actionLoading}
                  onClick={() => handleUpdateState(selectedAlert.alertId, "acknowledged")}
                  className="flex-1 py-2 px-3 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-semibold transition-all hover:scale-102"
                >
                  Acquitter l&apos;alerte
                </button>
              )}
              {selectedAlert.state !== "resolved" && (
                <button
                  disabled={actionLoading}
                  onClick={() => handleUpdateState(selectedAlert.alertId, "resolved")}
                  className="flex-1 py-2 px-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition-all hover:scale-102"
                >
                  Marquer résolue
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
