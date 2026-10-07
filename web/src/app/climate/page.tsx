"use client";

import React, { useEffect, useState } from "react";
import { CloudSun, Droplets, Calendar, RefreshCw } from "lucide-react";
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
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
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
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <CloudSun className="w-6 h-6 text-emerald-600" />
          Climat, anomalies pluviométriques et calendrier cultural
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Surveillance des précipitations, détection du stress hydrique et stades végétatifs des cultures PPN.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-md text-rose-700 text-xs">
          {error}
        </div>
      )}

      {/* Crop Calendar Section */}
      <div className="bg-card border border-border rounded-lg overflow-hidden shadow-sm">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-emerald-600" />
            <h2 className="text-sm font-semibold text-foreground">
              Calendrier cultural de référence (Madagascar)
            </h2>
          </div>
          <span className="text-xs text-muted-foreground">
            Sources : FAO GIEWS &amp; FEWS NET
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-muted/50 text-muted-foreground border-b border-border uppercase font-semibold">
              <tr>
                <th className="px-4 py-3">Culture / Cycle</th>
                <th className="px-4 py-3">Bassins de production</th>
                <th className="px-4 py-3">Semis / Pépinière</th>
                <th className="px-4 py-3">Repiquage</th>
                <th className="px-4 py-3">Récolte principale</th>
                <th className="px-4 py-3">Régime cultural</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {CROP_CALENDAR.map((c) => (
                <tr key={c.culture} className="hover:bg-muted/30">
                  <td className="px-4 py-3 font-semibold text-foreground">
                    {c.culture}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{c.zones}</td>
                  <td className="px-4 py-3 text-foreground">{c.semis}</td>
                  <td className="px-4 py-3 text-foreground">{c.repiquage}</td>
                  <td className="px-4 py-3 font-medium text-emerald-700 dark:text-emerald-400">
                    {c.recolte}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
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
      <div className="bg-card border border-border rounded-lg overflow-hidden shadow-sm">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Droplets className="w-4 h-4 text-emerald-600" />
            <h2 className="text-sm font-semibold text-foreground">
              Anomalies pluviométriques mensuelles par région
            </h2>
          </div>
          <SourceBadge sourceId="nasa_power_mdg" />
        </div>

        {loading ? (
          <div className="p-12 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
            Chargement des données agroclimatiques...
          </div>
        ) : anomalies.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            Aucune anomalie pluviométrique disponible pour cette période.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/50 text-muted-foreground border-b border-border uppercase font-semibold">
                <tr>
                  <th className="px-4 py-3">Région</th>
                  <th className="px-4 py-3">Période</th>
                  <th className="px-4 py-3">Pluie totale (mm)</th>
                  <th className="px-4 py-3">Écart à la normale (mm)</th>
                  <th className="px-4 py-3">Z-Score climatique</th>
                  <th className="px-4 py-3">Nature</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {anomalies.map((a, idx) => (
                  <tr key={`${a.locationPcode}-${idx}`} className="hover:bg-muted/30">
                    <td className="px-4 py-2.5 font-semibold text-foreground">
                      {a.locationName}
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {a.periodMonth}
                    </td>
                    <td className="px-4 py-2.5 font-bold text-foreground">
                      {formatNumber(a.precipTotalMm, 1)} mm
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`font-semibold ${
                          a.anomalyMm < -20
                            ? "text-rose-600"
                            : a.anomalyMm > 20
                            ? "text-blue-600"
                            : "text-muted-foreground"
                        }`}
                      >
                        {a.anomalyMm > 0 ? `+${formatNumber(a.anomalyMm, 1)}` : formatNumber(a.anomalyMm, 1)} mm
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-muted-foreground">
                      {a.zScore !== null && a.zScore !== undefined
                        ? formatNumber(a.zScore, 2)
                        : "—"}
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
