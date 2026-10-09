"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, CheckCircle2, Lock, Mail, ShieldCheck, Sparkles } from "lucide-react";

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
      const apiUrl = "/api";
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
      if (typeof data.token !== "string" || !data.token) throw new Error("Réponse de connexion invalide");
      
      // Compatibility: Set cookie if not httpOnly in some dev environments
      document.cookie = `session_token=${data.token}; path=/; max-age=86400; SameSite=Lax`;
      document.cookie = `ketrika_token=${data.token}; path=/; max-age=86400; SameSite=Lax`;

      router.push("/");
      router.refresh();
    } catch (err: any) {
      setError(err.message || "Erreur de connexion");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4 relative overflow-hidden selection:bg-emerald-500/20 selection:text-emerald-300">
      {/* Ambient background glows */}
      <div className="absolute -top-32 left-1/4 w-[500px] h-[500px] bg-emerald-500/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute -bottom-32 right-1/4 w-[500px] h-[500px] bg-sky-500/10 rounded-full blur-[140px] pointer-events-none" />

      <div className="max-w-md w-full glass-card p-8 sm:p-10 rounded-3xl border border-white/[0.1] shadow-2xl relative z-10">
        {/* Brand Logo & Title */}
        <div className="text-center mb-8">
          <div className="inline-flex relative mb-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-500 to-emerald-700 text-white font-bold text-2xl flex items-center justify-center shadow-xl shadow-emerald-950/60 border border-emerald-400/30">
              K
            </div>
            <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-emerald-400 border-2 border-slate-950 animate-pulse" />
          </div>

          <h1 className="text-2xl font-extrabold tracking-tight text-white">
            Ketrika
          </h1>
          <p className="text-xs font-mono font-medium text-emerald-400 tracking-wider uppercase mt-1">
            Agri Market Intelligence • Madagascar
          </p>
          <p className="text-xs text-slate-400 mt-2 leading-relaxed">
            Plateforme souveraine de veille économique sur les produits de première nécessité (PPN vivriers).
          </p>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-5 p-3.5 bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs rounded-xl flex items-center gap-2">
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-300 mb-1.5">
              Identifiant / Email
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="analyste@ketrika.mg"
                className="w-full text-xs bg-slate-900 border border-white/[0.1] rounded-xl pl-10 pr-3.5 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500 shadow-inner"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-mono uppercase tracking-wider text-slate-300 mb-1.5">
              Mot de passe
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full text-xs bg-slate-900 border border-white/[0.1] rounded-xl pl-10 pr-3.5 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500 shadow-inner"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-3 px-4 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold rounded-xl shadow-lg shadow-emerald-950/60 transition-all hover:scale-102 flex items-center justify-center gap-2 cursor-pointer"
          >
            {loading ? (
              <span>Authentification en cours...</span>
            ) : (
              <>
                <span>Accéder à l&apos;espace analyste</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Demo credentials helper pill */}
        <div className="mt-8 pt-5 border-t border-white/[0.08] text-center text-[11px] text-slate-400 font-mono">
          <span>Identifiants démonstration : </span>
          <span className="text-emerald-400 font-semibold">admin@ketrika.local</span>
        </div>
      </div>
    </div>
  );
}
