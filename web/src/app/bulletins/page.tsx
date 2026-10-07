"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { FileText, CheckCircle2, Clock, ArrowRight, RefreshCw } from "lucide-react";
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
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
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
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <FileText className="w-6 h-6 text-emerald-600" />
          Bulletins hebdomadaires de conjoncture PPN
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Rapports officiels hebdomadaires certifiés sans hallucination numérique (SPECS §20).
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-md text-rose-700 text-xs">
          {error}
        </div>
      )}

      {/* Bulletins Table */}
      <div className="bg-card border border-border rounded-lg overflow-hidden shadow-sm">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">
            Éditions publiées et en revue
          </h2>
          <span className="text-xs text-muted-foreground">
            {bulletins.length} éditions
          </span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
            Chargement des bulletins...
          </div>
        ) : bulletins.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            Aucun bulletin généré pour le moment.
          </div>
        ) : (
          <div className="divide-y divide-border">
            {bulletins.map((b) => (
              <div
                key={b.bulletinId}
                className="p-4 flex items-center justify-between hover:bg-muted/20 transition-colors"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-foreground">
                      Bulletin hebdomadaire PPN — Semaine du {b.periodStart} au {b.periodEnd}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        b.status === "approved"
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                          : b.status === "sent"
                          ? "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300"
                          : "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                      }`}
                    >
                      {b.status}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Généré le {formatMonthYear(b.createdAt)} • {b.factsCount || 0} faits vérifiés
                  </p>
                </div>

                <Link
                  href={`/bulletins/${b.bulletinId}`}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium text-emerald-700 hover:text-emerald-900 hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-950 transition-colors"
                >
                  <span>Consulter le rapport</span>
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
