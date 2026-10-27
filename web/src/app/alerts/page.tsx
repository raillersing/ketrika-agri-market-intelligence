"use client";

import React, { useEffect, useState } from "react";
import { Bell, Copy, RefreshCw } from "lucide-react";
import { alertSeverityLabel, alertStateLabel, humanDate } from "@/lib/reading";

type AlertItem = { alert_id: string; rule_code: string; severity: string; title: string; evidence: Record<string, unknown>; state: string; product_code: string | null; location_pcode: string | null; first_seen_at: string; last_seen_at: string };
export default function AlertsPage() {
  const [items, setItems] = useState<AlertItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [stateFilter, setStateFilter] = useState("");
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(null); setItems([]);
    async function load() {
      try {
        const params = new URLSearchParams();
        if (stateFilter) params.set("state", stateFilter);
        const response = await fetch(`/api/v1/alerts?${params}`, { credentials: "include", signal: controller.signal });
        if (!response.ok) throw new Error(`Les alertes sont indisponibles (HTTP ${response.status}).`);
        const data: AlertItem[] = await response.json();
        if (!controller.signal.aborted) setItems(data);
      } catch (failure) { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Les alertes sont indisponibles."); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load(); return () => controller.abort();
  }, [stateFilter, revision]);
  const selected = items.find(item => item.alert_id === selectedId) || items[0] || null;
  const update = async (state: "acknowledged" | "resolved") => {
    if (!selected) return;
    setSaving(true); setActionError(null); setFeedback(null);
    try {
      const response = await fetch(`/api/v1/alerts/${encodeURIComponent(selected.alert_id)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ state }) });
      if (!response.ok) throw new Error(response.status === 403 ? "Seul un administrateur peut modifier le suivi de cette alerte." : "Le changement d’état n’a pas pu être enregistré.");
      setFeedback("Le suivi de l’alerte a été mis à jour."); setRevision(value => value + 1);
    } catch (failure) { setActionError(failure instanceof Error ? failure.message : "La mise à jour a échoué."); }
    finally { setSaving(false); }
  };
  const copy = async () => {
    if (!selected) return;
    try { await navigator.clipboard.writeText(JSON.stringify(selected.evidence, null, 2)); setFeedback("Détails copiés."); }
    catch { setActionError("Copie indisponible. Vous pouvez sélectionner le texte dans les détails."); }
  };
  return <div className="space-y-6">
    <header className="space-y-2"><h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold"><Bell aria-hidden="true" className="h-6 w-6 shrink-0 text-primary-readable" />Alertes enregistrées</h1><p className="max-w-3xl text-sm leading-6 text-muted-foreground">Examinez un signal, ses dates et les éléments enregistrés avant d’en modifier le suivi. L’absence d’alerte ne suffit pas à conclure que le marché est stable.</p></header>
    <div className="flex flex-wrap items-end gap-3"><label className="flex flex-col gap-1 text-xs text-muted-foreground">État de l’alerte<select value={stateFilter} onChange={event => { setStateFilter(event.target.value); setActionError(null); setFeedback(null); }} className="min-h-[44px] rounded-lg border border-border bg-card px-3 text-sm text-foreground focus:ring-2 focus:ring-ring"><option value="">Tous les états</option><option value="open">À examiner</option><option value="acknowledged">Prises en compte</option><option value="resolved">Résolues</option></select></label><button type="button" disabled={loading} onClick={() => setRevision(value => value + 1)} className="inline-flex min-h-[44px] items-center gap-2 rounded-lg border border-border px-3 text-sm text-muted-foreground disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"><RefreshCw aria-hidden="true" className="h-4 w-4" />Actualiser</button></div>
    {loading ? <p role="status" className="text-sm text-muted-foreground">Chargement des alertes…</p> : error ? <p role="alert" className="rounded-xl border border-rose-500/20 p-4 text-sm text-rose-700 dark:text-rose-300">{error}</p> : <>
      <div className="grid gap-3 sm:grid-cols-3">{[["Résultats du filtre", items.length], ["Priorité élevée", items.filter(item => item.severity === "high").length], ["À examiner", items.filter(item => item.state === "open").length]].map(([label, count]) => <div key={label} className="rounded-xl border border-border bg-card p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 text-2xl font-semibold">{count}</p></div>)}</div>
      {!items.length ? <section className="rounded-xl border border-border bg-card p-6"><h2 className="font-medium">Aucune alerte enregistrée pour ce filtre</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">Cette liste ne mesure pas la couverture de surveillance. Un manque de données, une collecte interrompue ou une règle non évaluée peuvent empêcher la production d’alertes.</p></section> : <div className="grid min-w-0 gap-5 lg:grid-cols-2">
        <section aria-label="Liste des alertes" className="min-w-0 space-y-3">{items.map(item => <button key={item.alert_id} type="button" aria-pressed={selected?.alert_id === item.alert_id} onClick={() => { setSelectedId(item.alert_id); setActionError(null); setFeedback(null); }} className={`w-full break-words rounded-xl border bg-card p-5 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring ${selected?.alert_id === item.alert_id ? "border-primary" : "border-border"}`}><span className="flex flex-wrap gap-2 text-xs"><span className={`rounded border px-2 py-1 ${item.severity === "high" ? "border-rose-500/30 text-rose-700 dark:text-rose-300" : "border-border text-muted-foreground"}`}>{alertSeverityLabel(item.severity)}</span><span className="rounded border border-border px-2 py-1 text-muted-foreground">{alertStateLabel(item.state)}</span></span><span className="mt-3 block text-base font-medium">{item.title}</span><span className="mt-2 block text-xs leading-5 text-muted-foreground">Dernier signalement : {humanDate(item.last_seen_at)}</span></button>)}</section>
        {selected && <section aria-labelledby="alert-detail-title" className="min-w-0 break-words rounded-xl border border-border bg-card p-5"><h2 id="alert-detail-title" className="text-lg font-medium">Comprendre ce signal</h2><p className="mt-3 font-medium">{selected.title}</p><dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2">{[["Produit", selected.product_code || "Non renseigné"], ["Zone", selected.location_pcode || "Non renseignée"], ["Premier signalement", humanDate(selected.first_seen_at)], ["Dernier signalement", humanDate(selected.last_seen_at)], ["Priorité", alertSeverityLabel(selected.severity)], ["Suivi", alertStateLabel(selected.state)]].map(([term, value]) => <div key={term}><dt className="text-xs text-muted-foreground">{term}</dt><dd className="mt-1">{value}</dd></div>)}</dl><p className="mt-5 border-t border-border pt-4 text-sm leading-6 text-muted-foreground">Vérifiez la période, la nature des données et les preuves disponibles. Ce signal ne constitue pas, à lui seul, un diagnostic de rupture ou une recommandation d’achat.</p><details className="mt-5 rounded-lg border border-border p-3"><summary className="cursor-pointer rounded py-2 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">Voir les éléments enregistrés</summary><p className="mt-3 text-xs text-muted-foreground">Règle : {selected.rule_code}</p><pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words text-xs text-muted-foreground">{JSON.stringify(selected.evidence || {}, null, 2)}</pre><button type="button" onClick={copy} className="mt-2 inline-flex min-h-[44px] items-center gap-2 rounded px-2 text-sm text-primary-readable focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"><Copy aria-hidden="true" className="h-4 w-4" />Copier les détails</button></details>
          {selected.state !== "resolved" && <div className="mt-5 border-t border-border pt-4"><p className="mb-3 text-xs leading-5 text-muted-foreground">Les changements de suivi sont réservés aux administrateurs.</p><div className="flex flex-wrap gap-3">{selected.state === "open" && <button type="button" disabled={saving} onClick={() => update("acknowledged")} className="min-h-[44px] rounded-lg border border-border px-3 text-sm disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">Prendre en compte</button>}<button type="button" disabled={saving} onClick={() => update("resolved")} className="min-h-[44px] rounded-lg bg-primary-action px-3 text-sm text-primary-foreground disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">Marquer comme résolue</button></div></div>}
        </section>}
      </div>}
    </>}{feedback && <p role="status" className="text-sm text-primary-readable">{feedback}</p>}{actionError && <p role="alert" className="text-sm text-rose-700 dark:text-rose-300">{actionError}</p>}
  </div>;
}
