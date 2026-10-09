"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  AlertTriangle,
  Bell,
  Command,
  Database,
  ExternalLink,
  Layers,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

const ROUTE_TITLES: Record<string, { title: string; subtitle: string }> = {
  "/": { title: "Vue d'ensemble", subtitle: "Tableau de bord exécutif des marchés vivriers" },
  "/prices": { title: "Prix vivriers", subtitle: "Séries temporelles, dispersion et relevés" },
  "/map": { title: "Carte des marchés", subtitle: "Disparités territoriales & corridors" },
  "/trade": { title: "Commerce extérieur", subtitle: "Flux d'importation & prix parité import" },
  "/climate": { title: "Climat & Cultures", subtitle: "Anomalies agroclimatiques & stress hydrique" },
  "/alerts": { title: "Centre d'alertes", subtitle: "Détection des tensions et ruptures de marché" },
  "/bulletins": { title: "Bulletins hebdomadaires", subtitle: "Publications officielles chiffrées & certifiées" },
  "/copilot": { title: "Copilote analyste", subtitle: "Assistant de veille économique sans hallucination" },
  "/sources": { title: "Sources & DataOps", subtitle: "Qualité des données & monitoring des flux" },
  "/admin/review": { title: "File de revue", subtitle: "Arbitrage des anomalies & validation humaine" },
  "/system": { title: "Architecture Système", subtitle: "Infrastructure conteneurisée & cadences Dagster" },
};

export function TopHeader({
  onOpenCommand,
}: {
  onOpenCommand: () => void;
}) {
  const pathname = usePathname();
  const currentRoute = ROUTE_TITLES[pathname] || {
    title: "Ketrika Agri",
    subtitle: "Système de veille de marché vivrier à Madagascar",
  };

  return (
    <header className="h-16 px-6 border-b border-white/[0.07] bg-slate-950/70 backdrop-blur-xl flex items-center justify-between gap-4 sticky top-0 z-20">
      {/* Left: Route Title & Context */}
      <div className="flex items-center gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-bold tracking-tight text-white flex items-center gap-2">
              {currentRoute.title}
            </h1>
            <span className="hidden sm:inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Live UTC+3
            </span>
          </div>
          <p className="text-[11px] text-slate-400 hidden md:block">
            {currentRoute.subtitle}
          </p>
        </div>
      </div>

      {/* Center: Command Palette Trigger Button */}
      <div className="flex-1 max-w-md mx-2">
        <button
          onClick={onOpenCommand}
          className="w-full flex items-center justify-between px-3.5 py-1.5 rounded-xl bg-slate-900/80 border border-white/[0.08] hover:border-emerald-500/40 text-xs text-slate-400 hover:text-slate-200 transition-all shadow-inner group"
        >
          <span className="flex items-center gap-2">
            <Search className="w-3.5 h-3.5 text-slate-400 group-hover:text-emerald-400 transition-colors" />
            <span className="truncate">Rechercher une analyse, un produit, un lieu...</span>
          </span>
          <kbd className="hidden sm:inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-800 text-[10px] font-mono text-slate-400 border border-white/[0.08]">
            <Command className="w-2.5 h-2.5" /> K
          </kbd>
        </button>
      </div>

      {/* Right: Status Pills & User Profile */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Alerts Pill */}
        <Link
          href="/alerts"
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 text-amber-400 text-xs font-medium transition-colors"
          title="3 alertes actives"
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          <span className="hidden lg:inline text-[11px]">3 alertes</span>
        </Link>

        {/* Provenance badge */}
        <div
          className="hidden xl:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-[11px] font-medium"
          title="Toutes les données ont une provenance traçable"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>100% Provenance vérifiée</span>
        </div>

        {/* User Chip */}
        <div className="flex items-center gap-2 pl-2 border-l border-white/[0.08]">
          <div className="w-7 h-7 rounded-lg bg-emerald-600/30 border border-emerald-500/40 flex items-center justify-center text-xs font-bold text-emerald-300">
            A
          </div>
          <div className="hidden md:flex flex-col text-left">
            <span className="text-[11px] font-semibold text-slate-200 leading-tight">
              Analyste Marché
            </span>
            <span className="text-[9px] uppercase tracking-wider text-emerald-400 font-mono">
              Admin
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
