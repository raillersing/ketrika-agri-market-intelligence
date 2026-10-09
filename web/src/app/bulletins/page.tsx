"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2, Clock, FileText, RefreshCw, ShieldCheck } from "lucide-react";
import { formatMonthYear } from "@/lib/formatters";

interface BulletinItem {
  bulletinId: string;
  periodStart: string;
  periodEnd: string;
  status: "draft" | "approved" | "sent";
  createdAt: string;
  factsCount?: number;
}

export default function BulletinsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [bulletins, setBulletins] = useState<BulletinItem[]>([]);

  useEffect(() => {
    async function fetchBulletins() {
      setLoading(true);
      setError(null);
      try {
        const apiUrl = "/api";
        const res = await fetch(`${apiUrl}/v1/bulletins`, {
          credentials: "include",
        });

        if (!res.ok) {
          throw new Error(`Erreur API: ${res.statusText}`);
        }

        const data = await res.json();
        const items: BulletinItem[] = data.map((b: any) => ({
          bulletinId: b.bulletin_id,
          periodStart: b.period_start,
          periodEnd: b.period_end,
          status: b.status,
          createdAt: b.created_at,
          factsCount: Object.keys(b.facts || {}).length,
        }));
        setBulletins(items);
      } catch (err: any) {
        setError(err.message || "Erreur de chargement des bulletins hebdomadaires");
      } finally {
        setLoading(false);
      }
    }

    fetchBulletins();
  }, []);

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight text-white flex items-center gap-2.5">
              <FileText className="w-6 h-6 text-emerald-400" />
              Bulletins hebdomadaires PPN
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
              Certifié SPECS §20
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Rapports officiels de conjoncture des marchés vivriers • Audit mécanique 100% des chiffres.
          </p>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 glass-panel rounded-xl text-xs font-mono text-emerald-400">
          <ShieldCheck className="w-4 h-4" />
          <span>Audit-proof</span>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs">
          {error}
        </div>
      )}

      {/* Bulletins Table */}
      <div className="glass-card rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-white/[0.07] flex items-center justify-between">
          <h2 className="text-sm font-bold text-white">
            Éditions publiées & Rapports disponibles
          </h2>
          <span className="text-[11px] font-mono text-slate-400">
            {bulletins.length} éditions
          </span>
        </div>

        {loading ? (
          <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
            <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
            Chargement des bulletins...
          </div>
        ) : bulletins.length === 0 ? (
          <div className="p-16 text-center text-xs text-slate-400 font-mono">
            Aucun bulletin généré pour le moment.
          </div>
        ) : (
          <div className="divide-y divide-white/[0.04]">
            {bulletins.map((b) => (
              <div
                key={b.bulletinId}
                className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-white/[0.02] transition-colors"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-sm text-white">
                      Bulletin hebdomadaire PPN — Semaine du {b.periodStart} au {b.periodEnd}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase border ${
                        b.status === "approved"
                          ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                          : b.status === "sent"
                          ? "bg-sky-500/15 text-sky-300 border-sky-500/30"
                          : "bg-amber-500/15 text-amber-300 border-amber-500/30"
                      }`}
                    >
                      {b.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 font-mono">
                    Généré le {formatMonthYear(b.createdAt)} • {b.factsCount || 0} faits chiffrés vérifiés
                  </p>
                </div>

                <Link
                  href={`/bulletins/${b.bulletinId}`}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-950/40 transition-all hover:scale-102 self-start sm:self-auto"
                >
                  <span>Lire le bulletin</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
