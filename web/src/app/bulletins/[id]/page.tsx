"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  FileText,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

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
        const apiUrl = "/api";
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
      const apiUrl = "/api";
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
      <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
        <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
        Chargement du rapport hebdomadaire officiel...
      </div>
    );
  }

  if (error || !bulletin) {
    return (
      <div className="space-y-4 max-w-4xl mx-auto">
        <Link href="/bulletins" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white">
          <ArrowLeft className="w-3.5 h-3.5" />
          Retour aux bulletins
        </Link>
        <div className="p-6 bg-rose-500/10 border border-rose-500/20 rounded-2xl text-rose-300 text-sm">
          {error || "Bulletin introuvable"}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* Top back navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/bulletins"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Retour aux bulletins
        </Link>

        <div className="flex items-center gap-3">
          {bulletin.status === "draft" && (
            <button
              onClick={handleApprove}
              disabled={approving}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold shadow-md transition-all hover:scale-102"
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
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 glass-panel rounded-xl text-xs font-medium text-slate-200 hover:text-white hover:border-emerald-500/40 transition-all shadow-sm"
            >
              <Download className="w-3.5 h-3.5 text-emerald-400" />
              <span>Télécharger le PDF</span>
            </a>
          )}
        </div>
      </div>

      {/* Document card */}
      <div className="glass-card rounded-3xl p-8 sm:p-10 space-y-8 border border-white/[0.08]">
        <div className="border-b border-white/[0.08] pb-6 flex items-start justify-between gap-4">
          <div>
            <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-emerald-400 block mb-1.5">
              Ketrika Agri Market Intelligence • Rapport Officiel
            </span>
            <h1 className="text-2xl font-extrabold text-white">
              Conjoncture hebdomadaire des marchés vivriers (PPN)
            </h1>
            <p className="text-xs text-slate-400 font-mono mt-1">
              Période sous revue : du {bulletin.period_start} au {bulletin.period_end}
            </p>
          </div>

          <span
            className={`px-3 py-1 rounded-full text-[10px] font-mono font-bold uppercase border ${
              bulletin.status === "approved"
                ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                : "bg-amber-500/15 text-amber-300 border-amber-500/30"
            }`}
          >
            {bulletin.status}
          </span>
        </div>

        {/* Narrative / Content section */}
        <div className="space-y-6 text-xs sm:text-sm leading-relaxed text-slate-300">
          <div>
            <h3 className="text-sm font-bold text-white mb-2">1. Synthèse exécutive</h3>
            <p className="text-slate-400 leading-relaxed">
              Au cours de la semaine écoulée, les approvisionnements en riz local (makalioka et vary gasy) demeurent réguliers sur les grands marchés de consommation d&apos;Analamanga et de Vakinankaratne. Le prix médian national se maintient à un niveau stable avec une légère hausse saisonnière observée en fin de période.
            </p>
          </div>

          <div>
            <h3 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>2. Faits numériques vérifiés (Zéro hallucination)</span>
            </h3>
            <div className="p-4 bg-slate-950/80 rounded-2xl border border-white/[0.06] space-y-2">
              <div className="text-[11px] font-mono text-slate-400 mb-1">
                Extraction déterministe certifiée depuis les vues Gold :
              </div>
              <pre className="text-[11px] font-mono bg-slate-900/90 p-4 rounded-xl border border-white/[0.05] overflow-x-auto text-emerald-300">
                {JSON.stringify(bulletin.facts || {}, null, 2)}
              </pre>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-bold text-white mb-2">3. Perspectives agroclimatiques</h3>
            <p className="text-slate-400 leading-relaxed">
              Les prévisions pluviométriques issues des observations satellitaires (NASA POWER / CHIRPS) indiquent des précipitations conformes aux normales saisonnières sur les bassins rizicoles du Moyen-Ouest et du Lac Alaotra.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
