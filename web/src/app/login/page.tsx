"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Lock, Mail } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@ketrika.local");
  const [password, setPassword] = useState("admin-secret-password-123");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
      const res = await fetch(`${apiUrl}/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Identifiants invalides");
      }

      const data = await res.json();
      // Set session cookie in browser
      document.cookie = `ketrika_token=${data.access_token}; path=/; max-age=86400; SameSite=Lax`;
      router.push("/");
      router.refresh();
    } catch (err: any) {
      setError(err.message || "Erreur de connexion");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 px-4">
      <div className="max-w-md w-full bg-card border border-border rounded-xl shadow-lg p-8">
        <div className="text-center mb-8">
          <div className="inline-flex w-12 h-12 rounded-xl bg-emerald-600 text-white font-bold text-2xl items-center justify-center shadow-md mb-3">
            K
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Ketrika
          </h1>
          <p className="text-sm font-medium text-emerald-600 uppercase tracking-wider mt-1">
            Agri Market Intelligence
          </p>
          <p className="text-xs text-muted-foreground mt-2">
            Plateforme de veille de marché sur les produits PPN vivriers à Madagascar
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-md">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-foreground mb-1">
              Adresse email
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-muted-foreground absolute left-3 top-2.5" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="analyste@ketrika.mg"
                className="w-full text-sm bg-background border border-input rounded-md pl-9 pr-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-foreground mb-1">
              Mot de passe
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-muted-foreground absolute left-3 top-2.5" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full text-sm bg-background border border-input rounded-md pl-9 pr-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 bg-emerald-700 hover:bg-emerald-800 text-white font-medium text-sm rounded-md shadow transition-colors disabled:opacity-50 mt-6"
          >
            {loading ? "Connexion en cours..." : "Se connecter"}
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-border text-center text-xs text-muted-foreground">
          Identifiants démo : <span className="font-mono text-foreground">admin@ketrika.local</span> /{" "}
          <span className="font-mono text-foreground">admin-secret-password-123</span>
        </div>
      </div>
    </div>
  );
}
