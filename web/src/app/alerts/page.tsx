"use client";

import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle, Clock, Filter, RefreshCw, ShieldAlert } from "lucide-react";
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

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
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
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
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

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case "high":
        return "bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950 dark:text-rose-300";
      case "medium":
        return "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300";
      default:
        return "bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-800 dark:text-slate-300";
    }
  };

  const getStateBadge = (st: string) => {
    switch (st) {
      case "open":
        return "bg-rose-50 text-rose-700 border-rose-200";
      case "acknowledged":
        return "bg-blue-50 text-blue-700 border-blue-200";
      case "resolved":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      default:
        return "bg-slate-50 text-slate-700 border-slate-200";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <AlertTriangle className="w-6 h-6 text-rose-600" />
            Alertes et signaux de tension de marché
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Détection automatique de flambées de prix, disparités anormales et ruptures d&apos;approvisionnement.
          </p>
        </div>

        {/* State filters */}
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-muted-foreground" />
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            className="text-xs bg-card border border-input rounded-md px-2.5 py-1.5 shadow-sm"
          >
            <option value="">Tous les états</option>
            <option value="open">Ouvertes (Open)</option>
            <option value="acknowledged">Acquittées (Acknowledged)</option>
            <option value="resolved">Résolues (Resolved)</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-md text-rose-700 text-xs">
          {error}
        </div>
      )}

      {/* Main Grid: List + Detail */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* List of alerts */}
        <div className="lg:col-span-2 bg-card border border-border rounded-lg overflow-hidden shadow-sm">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">
              Alertes détectées ({alerts.length})
            </h2>
            <button
              onClick={fetchAlerts}
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              Actualiser
            </button>
          </div>

          {loading ? (
            <div className="p-12 text-center text-sm text-muted-foreground">
              Chargement des alertes...
            </div>
          ) : alerts.length === 0 ? (
            <div className="p-12 text-center text-sm text-muted-foreground">
              Aucune alerte active ne correspond à ce filtre.
            </div>
          ) : (
            <div className="divide-y divide-border">
              {alerts.map((al) => {
                const isSelected = selectedAlert?.alertId === al.alertId;
                return (
                  <button
                    key={al.alertId}
                    onClick={() => setSelectedAlert(al)}
                    className={`w-full p-4 text-left transition-colors flex items-start justify-between gap-4 ${
                      isSelected
                        ? "bg-muted/40 border-l-4 border-l-emerald-600"
                        : "hover:bg-muted/20"
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${getSeverityBadge(
                            al.severity
                          )}`}
                        >
                          {al.severity}
                        </span>
                        <span className="font-semibold text-sm text-foreground">
                          {al.title}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <span className="font-mono">{al.ruleCode}</span>
                        <span>•</span>
                        <span>Vu le {formatMonthYear(al.lastSeenAt)}</span>
                      </div>
                    </div>

                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium border capitalize ${getStateBadge(
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
        <div className="bg-card border border-border rounded-lg p-5 shadow-sm space-y-4">
          <h2 className="text-sm font-semibold text-foreground border-b border-border pb-2 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-emerald-600" />
            Détail de l&apos;alerte
          </h2>

          {selectedAlert ? (
            <div className="space-y-4 text-xs">
              <div>
                <span className="text-muted-foreground block mb-1">Titre de l&apos;alerte :</span>
                <span className="font-bold text-sm text-foreground">
                  {selectedAlert.title}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 py-2 border-y border-border">
                <div>
                  <span className="text-muted-foreground block">Règle :</span>
                  <span className="font-mono font-semibold text-foreground">
                    {selectedAlert.ruleCode}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">Statut actuel :</span>
                  <span className="font-semibold uppercase text-foreground">
                    {selectedAlert.state}
                  </span>
                </div>
              </div>

              <div>
                <span className="text-muted-foreground block mb-1">Preuve et métriques déclenchantes :</span>
                <pre className="p-3 bg-muted rounded font-mono text-[11px] overflow-x-auto text-foreground">
                  {JSON.stringify(selectedAlert.evidence, null, 2)}
                </pre>
              </div>

              {/* Action buttons (admin) */}
              <div className="pt-2 border-t border-border flex gap-2">
                {selectedAlert.state === "open" && (
                  <button
                    disabled={actionLoading}
                    onClick={() => handleUpdateState(selectedAlert.alertId, "acknowledged")}
                    className="flex-1 py-1.5 px-3 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-medium transition-colors"
                  >
                    Acquitter l&apos;alerte
                  </button>
                )}
                {selectedAlert.state !== "resolved" && (
                  <button
                    disabled={actionLoading}
                    onClick={() => handleUpdateState(selectedAlert.alertId, "resolved")}
                    className="flex-1 py-1.5 px-3 bg-emerald-700 hover:bg-emerald-800 text-white rounded text-xs font-medium transition-colors"
                  >
                    Marquer résolue
                  </button>
                )}
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              Sélectionnez une alerte pour afficher ses détails et preuves.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
