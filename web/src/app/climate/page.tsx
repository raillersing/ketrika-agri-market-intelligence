"use client";

import React, { useEffect, useState } from "react";
import {
  Calendar,
  CloudRain,
  CloudSun,
  Droplets,
  Layers,
  RefreshCw,
  Sun,
  Thermometer,
} from "lucide-react";
import { formatNumber } from "@/lib/formatters";
import { ValueKindBadge } from "@/components/ui/ValueKindBadge";
import { SourceBadge } from "@/components/ui/SourceBadge";

interface WeatherAnomaly {
  locationPcode: string;
  locationName: string;
  periodMonth: string;
  precipTotalMm: number;
  anomalyMm: number;
  zScore?: number | null;
  valueKind: string;
  sources: string[];
}

const CROP_CALENDAR = [
  {
    culture: "Riz Vakiambiaty (Grande saison)",
    zones: "Hautes Terres (Analamanga, Vakinankaratne, Itasy)",
    semis: "Octobre – Décembre",
    repiquage: "Décembre – Janvier",
    recolte: "Avril – Juin",
    statut: "Saison principale",
  },
  {
    culture: "Riz Hosy (Saison précoce)",
    zones: "Alaotra-Mangoro, Marovoay, Boeny",
    semis: "Juin – Août",
    repiquage: "Août – Septembre",
    recolte: "Novembre – Janvier",
    statut: "Riz de contre-saison irrigué",
  },
  {
    culture: "Riz Asara (Saison des pluies)",
    zones: "Côte Est & Ouest (Atsinanana, Menabe, Sofia)",
    semis: "Novembre – Décembre",
    repiquage: "Janvier",
    recolte: "Mars – Mai",
    statut: "Pluvial et bas-fonds",
  },
  {
    culture: "Maïs grain",
    zones: "Vakinankaratne, Menabe, Atsimo-Andrefana",
    semis: "Novembre – Décembre",
    repiquage: "Semis direct",
    recolte: "Mars – Mai",
    statut: "Alimentaire & provende",
  },
];

export default function ClimatePage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [anomalies, setAnomalies] = useState<WeatherAnomaly[]>([]);

  useEffect(() => {
    async function fetchWeather() {
      setLoading(true);
      setError(null);
      try {
        const apiUrl = "/api";
        const res = await fetch(`${apiUrl}/v1/weather/anomalies`, {
          credentials: "include",
        });

        if (!res.ok) {
          throw new Error(`Erreur API: ${res.statusText}`);
        }

        const data = await res.json();
        const items: WeatherAnomaly[] = data.map((item: any) => ({
          locationPcode: item.location_pcode,
          locationName: item.location_name,
          periodMonth: item.period_month,
          precipTotalMm: item.precip_total_mm,
          anomalyMm: item.anomaly_mm,
          zScore: item.z_score,
          valueKind: item.value_kind || "observed",
          sources: item.sources || ["nasa_power_mdg"],
        }));
        setAnomalies(items);
      } catch (err: any) {
        setError(err.message || "Erreur de chargement des données climatiques");
      } finally {
        setLoading(false);
      }
    }

    fetchWeather();
  }, []);

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight text-white flex items-center gap-2.5">
              <CloudSun className="w-6 h-6 text-sky-400" />
              Agroclimatologie & Suivi des cultures
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-sky-500/10 text-sky-300 border border-sky-500/20">
              NASA POWER & CHIRPS
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Détection précoce du stress hydrique, précipitations décadaires et calendrier cultural des PPN à Madagascar.
          </p>
        </div>

        <SourceBadge sourceId="nasa_power_mdg" />
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs">
          {error}
        </div>
      )}

      {/* Crop Calendar Section */}
      <div className="glass-card rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-white/[0.07] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-emerald-400" />
            <h2 className="text-sm font-bold text-white">
              Calendrier cultural de référence (Madagascar)
            </h2>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            Source : FAO GIEWS & FEWS NET
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-slate-950/60 text-slate-400 border-b border-white/[0.06] uppercase font-mono text-[10px] tracking-wider">
              <tr>
                <th className="px-4 py-3">Culture / Variété</th>
                <th className="px-4 py-3">Bassins de production</th>
                <th className="px-4 py-3">Semis / Pépinière</th>
                <th className="px-4 py-3">Repiquage</th>
                <th className="px-4 py-3">Récolte principale</th>
                <th className="px-4 py-3">Régime cultural</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {CROP_CALENDAR.map((c) => (
                <tr key={c.culture} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-4 py-3 font-semibold text-white">
                    {c.culture}
                  </td>
                  <td className="px-4 py-3 text-slate-300">{c.zones}</td>
                  <td className="px-4 py-3 text-slate-200 font-mono text-[11px]">{c.semis}</td>
                  <td className="px-4 py-3 text-slate-200 font-mono text-[11px]">{c.repiquage}</td>
                  <td className="px-4 py-3 font-semibold text-emerald-400 font-mono text-[11px]">
                    {c.recolte}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-mono bg-slate-800 text-slate-300 border border-white/[0.06]">
                      {c.statut}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Rainfall Anomalies Table */}
      <div className="glass-card rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-white/[0.07] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Droplets className="w-4 h-4 text-sky-400" />
            <h2 className="text-sm font-bold text-white">
              Anomalies pluviométriques mensuelles par région
            </h2>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            {anomalies.length} relevés régionaux
          </span>
        </div>

        {loading ? (
          <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
            <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
            Chargement des séries agroclimatiques...
          </div>
        ) : anomalies.length === 0 ? (
          <div className="p-16 text-center text-xs text-slate-400 font-mono">
            Aucune anomalie pluviométrique disponible pour cette période.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-950/60 text-slate-400 border-b border-white/[0.06] uppercase font-mono text-[10px] tracking-wider">
                <tr>
                  <th className="px-4 py-3">Région</th>
                  <th className="px-4 py-3">Période</th>
                  <th className="px-4 py-3 text-right">Cumul Pluie</th>
                  <th className="px-4 py-3 text-right">Écart Normale</th>
                  <th className="px-4 py-3 text-center">Z-Score</th>
                  <th className="px-4 py-3">Nature</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {anomalies.map((a, idx) => (
                  <tr key={`${a.locationPcode}-${idx}`} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-2.5 font-semibold text-white">
                      {a.locationName}
                    </td>
                    <td className="px-4 py-2.5 text-slate-400 font-mono text-[11px]">
                      {a.periodMonth}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono font-bold text-white">
                      {formatNumber(a.precipTotalMm, 1)} mm
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono">
                      <span
                        className={`font-semibold ${
                          a.anomalyMm < -20
                            ? "text-rose-400"
                            : a.anomalyMm > 20
                            ? "text-sky-400"
                            : "text-slate-400"
                        }`}
                      >
                        {a.anomalyMm > 0 ? `+${formatNumber(a.anomalyMm, 1)}` : formatNumber(a.anomalyMm, 1)} mm
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-center font-mono">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] ${
                          (a.zScore ?? 0) < -1.5
                            ? "bg-rose-500/15 text-rose-300 border border-rose-500/20"
                            : (a.zScore ?? 0) > 1.5
                            ? "bg-sky-500/15 text-sky-300 border border-sky-500/20"
                            : "text-slate-400"
                        }`}
                      >
                        {a.zScore !== null && a.zScore !== undefined
                          ? formatNumber(a.zScore, 2)
                          : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <ValueKindBadge kind={a.valueKind} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
