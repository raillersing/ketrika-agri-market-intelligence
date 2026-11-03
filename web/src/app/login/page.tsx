"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, KeyRound } from "lucide-react";
import { BRAND } from "@/lib/brand";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const from = searchParams.get("from") || "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/v1/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Identifiants invalides");
      }
      const data = await response.json();
      if (typeof data.token !== "string" || !data.token) throw new Error("Réponse de connexion invalide");
      window.location.href = from;
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Erreur de connexion");
    } finally {
      setLoading(false);
    }
  };

  const handleFillDemo = () => {
    setEmail("admin@ketrika.mg");
    setPassword("AdminKetrika2026!");
  };

  return (
    <div className="flex min-h-dvh flex-col bg-background px-5 text-foreground">
      <header className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-4 py-8"><Link href="/about" prefetch={false} className="inline-block min-h-11 rounded text-xl font-semibold tracking-tight focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring">{BRAND.product}<span className="ml-3 text-xs font-normal text-muted-foreground">{BRAND.descriptor}</span></Link><ThemeToggle /></header>
      <section aria-labelledby="login-title" className="mx-auto my-auto w-full max-w-sm py-12">
        <p className="mb-3 text-sm text-muted-foreground">{BRAND.name}</p>
        <h1 id="login-title" className="text-3xl font-semibold tracking-tight">Se connecter</h1>
        <p className="mb-8 mt-3 text-sm leading-6 text-muted-foreground">Accédez à votre espace de veille des marchés vivriers.</p>
        {error && <p role="alert" id="login-error" className="mb-5 rounded-lg border border-rose-400/20 bg-rose-400/5 px-4 py-3 text-sm leading-6 text-rose-700 dark:text-rose-300">{error}</p>}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div><label htmlFor="login-email" className="mb-2 block text-sm text-foreground">Adresse e-mail</label><input id="login-email" name="email" type="email" autoComplete="username" required value={email} onChange={event => setEmail(event.target.value)} aria-describedby={error ? "login-error" : undefined} className="min-h-12 w-full rounded-lg border border-border bg-foreground/[0.03] px-3 text-base text-foreground outline-none transition-colors focus:border-border focus:ring-1 focus:ring-ring" /></div>
          <div><label htmlFor="login-password" className="mb-2 block text-sm text-foreground">Mot de passe</label><input id="login-password" name="password" type="password" autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)} aria-describedby={error ? "login-error" : undefined} className="min-h-12 w-full rounded-lg border border-border bg-foreground/[0.03] px-3 text-base text-foreground outline-none transition-colors focus:border-border focus:ring-1 focus:ring-ring" /></div>
          <button type="submit" disabled={loading} aria-busy={loading} className="flex min-h-12 w-full items-center justify-between gap-3 rounded-lg bg-primary-action px-4 py-3 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary-hover disabled:cursor-wait disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"><span>{loading ? "Connexion en cours…" : "Se connecter"}</span><ArrowRight aria-hidden="true" className="h-4 w-4" /></button>
        </form>

        <div className="mt-6 p-4 rounded-xl border border-primary/20 bg-primary/5 text-xs space-y-2">
          <div className="font-semibold text-primary-readable flex items-center gap-1.5">
            <KeyRound className="w-3.5 h-3.5" />
            Accès local configuré :
          </div>
          <div className="text-muted-foreground font-mono text-[11px]">
            admin@ketrika.mg / AdminKetrika2026!
          </div>
          <button
            type="button"
            onClick={handleFillDemo}
            className="mt-1 inline-flex items-center text-xs text-primary-readable underline font-medium hover:opacity-80"
          >
            Remplir automatiquement les champs
          </button>
        </div>

        <p className="mt-6 text-xs leading-6 text-muted-foreground">Accès réservé aux comptes configurés pour cet environnement.</p>
      </section>
      <footer className="mx-auto flex w-full max-w-5xl flex-wrap justify-between gap-4 border-t border-border py-6 text-xs text-muted-foreground"><span>Un produit {BRAND.company}</span><Link href="/about" prefetch={false} className="inline-flex min-h-11 items-center rounded py-2 text-muted-foreground hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">À propos d’{BRAND.product} et de {BRAND.company}</Link></footer>
    </div>
  );
}

export default function LoginPage() {
  return (
    <React.Suspense fallback={<div className="min-h-dvh flex items-center justify-center">Chargement...</div>}>
      <LoginContent />
    </React.Suspense>
  );
}
