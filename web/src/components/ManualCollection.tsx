"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CollectionReceipt, collectionCounts, collectionStage } from "../lib/manual-collection";

export function useManualCollection(onFinished: () => void) {
  const [receipt, setReceipt] = useState<CollectionReceipt | null>(null);
  const [eligible, setEligible] = useState<string[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const guard = useRef(false);
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;
  const lastFinished = useRef("");

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      try {
        const [history, options] = await Promise.all([
          fetch("/api/v1/sources/collections", { cache: "no-store", signal: controller.signal }),
          fetch("/api/v1/sources/collection-options", { cache: "no-store", signal: controller.signal }),
        ]);
        if (!history.ok || !options.ok) throw new Error("monitoring_unavailable");
        const rows: CollectionReceipt[] = await history.json();
        const available: string[] = await options.json();
        if (!active) return;
        setEligible(available);
        if (rows[0]) {
          setReceipt(rows[0]);
          if (rows[0].status !== "running" && lastFinished.current !== rows[0].request_id) {
            lastFinished.current = rows[0].request_id;
            onFinishedRef.current();
          }
        }
      } catch {
        if (active) {
          setEligible([]);
          setError("Suivi de collecte indisponible. Ne supposez pas que l’opération a réussi ; aucune relance automatique.");
        }
      } finally {
        if (active) timer = setTimeout(poll, 2500);
      }
    }
    poll();
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, []);

  const start = useCallback(async (sourceId?: string) => {
    if (guard.current || receipt?.status === "running") return;
    guard.current = true;
    setSending(true);
    setError(null);
    try {
      const response = await fetch("/api/v1/sources/collect", {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: crypto.randomUUID(), source_id: sourceId ?? null }),
      });
      if (!response.ok) {
        throw new Error(response.status === 409
          ? "Une collecte est déjà en cours, ou cette source n’est pas autorisée. Consultez le suivi."
          : "Réponse de collecte non confirmée. Consultez le suivi avant un nouveau lancement.");
      }
      setReceipt(await response.json());
      onFinishedRef.current();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Réponse perdue ; vérifiez le suivi, sans relance automatique.");
    } finally {
      guard.current = false;
      setSending(false);
    }
  }, [receipt]);

  return { receipt, eligible, busy: sending || receipt?.status === "running", start, error };
}

export function ManualCollectionStatus({ receipt, error }: {
  receipt: CollectionReceipt | null; error: string | null;
}) {
  const counts = receipt && collectionCounts(receipt);
  return <section aria-label="Suivi de la collecte" className="rounded-2xl border border-emerald-500/20 bg-slate-950/60 p-5 space-y-3">
    <h2 className="font-bold text-white">Collecte des sources publiques</h2>
    <p className="text-sm text-slate-300">Seules les sources autorisées disposant d’un connecteur sont sollicitées. Les contrôles et quotas restent obligatoires. La collecte peut prendre plusieurs minutes.</p>
    <p className="text-xs text-slate-400">Banque mondiale : jusqu’à 120 estimations de riz sur une fenêtre récente avec contexte officiel. Couverture partielle, sans garantie de fraîcheur ; ce sont des valeurs imputées.</p>
    {error && <p role="alert" className="text-sm text-amber-300">{error}</p>}
    {receipt && counts ? <>
      <p role="status" aria-live="polite" className="text-sm text-emerald-200">{collectionStage(receipt)}</p>
      <p className="text-xs text-slate-300">{counts.sources} / {receipt.source_ids.length} sources abouties · {counts.documents} documents récupérés, dont {counts.newDocuments} nouveaux · {counts.records} enregistrements intégrés/révisés</p>
      <ul className="text-xs space-y-2 text-slate-300">{receipt.outcomes.map(item => <li key={item.source_id}>
        {item.source_id} : {item.status === "success" ? "collecte aboutie" : item.status === "running" ? "en traitement" : item.status === "blocked" ? "non autorisée" : "échec"}
        {item.run_id && <span className="block break-all text-slate-500">Référence : {item.run_id}</span>}
      </li>)}</ul>
      <p className="text-xs text-slate-400">Publication des indicateurs : {receipt.publication === "succeeded" ? "réussie" : receipt.publication === "failed" ? "refusée — données collectées non publiées" : receipt.publication === "running" ? "en cours" : "non réalisée"}. Les bulletins ne sont pas régénérés.</p>
      <p className="text-[10px] text-slate-500 break-all">Reçu persistant : {receipt.request_id}</p>
    </> : <p className="text-xs text-slate-400">Aucune collecte manuelle enregistrée.</p>}
  </section>;
}
