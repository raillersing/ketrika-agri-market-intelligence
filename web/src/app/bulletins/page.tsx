"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, FileText } from "lucide-react";
import { bulletinStateLabel, humanDate } from "@/lib/reading";

type Bulletin = { bulletin_id: string; period_start: string; period_end: string; status: string; created_at: string; facts: Record<string, unknown> };
export default function BulletinsPage() {
  const [items, setItems] = useState<Bulletin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch("/api/v1/bulletins", { credentials: "include", signal: controller.signal });
        if (!response.ok) throw new Error(`Les bulletins sont indisponibles (HTTP ${response.status}).`);
        const data: Bulletin[] = await response.json();
        if (!controller.signal.aborted) setItems(data);
      } catch (failure) { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Les bulletins sont indisponibles."); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load(); return () => controller.abort();
  }, []);
  return <div className="space-y-6">
    <header className="space-y-2"><h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold"><FileText aria-hidden="true" className="h-6 w-6 shrink-0 text-primary-readable" />Bulletins de veille</h1><p className="max-w-3xl text-sm leading-6 text-muted-foreground">Retrouvez les faits enregistrés pour chaque période. Le statut d’approbation ne garantit pas, à lui seul, la qualification des données.</p></header>
    <div className="grid gap-3 sm:grid-cols-3">{[["Brouillon", "Une édition à examiner."], ["Approuvé", "Une validation éditoriale enregistrée."], ["Envoi enregistré", "Un état enregistré à vérifier dans le suivi d’envoi."]].map(([label, description]) => <div key={label} className="rounded-xl border border-border bg-card p-4"><p className="font-medium">{label}</p><p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p></div>)}</div>
    {error && <p role="alert" className="rounded-xl border border-rose-500/20 p-4 text-sm text-rose-700 dark:text-rose-300">{error}</p>}
    {loading ? <p role="status" className="text-sm text-muted-foreground">Chargement des bulletins…</p> : !error && <section aria-label="Éditions disponibles" className="divide-y divide-border rounded-xl border border-border bg-card">
      {!items.length ? <div className="p-6"><h2 className="font-medium">Aucun bulletin enregistré</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">Les éditions apparaîtront ici après leur préparation à partir de faits disponibles.</p></div> : items.map(item => <article key={item.bulletin_id} className="flex flex-wrap items-center justify-between gap-4 p-5">
        <div className="min-w-0"><p className="text-xs text-muted-foreground">Du {humanDate(item.period_start)} au {humanDate(item.period_end)}</p><h2 className="mt-2 text-lg font-medium">Bulletin de veille des marchés vivriers</h2><p className="mt-2 text-sm text-muted-foreground">{bulletinStateLabel(item.status)} · Créé le {humanDate(item.created_at)}</p></div>
        <Link href={`/bulletins/${item.bulletin_id}`} className="inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-primary-action px-4 py-2 text-sm text-primary-foreground hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">Lire le bulletin<ArrowRight aria-hidden="true" className="h-4 w-4" /></Link>
      </article>)}
    </section>}
  </div>;
}
