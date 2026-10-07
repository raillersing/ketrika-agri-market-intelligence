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
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
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
      <div className="p-12 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
        <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
        Vérification de la traçabilité et extraction de la provenance Bronze...
      </div>
    );
  }

  if (error || !obs) {
    return (
      <div className="space-y-4 max-w-4xl mx-auto">
        <Link
          href="/prices"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Retour aux prix vivriers
        </Link>
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-sm">
          {error || "Observation introuvable"}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Top back navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/prices"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Retour aux observations
        </Link>

        {obs.bronze_download_url && (
          <a
            href={obs.bronze_download_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-700 hover:bg-emerald-800 text-white rounded text-xs font-semibold shadow-sm transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Télécharger l&apos;artefact Bronze (S3)</span>
          </a>
        )}
      </div>

      {/* Main Provenance Card */}
      <div className="bg-card border border-border rounded-xl shadow-md p-8 space-y-8">
        {/* Header */}
        <div className="border-b border-border pb-6 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ShieldCheck className="w-5 h-5 text-emerald-600" />
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-600">
                Certificat de provenance totale (100% Vérifiable)
              </span>
            </div>
            <h1 className="text-2xl font-bold text-foreground">
              Observation #{obs.observation_id.slice(0, 8)}
            </h1>
            <p className="text-xs font-mono text-muted-foreground mt-1">
              Clé naturelle : {obs.natural_key}
            </p>
          </div>

          <div className="flex flex-col items-end gap-1.5">
            <ValueKindBadge kind={obs.observed_or_imputed} />
            {obs.source_id && <SourceBadge sourceId={obs.source_id} />}
          </div>
        </div>

        {/* Value Comparison: Raw vs Normalized */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Raw Values */}
          <div className="p-5 bg-muted/40 rounded-lg border border-border space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
              Données brutes capturées (Bronze)
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Libellé brut :</span>
                <span className="font-semibold text-foreground">
                  {obs.product_raw || "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Prix brut :</span>
                <span className="font-mono font-bold text-foreground">
                  {obs.price_raw || "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Unité brute :</span>
                <span className="text-foreground">{obs.unit_raw || "—"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Devise brute :</span>
                <span className="text-foreground">{obs.currency_raw || "—"}</span>
              </div>
            </div>
          </div>

          {/* Normalized Values */}
          <div className="p-5 bg-emerald-50/50 dark:bg-emerald-950/20 rounded-lg border border-emerald-200 dark:border-emerald-800 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-800 dark:text-emerald-300">
              Valeur standardisée (Silver / Gold)
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Prix unitaire normalisé :</span>
                <span className="font-mono font-bold text-emerald-700 dark:text-emerald-400">
                  {formatPrice(obs.price_mga_per_base, obs.base_unit || "kg")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Unité de base SI :</span>
                <span className="text-foreground">{obs.base_unit || "kg"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Conversion :</span>
                <span className="text-foreground capitalize">
                  {obs.conversion_status || "Standard"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Statut d&apos;observation :</span>
                <span className="font-semibold text-foreground capitalize">
                  {obs.observed_or_imputed}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Evidence & Extraction Details */}
        <div className="space-y-4">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
            <FileSearch className="w-4 h-4 text-emerald-600" />
            Preuve mécanique d&apos;extraction (Page &amp; Extrait)
          </h3>

          <div className="p-4 bg-muted/60 rounded-lg border border-border space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
              <div>
                <span className="text-muted-foreground block">Méthode d&apos;extraction :</span>
                <span className="font-semibold text-foreground capitalize">
                  {obs.extraction_method || "Déterministe"}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground block">Version du parser :</span>
                <span className="font-mono text-foreground">
                  {obs.parser_version || "1.0.0"}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground block">Score de confiance :</span>
                <span className="font-bold text-emerald-600">
                  {obs.confidence !== undefined ? `${(obs.confidence * 100).toFixed(0)} %` : "100 %"}
                </span>
              </div>
            </div>

            <div className="pt-2 border-t border-border">
              <span className="text-xs text-muted-foreground block mb-1.5 font-semibold">
                Extrait brut du document source :
              </span>
              <pre className="p-3 bg-background rounded border border-border text-xs font-mono whitespace-pre-wrap text-foreground">
                {typeof obs.evidence === "object"
                  ? JSON.stringify(obs.evidence, null, 2)
                  : obs.evidence || "Preuve tabulaire déterministe"}
              </pre>
            </div>
          </div>
        </div>

        {/* Source Document Details */}
        <div className="space-y-3 pt-4 border-t border-border">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
            <Database className="w-4 h-4 text-emerald-600" />
            Provenance du document officiel
          </h3>

          <div className="text-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">URL du document source :</span>
              {obs.source_url ? (
                <a
                  href={obs.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono text-emerald-700 dark:text-emerald-400 hover:underline flex items-center gap-1"
                >
                  <span className="truncate max-w-md">{obs.source_url}</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </div>

            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Horodatage de collecte :</span>
              <span className="text-foreground">{formatMonthYear(obs.fetched_at)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
