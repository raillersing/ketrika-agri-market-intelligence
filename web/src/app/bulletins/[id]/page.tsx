"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle2, Download, FileText, RefreshCw, ShieldCheck } from "lucide-react";

export default function BulletinDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [bulletin, setBulletin] = useState<any>(null);
  const [approving, setApproving] = useState(false);

  useEffect(() => {
    async function fetchDetail() {
      setLoading(true);
      setError(null);
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
        const res = await fetch(`${apiUrl}/v1/bulletins/${id}`, {
          credentials: "include",
        });

        if (!res.ok) {
          throw new Error("Bulletin introuvable ou erreur serveur");
        }

        const data = await res.json();
        setBulletin(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    if (id) fetchDetail();
  }, [id]);

  const handleApprove = async () => {
    setApproving(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
      const res = await fetch(`${apiUrl}/v1/bulletins/${id}/approve`, {
        method: "POST",
        credentials: "include",
      });

      if (!res.ok) {
        throw new Error("Impossible d'approuver le bulletin (accès administrateur requis)");
      }

      const updated = await res.json();
      setBulletin(updated);
      alert("Le bulletin a été approuvé avec succès !");
    } catch (err: any) {
      alert(err.message);
    } finally {
      setApproving(false);
    }
  };

  if (loading) {
    return (
      <div className="p-12 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
        <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
        Chargement du bulletin hebdomadaire...
      </div>
    );
  }

  if (error || !bulletin) {
    return (
      <div className="space-y-4">
        <Link href="/bulletins" className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
          <ArrowLeft className="w-3.5 h-3.5" />
          Retour aux bulletins
        </Link>
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-sm">
          {error || "Bulletin introuvable"}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Top back navigation */}
      <div className="flex items-center justify-between">
        <Link href="/bulletins" className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground">
          <ArrowLeft className="w-3.5 h-3.5" />
          Retour à la liste des bulletins
        </Link>

        <div className="flex items-center gap-3">
          {bulletin.status === "draft" && (
            <button
              onClick={handleApprove}
              disabled={approving}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-700 hover:bg-emerald-800 text-white rounded text-xs font-semibold shadow-sm transition-colors"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{approving ? "Approbation..." : "Approuver (Admin)"}</span>
            </button>
          )}

          {bulletin.pdf_url && (
            <a
              href={bulletin.pdf_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-card border border-border rounded text-xs font-medium text-foreground hover:bg-muted transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Télécharger le PDF</span>
            </a>
          )}
        </div>
      </div>

      {/* Document card */}
      <div className="bg-card border border-border rounded-xl shadow-md p-8 space-y-6">
        <div className="border-b border-border pb-6 flex items-start justify-between gap-4">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-600 block mb-1">
              Ketrika Agri Market Intelligence • Bulletin Officiel
            </span>
            <h1 className="text-2xl font-bold text-foreground">
              Conjoncture hebdomadaire des marchés vivriers (PPN)
            </h1>
            <p className="text-xs text-muted-foreground mt-1">
              Période sous revue : du {bulletin.period_start} au {bulletin.period_end}
            </p>
          </div>

          <span
            className={`px-2.5 py-1 rounded text-xs font-bold uppercase ${
              bulletin.status === "approved"
                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                : "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
            }`}
          >
            Statut : {bulletin.status}
          </span>
        </div>

        {/* Narrative / Content section */}
        <div className="prose dark:prose-invert max-w-none text-sm leading-relaxed space-y-4">
          <h3 className="text-base font-bold text-foreground">1. Synthèse exécutive</h3>
          <p className="text-muted-foreground">
            Au cours de la semaine écoulée, les approvisionnements en riz local (makalioka et vary gasy) demeurent réguliers sur les grands marchés de consommation d&apos;Analamanga et de Vakinankaratne. Le prix médian national se maintient à un niveau stable avec une légère hausse saisonnière observée en fin de période.
          </p>

          <h3 className="text-base font-bold text-foreground">2. Faits numériques vérifiés (Zéro hallucination)</h3>
          <div className="p-4 bg-muted/40 rounded-lg border border-border space-y-2">
            <div className="text-xs font-semibold text-foreground flex items-center gap-1 mb-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Attribution et extraction déterministe des faits :</span>
            </div>
            <pre className="text-xs font-mono bg-background p-3 rounded border border-border overflow-x-auto text-foreground">
              {JSON.stringify(bulletin.facts || {}, null, 2)}
            </pre>
          </div>

          <h3 className="text-base font-bold text-foreground">3. Perspectives et météo</h3>
          <p className="text-muted-foreground">
            Les prévisions pluviométriques issues des observations satellitaires indiquent des précipitations conformes aux normales saisonnières sur les bassins rizicoles du Moyen-Ouest et du Lac Alaotra.
          </p>
        </div>
      </div>
    </div>
  );
}
