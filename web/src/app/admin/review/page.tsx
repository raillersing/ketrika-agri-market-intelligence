"use client";

import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle,
  CheckSquare,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { formatMonthYear } from "@/lib/formatters";

interface ReviewItem {
  reviewId: string;
  kind: string;
  payload: Record<string, any>;
  status: "open" | "approved" | "rejected";
  createdAt: string;
}

export default function AdminReviewPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [actionLoading, setActionLoading] = useState(false);

  async function fetchReviews() {
    setLoading(true);
    setError(null);
    try {
      const apiUrl = "/api";
      const res = await fetch(`${apiUrl}/v1/admin/review`, {
        credentials: "include",
      });

      if (!res.ok) {
        if (res.status === 403 || res.status === 401) {
          throw new Error("Accès restreint : privilèges analyste/admin requis");
        }
        throw new Error(`Erreur API: ${res.statusText}`);
      }

      const data = await res.json();
      const reviewRows: ReviewItem[] = data.map((r: any) => ({
        reviewId: r.review_id,
        kind: r.kind,
        payload: r.payload || {},
        status: r.status,
        createdAt: r.created_at,
      }));
      setItems(reviewRows);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchReviews();
  }, []);

  const handleResolve = async (reviewId: string, resolutionStatus: "approved" | "rejected") => {
    setActionLoading(true);
    try {
      const apiUrl = "/api";
      const res = await fetch(`${apiUrl}/v1/admin/review/${reviewId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          status: resolutionStatus,
          resolution_note: `Résolu par l'analyste (${resolutionStatus})`,
        }),
      });

      if (!res.ok) {
        throw new Error("Échec de la résolution");
      }

      setItems((prev) =>
        prev.map((it) => (it.reviewId === reviewId ? { ...it, status: resolutionStatus } : it))
      );
    } catch (err: any) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight text-white flex items-center gap-2.5">
              <CheckSquare className="w-6 h-6 text-purple-400" />
              File de revue & Arbitrage humain
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-purple-500/10 text-purple-300 border border-purple-500/20">
              Gate H5
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Arbitrage des toponymes, alias de variétés à confiance modérée et valeurs aberrantes (Human-in-the-Loop).
          </p>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 glass-panel rounded-xl text-xs font-mono text-emerald-400">
          <ShieldCheck className="w-4 h-4" />
          <span>Qualité Gold certifiée</span>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Review items table */}
      <div className="glass-card rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-white/[0.07] flex items-center justify-between">
          <h2 className="text-sm font-bold text-white">
            Éléments en attente d&apos;arbitrage ({items.length})
          </h2>
          <button
            onClick={fetchReviews}
            className="text-xs text-slate-400 hover:text-white flex items-center gap-1.5 transition-colors font-mono"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-purple-400" : ""}`} />
            Actualiser
          </button>
        </div>

        {loading ? (
          <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
            <RefreshCw className="w-4 h-4 animate-spin text-purple-400" />
            Chargement des anomalies...
          </div>
        ) : items.length === 0 ? (
          <div className="p-16 text-center text-xs text-slate-400 font-mono space-y-1">
            <div className="text-emerald-400 font-bold">File de revue vide</div>
            <div>Toutes les observations sont conformes avec une confiance &ge; 0,90.</div>
          </div>
        ) : (
          <div className="divide-y divide-white/[0.04]">
            {items.map((it) => (
              <div key={it.reviewId} className="p-5 flex flex-col md:flex-row md:items-start justify-between gap-4 hover:bg-white/[0.02] transition-colors">
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs px-2.5 py-0.5 rounded-full bg-purple-500/15 text-purple-300 border border-purple-500/25 font-bold">
                      {it.kind}
                    </span>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full uppercase font-bold border ${
                        it.status === "approved"
                          ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/25"
                          : it.status === "rejected"
                          ? "bg-rose-500/15 text-rose-300 border-rose-500/25"
                          : "bg-amber-500/15 text-amber-300 border-amber-500/25"
                      }`}
                    >
                      {it.status}
                    </span>
                    <span className="text-[11px] font-mono text-slate-400">
                      ID : {it.reviewId.slice(0, 8)}...
                    </span>
                  </div>

                  <pre className="p-3 bg-slate-950/80 border border-white/[0.06] rounded-xl font-mono text-[11px] text-emerald-300 overflow-x-auto">
                    {JSON.stringify(it.payload, null, 2)}
                  </pre>

                  <p className="text-[10px] text-slate-400 font-mono">
                    Soumis le {formatMonthYear(it.createdAt)}
                  </p>
                </div>

                {it.status === "open" && (
                  <div className="flex items-center gap-2 self-start">
                    <button
                      onClick={() => handleResolve(it.reviewId, "approved")}
                      disabled={actionLoading}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold shadow-md transition-all hover:scale-102"
                    >
                      <CheckCircle className="w-3.5 h-3.5" />
                      <span>Valider</span>
                    </button>
                    <button
                      onClick={() => handleResolve(it.reviewId, "rejected")}
                      disabled={actionLoading}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-600/80 hover:bg-rose-600 text-white rounded-xl text-xs font-semibold shadow-md transition-all hover:scale-102"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Rejeter</span>
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
