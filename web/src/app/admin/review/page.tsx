"use client";

import React, { useEffect, useState } from "react";
import { CheckSquare, CheckCircle, XCircle, RefreshCw, AlertCircle } from "lucide-react";
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
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
      const res = await fetch(`${apiUrl}/v1/admin/review`, {
        credentials: "include",
      });

      if (!res.ok) {
        if (res.status === 403 || res.status === 401) {
          throw new Error("Accès refusé : rôle administrateur requis");
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
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
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
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <CheckSquare className="w-6 h-6 text-emerald-600" />
          File de revue des anomalies et alias non reconnus
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Espace d&apos;arbitrage et de validation humaine pour les toponymes, variétés et valeurs aberrantes.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-md text-rose-700 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Review items table */}
      <div className="bg-card border border-border rounded-lg overflow-hidden shadow-sm">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">
            Éléments en attente d&apos;arbitrage ({items.length})
          </h2>
          <button
            onClick={fetchReviews}
            className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Actualiser
          </button>
        </div>

        {loading ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            Chargement des éléments de la file de revue...
          </div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            Aucun élément en attente de revue. La base de données est 100% conforme.
          </div>
        ) : (
          <div className="divide-y divide-border">
            {items.map((it) => (
              <div key={it.reviewId} className="p-4 flex items-start justify-between gap-4">
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs px-2 py-0.5 rounded bg-muted font-bold text-foreground">
                      {it.kind}
                    </span>
                    <span
                      className={`text-[11px] px-2 py-0.5 rounded uppercase font-semibold ${
                        it.status === "approved"
                          ? "bg-emerald-100 text-emerald-800"
                          : it.status === "rejected"
                          ? "bg-rose-100 text-rose-800"
                          : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {it.status}
                    </span>
                  </div>

                  <div className="p-2.5 bg-muted/40 rounded border border-border font-mono text-xs text-foreground">
                    {JSON.stringify(it.payload)}
                  </div>

                  <p className="text-[11px] text-muted-foreground">
                    Créé le {formatMonthYear(it.createdAt)}
                  </p>
                </div>

                {it.status === "open" && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleResolve(it.reviewId, "approved")}
                      disabled={actionLoading}
                      className="inline-flex items-center gap-1 px-3 py-1.5 bg-emerald-700 hover:bg-emerald-800 text-white rounded text-xs font-medium shadow-sm transition-colors"
                    >
                      <CheckCircle className="w-3.5 h-3.5" />
                      <span>Approuver</span>
                    </button>
                    <button
                      onClick={() => handleResolve(it.reviewId, "rejected")}
                      disabled={actionLoading}
                      className="inline-flex items-center gap-1 px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded text-xs font-medium shadow-sm transition-colors"
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
