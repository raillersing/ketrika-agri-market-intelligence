"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  ArrowLeftRight,
  ArrowRight,
  CheckSquare,
  CloudSun,
  Cpu,
  FileText,
  LayoutDashboard,
  LogOut,
  Map,
  Search,
  Sparkles,
  TrendingUp,
  X,
} from "lucide-react";

interface CommandItem {
  id: string;
  title: string;
  category: "Navigation" | "Produit" | "Région" | "Action";
  icon: React.ComponentType<{ className?: string }>;
  href?: string;
  action?: () => void;
  shortcut?: string;
}

export function CommandPalette({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  const items: CommandItem[] = [
    // Pages
    { id: "nav-overview", title: "Vue d'ensemble du marché", category: "Navigation", icon: LayoutDashboard, href: "/" },
    { id: "nav-prices", title: "Prix vivriers & Séries chronologiques", category: "Navigation", icon: TrendingUp, href: "/prices" },
    { id: "nav-map", title: "Carte spatiale des disparités de prix", category: "Navigation", icon: Map, href: "/map" },
    { id: "nav-trade", title: "Commerce extérieur & Importations", category: "Navigation", icon: ArrowLeftRight, href: "/trade" },
    { id: "nav-climate", title: "Agroclimatologie & Suivi des cultures", category: "Navigation", icon: CloudSun, href: "/climate" },
    { id: "nav-alerts", title: "Centre d'alertes & Tensions de marché", category: "Navigation", icon: AlertTriangle, href: "/alerts" },
    { id: "nav-bulletins", title: "Bulletins hebdomadaires PPN officiels", category: "Navigation", icon: FileText, href: "/bulletins" },
    { id: "nav-copilot", title: "Copilote analyste IA vérifié", category: "Navigation", icon: Sparkles, href: "/copilot" },
    { id: "nav-sources", title: "Sources de données & Cockpit DataOps", category: "Navigation", icon: Activity, href: "/sources" },
    { id: "nav-review", title: "File de revue des anomalies", category: "Navigation", icon: CheckSquare, href: "/admin/review" },
    { id: "nav-system", title: "Architecture & Documentation Système", category: "Navigation", icon: Cpu, href: "/system" },

    // Products filters
    { id: "prod-rice-milled", title: "Filtrer: Riz blanc local (makalioka)", category: "Produit", icon: TrendingUp, href: "/prices?product=rice_milled" },
    { id: "prod-rice-paddy", title: "Filtrer: Paddy (riz brut)", category: "Produit", icon: TrendingUp, href: "/prices?product=rice_paddy" },
    { id: "prod-rice-imp", title: "Filtrer: Riz importé (stock/parfumé)", category: "Produit", icon: TrendingUp, href: "/prices?product=rice_imported" },
    { id: "prod-maize", title: "Filtrer: Maïs grain", category: "Produit", icon: TrendingUp, href: "/prices?product=maize_grain" },
    { id: "prod-cassava", title: "Filtrer: Manioc frais & cossettes", category: "Produit", icon: TrendingUp, href: "/prices?product=cassava_fresh" },
    { id: "prod-oil", title: "Filtrer: Huile végétale alimentaire", category: "Produit", icon: TrendingUp, href: "/prices?product=oil_edible" },
    { id: "prod-sugar", title: "Filtrer: Sucre blanc raffiné", category: "Produit", icon: TrendingUp, href: "/prices?product=sugar_refined" },

    // Regions filters
    { id: "reg-analamanga", title: "Région: Analamanga (Antananarivo)", category: "Région", icon: Map, href: "/map?region=MG11" },
    { id: "reg-vakinankaratne", title: "Région: Vakinankaratne (Antsirabe)", category: "Région", icon: Map, href: "/map?region=MG12" },
    { id: "reg-atsimo", title: "Région: Atsimo-Andrefana (Toliara)", category: "Région", icon: Map, href: "/map?region=MG51" },
    { id: "reg-alaotra", title: "Région: Alaotra-Mangoro (Grenier à riz)", category: "Région", icon: Map, href: "/map?region=MG33" },

    // Actions
    {
      id: "act-logout",
      title: "Se déconnecter de la session",
      category: "Action",
      icon: LogOut,
      action: async () => {
        try {
          await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" });
        } catch {}
        document.cookie = "session_token=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT";
        document.cookie = "ketrika_token=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT";
        window.location.href = "/login";
      },
    },
  ];

  const filteredItems = items.filter((item) =>
    item.title.toLowerCase().includes(query.toLowerCase()) ||
    item.category.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleSelect = React.useCallback(
    (item: CommandItem) => {
      onClose();
      if (item.action) {
        item.action();
      } else if (item.href) {
        router.push(item.href);
      }
    },
    [onClose, router]
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % (filteredItems.length || 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + filteredItems.length) % (filteredItems.length || 1));
      } else if (e.key === "Enter" && filteredItems[selectedIndex]) {
        e.preventDefault();
        handleSelect(filteredItems[selectedIndex]);
      } else if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, filteredItems, selectedIndex, handleSelect, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
      <div
        className="w-full max-w-xl bg-slate-900 border border-emerald-500/30 rounded-2xl shadow-2xl shadow-emerald-950/50 overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-white/[0.08] bg-slate-900/90">
          <Search className="w-5 h-5 text-emerald-400 shrink-0" />
          <input
            autoFocus
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Rechercher une page, un produit vivrier, une région..."
            className="flex-1 bg-transparent text-sm text-white placeholder-slate-400 outline-none"
          />
          <button
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results list */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filteredItems.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-400">
              Aucun résultat pour « {query} »
            </div>
          ) : (
            filteredItems.map((item, idx) => {
              const Icon = item.icon;
              const isSelected = idx === selectedIndex;

              return (
                <button
                  key={item.id}
                  onClick={() => handleSelect(item)}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left text-xs font-medium transition-all ${
                    isSelected
                      ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 shadow-sm"
                      : "text-slate-300 hover:bg-white/[0.04] border border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                        isSelected
                          ? "bg-emerald-500/20 text-emerald-300"
                          : "bg-slate-800 text-slate-400"
                      }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                    </div>
                    <span>{item.title}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-400 border border-white/[0.05]">
                      {item.category}
                    </span>
                    {isSelected && <ArrowRight className="w-3.5 h-3.5 text-emerald-400" />}
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Command footer */}
        <div className="px-4 py-2 border-t border-white/[0.06] bg-slate-950/60 flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center gap-3">
            <span>Navigation: <kbd className="px-1 py-0.5 rounded bg-slate-800 text-slate-300 border border-white/10 font-mono text-[10px]">↑</kbd> <kbd className="px-1 py-0.5 rounded bg-slate-800 text-slate-300 border border-white/10 font-mono text-[10px]">↓</kbd></span>
            <span>Sélectionner: <kbd className="px-1 py-0.5 rounded bg-slate-800 text-slate-300 border border-white/10 font-mono text-[10px]">↵ Entrée</kbd></span>
          </div>
          <div>
            Fermer: <kbd className="px-1 py-0.5 rounded bg-slate-800 text-slate-300 border border-white/10 font-mono text-[10px]">Échap</kbd>
          </div>
        </div>
      </div>
    </div>
  );
}
