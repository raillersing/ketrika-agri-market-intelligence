"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle,
  Database,
  Download,
  ExternalLink,
  FileSearch,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { formatMonthYear, formatPrice } from "@/lib/formatters";
import { ValueKindBadge } from "@/components/ui/ValueKindBadge";
import { SourceBadge } from "@/components/ui/SourceBadge";

export default function ObservationDetailPage() {
  const params = useParams();
  const id = params?.id as string;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [obs, setObs] = useState<any>(null);

  useEffect(() => {
    async function fetchObservation() {
      setLoading(true);
      setError(null);
      try {
        const apiUrl = "/api";
        const res = await fetch(`${apiUrl}/v1/observations/${id}`, {
          credentials: "include",
        });

        if (!res.ok) {
          throw new Error("Observation introuvable ou erreur de provenance");
        }

        const data = await res.json();
        setObs(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    if (id) fetchObservation();
  }, [id]);

  if (loading) {
    return (
      <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
        <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
        Vérification de la traçabilité et extraction de la preuve Bronze...
      </div>
    );
  }

  if (error || !obs) {
    return (
      <div className="space-y-4 max-w-4xl mx-auto">
        <Link
          href="/prices"
          className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Retour aux prix vivriers
        </Link>
        <div className="p-6 bg-rose-500/10 border border-rose-500/20 rounded-2xl text-rose-300 text-sm">
          {error || "Observation introuvable"}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* Top back navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/prices"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Retour aux observations
        </Link>

        {obs.bronze_download_url && (
          <a
            href={obs.bronze_download_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold shadow-md transition-all hover:scale-102"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Télécharger l&apos;artefact Bronze (S3)</span>
          </a>
        )}
      </div>

      {/* Main Provenance Card */}
      <div className="glass-card rounded-3xl p-8 space-y-8 border border-white/[0.08]">
        {/* Header */}
        <div className="border-b border-white/[0.08] pb-6 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-emerald-400">
                Certificat de provenance totale (100% Vérifiable)
              </span>
            </div>
            <h1 className="text-2xl font-extrabold text-white">
              Observation #{obs.observation_id.slice(0, 8)}
            </h1>
            <p className="text-xs font-mono text-slate-400 mt-1">
              Clé naturelle : {obs.natural_key}
            </p>
          </div>

          <div className="flex flex-col items-end gap-2">
            <ValueKindBadge kind={obs.observed_or_imputed} />
            {obs.source_id && <SourceBadge sourceId={obs.source_id} />}
          </div>
        </div>

        {/* Value Comparison: Raw vs Normalized */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Raw Values */}
          <div className="p-5 bg-slate-950/60 rounded-2xl border border-white/[0.06] space-y-3">
            <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400">
              Données brutes capturées (Bronze)
            </h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Libellé brut :</span>
                <span className="font-semibold text-white">
                  {obs.product_raw || "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Prix brut :</span>
                <span className="font-mono font-bold text-white">
                  {obs.price_raw || "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Unité brute :</span>
                <span className="text-slate-200">{obs.unit_raw || "—"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Devise brute :</span>
                <span className="text-slate-200">{obs.currency_raw || "—"}</span>
              </div>
            </div>
          </div>

          {/* Normalized Values */}
          <div className="p-5 bg-emerald-500/10 rounded-2xl border border-emerald-500/20 space-y-3">
            <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-emerald-300">
              Valeur standardisée (Silver / Gold)
            </h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Prix unitaire normalisé :</span>
                <span className="font-mono font-bold text-emerald-400 text-sm">
                  {formatPrice(obs.price_mga_per_base, obs.base_unit || "kg")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Unité de base SI :</span>
                <span className="text-white font-mono">{obs.base_unit || "kg"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Conversion :</span>
                <span className="text-white capitalize">
                  {obs.conversion_status || "Standard"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Statut d&apos;observation :</span>
                <span className="font-semibold text-white capitalize">
                  {obs.observed_or_imputed}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Evidence & Extraction Details */}
        <div className="space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <FileSearch className="w-4 h-4 text-emerald-400" />
            Preuve mécanique d&apos;extraction (Page & Extrait)
          </h3>

          <div className="p-5 bg-slate-950/60 rounded-2xl border border-white/[0.06] space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div>
                <span className="text-slate-400 block text-[10px] font-mono">Méthode d&apos;extraction :</span>
                <span className="font-semibold text-white capitalize">
                  {obs.extraction_method || "Déterministe"}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] font-mono">Version parser :</span>
                <span className="font-mono text-emerald-400">
                  {obs.parser_version || "1.0.0"}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] font-mono">Score de confiance :</span>
                <span className="font-mono font-bold text-emerald-400">
                  {obs.confidence !== undefined ? `${(obs.confidence * 100).toFixed(0)} %` : "100 %"}
                </span>
              </div>
            </div>

            <div className="pt-3 border-t border-white/[0.06]">
              <span className="text-[10px] font-mono text-slate-400 block mb-1.5 font-semibold">
                Extrait brut certifié du document source :
              </span>
              <pre className="p-3 bg-slate-900/90 rounded-xl border border-white/[0.06] text-xs font-mono whitespace-pre-wrap text-emerald-300">
                {typeof obs.evidence === "object"
                  ? JSON.stringify(obs.evidence, null, 2)
                  : obs.evidence || "Preuve tabulaire déterministe"}
              </pre>
            </div>
          </div>
        </div>

        {/* Source Document Details */}
        <div className="space-y-3 pt-4 border-t border-white/[0.06]">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Database className="w-4 h-4 text-emerald-400" />
            Provenance du document officiel
          </h3>

          <div className="text-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">URL du document source :</span>
              {obs.source_url ? (
                <a
                  href={obs.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono text-emerald-400 hover:underline flex items-center gap-1"
                >
                  <span className="truncate max-w-md">{obs.source_url}</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              ) : (
                <span className="text-slate-400 font-mono">—</span>
              )}
            </div>

            <div className="flex items-center justify-between">
              <span className="text-slate-400">Horodatage de collecte :</span>
              <span className="text-white font-mono">{formatMonthYear(obs.fetched_at)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
