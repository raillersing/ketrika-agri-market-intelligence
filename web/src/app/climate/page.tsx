"use client";

import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Calendar,
  CheckCircle2,
  CloudRain,
  CloudSun,
  Droplets,
  Flame,
  Info,
  Layers,
  MapPin,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Thermometer,
  TrendingDown,
  TrendingUp,
  Waves,
} from "lucide-react";
import { formatNumber } from "@/lib/formatters";
import { ValueKindBadge } from "@/components/ui/ValueKindBadge";
import { SourceBadge } from "@/components/ui/SourceBadge";

interface MarketLink {
  location_code: string;
  location_name: string;
  flow_role: string;
  proof_status: string;
  source_evidence: string;
}

interface CropCalendarEntry {
  zone_code: string;
  zone_name: string;
  crop: string;
  product_code: string;
  crop_cycle?: string | null;
  season_name: string;
  crop_regime: string;
  calendar_version: string;
  calendar_type: string;
  campaign: string;
  variety?: string | null;
  current_phenological_stage?: string | null;
  planting_months: number[];
  harvest_months: number[];
  peak_harvest_month?: number | null;
  water_sensitivity_profile: Record<string, string>;
  market_links: MarketLink[];
  source_reference: string;
  verified: boolean;
  eligible_for_alerts: boolean;
}

interface ClimateEvent {
  event_id: string;
  source_id: string;
  location_pcode: string;
  location_name: string;
  event_type: string;
  severity: string;
  title: string;
  description: string;
  published_at: string;
  is_projected: boolean;
  ipc_phase?: number | null;
  source_reference: string;
}

interface FacultativeSource {
  source_id: string;
  source_name: string;
  status: string;
  reason: string;
  data_available: boolean;
}

interface ClimateSummary {
  location_pcode: string;
  location_name: string;
  current_month: string;
  observed_precipitation_mm?: number | null;
  precipitation_anomaly_pct?: number | null;
  precipitation_risk_level?: string | null;
  aggregation_method: string;
  cropland_mask_applied: boolean;
  observed_source: string | null;
  temperature_mean_c?: number | null;
  forecast_next_72h_precip_mm?: number | null;
  forecast_p10_mm?: number | null;
  forecast_p90_mm?: number | null;
  forecast_model?: string | null;
  forecast_issued_at?: string | null;
  forecast_value_kind: string;
  active_crop_cycles: CropCalendarEntry[];
  events_and_outlooks: ClimateEvent[];
  facultative_sources: FacultativeSource[];
}

export default function ClimatePage() {
  const [regions, setRegions] = useState<{ pcode: string; name: string }[]>([]);
  const [selectedPcode, setSelectedPcode] = useState("MDG11");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<ClimateSummary | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/locations?level=1", { signal: controller.signal })
      .then(async (response) => { if (!response.ok) throw new Error("Référentiel indisponible"); return response.json(); })
      .then((data) => { if (!controller.signal.aborted) setRegions(data.filter((r: { pcode: string | null }) => r.pcode)); })
      .catch(() => { /* Keep the selected code visible; do not invent its name. */ });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    async function fetchClimateData() {
      setLoading(true);
      setError(null);
      setSummary(null);
      try {
        const apiUrl = "/api";
        const res = await fetch(`${apiUrl}/v1/climate/summary?location=${selectedPcode}`, {
          credentials: "include",
          signal: controller.signal,
        });

        if (!res.ok) {
          throw new Error(`Erreur API: ${res.statusText}`);
        }

        const data: ClimateSummary = await res.json();
        if (!controller.signal.aborted) setSummary(data);
      } catch (err: any) {
        if (!controller.signal.aborted) setError(err.message || "Erreur de chargement des données agroclimatiques");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    fetchClimateData();
    return () => controller.abort();
  }, [selectedPcode]);

  const getRiskBadge = (level?: string | null) => {
    switch (level) {
      case "critical":
        return <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-300 border border-rose-500/30">Sécheresse / Alerte Critique</span>;
      case "high":
        return <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">Déficit Pluviométrique Élevé</span>;
      case "medium":
        return <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-yellow-500/15 text-yellow-300 border border-yellow-500/30">Anomalie Modérée</span>;
      case "low":
        return <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">Conditions Hydriques Normales</span>;
      default:
        return <span className="px-2.5 py-1 rounded-full text-xs text-slate-300 bg-slate-800">Risque non évalué</span>;
    }
  };

  const getStageBadge = (stage?: string | null) => {
    switch (stage) {
      case "peak_harvest":
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">🌾 Pic de récolte</span>;
      case "harvest":
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">Récolte en cours</span>;
      case "planting":
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/30">Semis / Pépinière</span>;
      case "growing":
        return <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Tallage & Croissance</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[11px] text-slate-400 bg-slate-800">Intersaison / Repos</span>;
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header & Basin Selector */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-extrabold tracking-tight text-white flex items-center gap-2.5">
              <CloudSun className="w-6 h-6 text-sky-400" />
              Observatoire Agroclimatique & Calendriers Culturaux
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-sky-500/10 text-sky-300 border border-sky-500/20">
              Données disponibles et limites
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Observations et projections disponibles, avec leurs dates et limites. Les références saisonnières ne constituent pas des prévisions de récolte validées.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <select
              value={selectedPcode}
              onChange={(e) => setSelectedPcode(e.target.value)}
              className="bg-slate-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
            >
              {!regions.some((r) => r.pcode === selectedPcode) && <option value={selectedPcode}>{selectedPcode}</option>}
              {regions.map((opt) => (
                <option key={opt.pcode} value={opt.pcode}>
                  {opt.name} ({opt.pcode})
                </option>
              ))}
            </select>
          </div>
          {summary?.observed_source && <span className="text-xs text-slate-400">Sources observées : {summary.observed_source}</span>}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="glass-card rounded-2xl p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
          <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
          Chargement de l&apos;observatoire agroclimatique explicable...
        </div>
      ) : !summary || error ? <p className="text-slate-400">Synthèse indisponible pour cette zone.</p> : (
        <>
          {/* Top KPI Cards: Observed vs Forecast */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {/* Card 1: Observed Rainfall & Anomaly */}
            <div className="glass-card rounded-2xl p-5 border border-white/[0.08] relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <CloudRain className="w-4 h-4 text-sky-400" />
                  Précipitations Observées
                </span>
                <ValueKindBadge kind="observed" />
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-white font-mono">
                  {summary.observed_precipitation_mm !== null && summary.observed_precipitation_mm !== undefined
                    ? formatNumber(summary.observed_precipitation_mm, 1)
                    : "—"}
                </span>
                <span className="text-sm font-semibold text-slate-400">mm / mois</span>
              </div>
              <div className="mt-3 flex items-center justify-between text-xs border-t border-white/[0.06] pt-3">
                <span className="text-slate-400">Écart à l’historique disponible :</span>
                <span
                  className={`font-mono font-bold ${
                    (summary.precipitation_anomaly_pct ?? 0) < 0
                      ? "text-rose-400"
                      : (summary.precipitation_anomaly_pct ?? 0) > 0
                      ? "text-sky-400"
                      : "text-emerald-400"
                  }`}
                >
                  {summary.precipitation_anomaly_pct !== null && summary.precipitation_anomaly_pct !== undefined
                    ? `${formatNumber(summary.precipitation_anomaly_pct, 1)}%`
                    : "Baseline insuffisante"}
                </span>
              </div>
              <div className="mt-2 text-[11px] text-slate-500 flex items-center gap-1 font-mono">
                <Info className="w-3 h-3 text-slate-400" />
                <span>Méthode : {summary.aggregation_method}</span>
              </div>
            </div>

            {/* Card 2: NWP Forecast (ECMWF Open Data) */}
            <div className="glass-card rounded-2xl p-5 border border-sky-500/20 bg-sky-950/20 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-sky-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Droplets className="w-4 h-4 text-sky-400" />
                  Météo prévue (fenêtre du modèle : 72h)
                </span>
                <ValueKindBadge kind="projected" />
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-white font-mono">
                  {summary.forecast_next_72h_precip_mm !== null && summary.forecast_next_72h_precip_mm !== undefined
                    ? formatNumber(summary.forecast_next_72h_precip_mm, 1)
                    : "—"}
                </span>
                <span className="text-sm font-semibold text-slate-400">mm prévus</span>
              </div>
              <div className="mt-3 flex items-center justify-between text-xs border-t border-sky-500/15 pt-3">
                <span className="text-slate-400">Incertitude p10 – p90 :</span>
                <span className="font-mono text-sky-300 font-semibold">
                  {summary.forecast_p10_mm != null && summary.forecast_p90_mm != null ? `[${formatNumber(summary.forecast_p10_mm, 1)} – ${formatNumber(summary.forecast_p90_mm, 1)}] mm` : "Indisponible"}
                </span>
              </div>
              <div className="mt-2 text-[11px] text-slate-400 flex items-center justify-between font-mono">
                <span>Modèle : {summary.forecast_model || "Indisponible"}</span>
                <span>Émis le : {summary.forecast_issued_at ? summary.forecast_issued_at.slice(0, 10) : "Indisponible"}</span>
              </div>
            </div>

            {/* Card 3: Agroclimatic Risk Assessment */}
            <div className="glass-card rounded-2xl p-5 border border-white/[0.08] relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4 text-amber-400" />
                  Diagnostic de Risque Hydrique
                </span>
                <span className="text-[10px] font-mono text-slate-500">Mois {summary.current_month.slice(0, 7)}</span>
              </div>
              <div className="mt-3">
                {getRiskBadge(summary.precipitation_risk_level)}
              </div>
              <p className="mt-3 text-xs text-slate-400 leading-relaxed">
                Comparaison à l’historique disponible ; la référence climatologique et son effectif restent à qualifier.
              </p>
              <div className="mt-2 text-[11px] text-slate-500 font-mono">
                Température moyenne observée : {summary.temperature_mean_c != null ? `${formatNumber(summary.temperature_mean_c, 1)} °C` : "—"}
              </div>
            </div>
          </div>

          {/* Crop Calendars & Corridors Section */}
          <div className="glass-card rounded-2xl overflow-hidden border border-white/[0.08]">
            <div className="p-4 border-b border-white/[0.07] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-emerald-400" />
                <h2 className="text-sm font-bold text-white">
                  Calendriers culturaux du bassin & Corridors commerciaux documentés
                </h2>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                Source : MinAE, ODR & FAO GIEWS (ADR-086)
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-950/60 text-slate-400 border-b border-white/[0.06] uppercase font-mono text-[10px] tracking-wider">
                  <tr>
                    <th className="px-4 py-3">Culture / Cycle</th>
                    <th className="px-4 py-3">Typologie</th>
                    <th className="px-4 py-3">Stade Actuel</th>
                    <th className="px-4 py-3">Semis</th>
                    <th className="px-4 py-3">Récolte</th>
                    <th className="px-4 py-3">Marchés Récepteurs Documentés</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {summary.active_crop_cycles.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                        Aucun calendrier cultural actif enregistré pour ce bassin.
                      </td>
                    </tr>
                  ) : (
                    summary.active_crop_cycles.map((c, idx) => (
                      <tr key={`${c.zone_code}-${c.product_code}-${idx}`} className="hover:bg-white/[0.02] transition-colors">
                        <td className="px-4 py-3">
                          <div className="font-semibold text-white">{c.crop} ({c.season_name})</div>
                          <div className="text-[11px] text-slate-400">{c.variety || c.product_code}</div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-mono ${
                            c.calendar_type === "seasonal_recommendation"
                              ? "bg-purple-500/15 text-purple-300 border border-purple-500/30"
                              : "bg-slate-800 text-slate-300 border border-white/[0.06]"
                          }`}>
                            {c.calendar_type === "seasonal_recommendation" ? `Avis ${c.campaign}` : "Baseline"}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {getStageBadge(c.current_phenological_stage)}
                        </td>
                        <td className="px-4 py-3 text-slate-300 font-mono text-[11px]">
                          Mois {c.planting_months.join(", ")}
                        </td>
                        <td className="px-4 py-3 text-emerald-400 font-mono font-semibold text-[11px]">
                          Mois {c.harvest_months.join(", ")}
                        </td>
                        <td className="px-4 py-3">
                          {c.market_links.length > 0 ? (
                            <div className="flex flex-wrap gap-1.5">
                              {c.market_links.map((link, lIdx) => (
                                <span
                                  key={lIdx}
                                  title={`${link.source_evidence} (${link.proof_status})`}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-950/40 text-emerald-300 border border-emerald-500/20 cursor-help"
                                >
                                  <ArrowRight className="w-2.5 h-2.5" />
                                  {link.location_name}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-500 font-mono text-[11px]">Aucun corridor renseigné</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Environmental Sources Transparency & FEWS NET / IPC Events */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Left: Food Security Outlooks & Events */}
            <div className="glass-card rounded-2xl p-5 border border-white/[0.08]">
              <div className="flex items-center gap-2 border-b border-white/[0.06] pb-3">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-bold text-white">Alertes & Perspectives de Sécurité Alimentaire</h3>
              </div>
              <div className="mt-4 space-y-3">
                {summary.events_and_outlooks.length === 0 ? (
                  <div className="text-xs text-slate-400 py-6 text-center">
                    Aucun événement critique FEWS NET / IPC répertorié sur cette zone.
                  </div>
                ) : (
                  summary.events_and_outlooks.map((ev) => (
                    <div key={ev.event_id} className="p-3 rounded-xl bg-slate-900/60 border border-white/[0.05] space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-white">{ev.title}</span>
                        {ev.is_projected && <ValueKindBadge kind="projected" />}
                      </div>
                      <p className="text-xs text-slate-300">{ev.description}</p>
                      <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono pt-1">
                        <span>Source : {ev.source_reference}</span>
                        {ev.ipc_phase && (
                          <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold">
                            Phase IPC {ev.ipc_phase}
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Right: Transparent Status on Facultative Sources */}
            <div className="glass-card rounded-2xl p-5 border border-white/[0.08]">
              <div className="flex items-center gap-2 border-b border-white/[0.06] pb-3">
                <Info className="w-4 h-4 text-sky-400" />
                <h3 className="text-sm font-bold text-white">Transparence des Sources Facultatives (R4.8–R4.10)</h3>
              </div>
              <p className="text-xs text-slate-400 mt-3 leading-relaxed">
                Conformément à la règle d&apos;intégrité métrologique (ADR-087), les sources environnementales optionnelles non configurées sont formellement signalées comme indisponibles. Aucun faux chiffre zéro n&apos;est inséré et aucun indice composite fabriqué n&apos;est calculé.
              </p>
              <div className="mt-4 space-y-2.5">
                {summary.facultative_sources.map((src) => (
                  <div key={src.source_id} className="p-3 rounded-xl bg-slate-900/40 border border-white/[0.04] flex items-start justify-between gap-3">
                    <div>
                      <div className="text-xs font-semibold text-slate-300">{src.source_name}</div>
                      <div className="text-[11px] text-slate-400 mt-0.5">{src.reason}</div>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-400 border border-white/[0.06] whitespace-nowrap">
                      Indisponible
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
