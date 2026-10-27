"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { BRAND } from "@/lib/brand";
import { bulletinStateLabel, humanDate, recordedFacts } from "@/lib/reading";
import { SourceBadge } from "@/components/ui/SourceBadge";
import { ProvenanceLink } from "@/components/ui/ProvenanceLink";

type Bulletin = { bulletin_id: string; status: string; period_start: string; period_end: string; created_at: string; approved_at: string | null; facts: Record<string, unknown> };
export default function BulletinDetailPage() {
  const id = useParams()?.id as string;
  const [bulletin, setBulletin] = useState<Bulletin | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setBulletin(null); setLoading(true); setError(null); setFeedback(null); setActionError(null);
    async function load() {
      try {
        const response = await fetch(`/api/v1/bulletins/${encodeURIComponent(id)}`, { credentials: "include", signal: controller.signal });
        if (!response.ok) throw new Error(response.status === 404 ? "Ce bulletin est introuvable." : `Le bulletin est indisponible (HTTP ${response.status}).`);
        const data: Bulletin = await response.json();
        if (!controller.signal.aborted) setBulletin(data);
      } catch (failure) { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Le bulletin est indisponible."); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    }
    if (id) void load();
    return () => controller.abort();
  }, [id]);
  const approve = async () => {
    setApproving(true); setFeedback(null); setActionError(null);
    try {
      const response = await fetch(`/api/v1/bulletins/${encodeURIComponent(id)}/approve`, { method: "POST", credentials: "include" });
      if (!response.ok) throw new Error(response.status === 403 ? "Seul un administrateur peut approuver ce bulletin." : "L’approbation n’a pas pu être enregistrée.");
      setBulletin(await response.json()); setFeedback("Approbation enregistrée. Cette action n’envoie pas le bulletin.");
    } catch (failure) { setActionError(failure instanceof Error ? failure.message : "L’approbation n’a pas pu être enregistrée."); }
    finally { setApproving(false); }
  };
  const facts = recordedFacts(bulletin?.facts || {});
  const missing = Object.keys(bulletin?.facts || {}).length - facts.length;
  return <div className="mx-auto max-w-4xl space-y-6">
    <Link href="/bulletins" className="inline-flex min-h-[44px] items-center gap-2 rounded px-2 text-sm text-muted-foreground hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"><ArrowLeft aria-hidden="true" className="h-4 w-4" />Retour aux bulletins</Link>
    {loading ? <p role="status" className="text-sm text-muted-foreground">Chargement du bulletin…</p> : error || !bulletin ? <p role="alert" className="rounded-xl border border-rose-500/20 p-5 text-sm text-rose-700 dark:text-rose-300">{error || "Bulletin indisponible."}</p> : <>
      <header className="space-y-3 border-b border-border pb-5"><p className="text-xs text-muted-foreground">{BRAND.name}</p><h1 className="text-2xl font-semibold">Bulletin de veille des marchés vivriers</h1><p className="text-sm text-muted-foreground">Du {humanDate(bulletin.period_start)} au {humanDate(bulletin.period_end)}</p><p className="text-sm"><span className="rounded-md border border-border bg-card px-2 py-1">{bulletinStateLabel(bulletin.status)}</span><span className="ml-3 text-muted-foreground">Créé le {humanDate(bulletin.created_at)}</span></p>{bulletin.approved_at && <p className="text-sm text-muted-foreground">Approbation enregistrée le {humanDate(bulletin.approved_at)}</p>}</header>
      <section className="rounded-xl border border-border bg-card p-5"><h2 className="font-medium">À savoir avant de lire</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">Les éléments ci-dessous sont les faits enregistrés dans cette édition. Leur présence ou l’approbation du bulletin ne suffit pas à qualifier les sources. Aucune synthèse de marché ou perspective météo n’est ajoutée en l’absence de contenu reçu.</p></section>
      <section aria-labelledby="recorded-facts"><h2 id="recorded-facts" className="text-lg font-medium">Faits enregistrés</h2>{!facts.length ? <p className="mt-3 rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">Aucun fait présentable n’est disponible dans cette édition.</p> : <div className="mt-4 grid gap-4 sm:grid-cols-2">{facts.map(fact => <article key={fact.id} className="min-w-0 break-words rounded-xl border border-border bg-card p-5"><h3 className="text-sm font-medium">{fact.label}</h3><p className="mt-3 text-xl font-semibold">{fact.display ?? "Valeur non renseignée"}{fact.unit ? ` ${fact.unit}` : ""}</p><div className="mt-4 flex flex-wrap gap-2">{fact.sources.length ? fact.sources.map(source => <SourceBadge key={source} sourceId={source} />) : <span className="text-xs text-muted-foreground">Source non renseignée</span>}</div>{fact.observationIds.length > 0 && <div className="mt-3 flex flex-wrap gap-3">{fact.observationIds.map((observation, index) => <ProvenanceLink key={observation} observationId={observation} label={`Pièce ${index + 1}`} />)}</div>}</article>)}</div>}{missing > 0 && <p className="mt-3 text-sm text-muted-foreground">Certains éléments ont une structure non reconnue. Ils restent consultables dans les détails enregistrés.</p>}</section>
      <details className="rounded-xl border border-border bg-card p-4"><summary className="cursor-pointer rounded py-2 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">Détails enregistrés et données brutes</summary><pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs text-muted-foreground">{JSON.stringify(bulletin.facts || {}, null, 2)}</pre></details>
      {feedback && <p role="status" className="text-sm text-primary-readable">{feedback}</p>}{actionError && <p role="alert" className="text-sm text-rose-700 dark:text-rose-300">{actionError}</p>}
      {bulletin.status === "draft" && <div className="rounded-xl border border-border p-5"><p className="mb-3 text-sm leading-6 text-muted-foreground">L’approbation est réservée aux administrateurs. Elle n’envoie pas le bulletin.</p><button type="button" onClick={approve} disabled={approving} aria-busy={approving} className="inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-primary-action px-4 py-2 text-sm text-primary-foreground hover:bg-primary-hover disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"><CheckCircle2 aria-hidden="true" className="h-4 w-4" />{approving ? "Approbation en cours…" : "Approuver le bulletin"}</button></div>}
    </>}
  </div>;
}
