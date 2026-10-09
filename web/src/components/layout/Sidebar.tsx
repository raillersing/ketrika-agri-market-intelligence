"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  ArrowLeftRight,
  CheckSquare,
  CloudSun,
  Cpu,
  FileText,
  LayoutDashboard,
  LogOut,
  Map,
  Server,
  Sparkles,
  TrendingUp,
} from "lucide-react";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  badgeColor?: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    title: "Marché & Cours",
    items: [
      { label: "Vue d'ensemble", href: "/", icon: LayoutDashboard },
      { label: "Prix vivriers", href: "/prices", icon: TrendingUp },
      { label: "Carte des marchés", href: "/map", icon: Map },
      { label: "Commerce extérieur", href: "/trade", icon: ArrowLeftRight },
    ],
  },
  {
    title: "Intelligence & Risques",
    items: [
      { label: "Climat & Cultures", href: "/climate", icon: CloudSun },
      { label: "Centre d'alertes", href: "/alerts", icon: AlertTriangle, badge: "3", badgeColor: "bg-amber-500/20 text-amber-400 border-amber-500/30" },
      { label: "Bulletins officiels", href: "/bulletins", icon: FileText },
      { label: "Copilote analyste", href: "/copilot", icon: Sparkles, badge: "IA", badgeColor: "bg-purple-500/20 text-purple-300 border-purple-500/30" },
    ],
  },
  {
    title: "Data Platform",
    items: [
      { label: "Sources & DataOps", href: "/sources", icon: Activity },
      { label: "File de revue", href: "/admin/review", icon: CheckSquare },
      { label: "Architecture Système", href: "/system", icon: Cpu },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  const handleLogout = async () => {
    try {
      await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" });
    } catch {}
    document.cookie = "session_token=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    document.cookie = "ketrika_token=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    window.location.href = "/login";
  };

  return (
    <aside className="w-64 bg-slate-950/95 text-slate-200 border-r border-white/[0.08] flex flex-col justify-between shrink-0 h-screen sticky top-0 select-none z-30">
      <div className="flex flex-col h-[calc(100vh-80px)] overflow-y-auto">
        {/* Brand Header */}
        <div className="p-5 border-b border-white/[0.08]">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="relative w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center font-bold text-white text-lg shadow-lg shadow-emerald-950/60 border border-emerald-400/30 group-hover:scale-105 transition-transform">
              <span className="drop-shadow-sm">K</span>
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-slate-950 animate-pulse" />
            </div>
            <div className="flex flex-col">
              <span className="text-base font-bold tracking-tight text-white group-hover:text-emerald-400 transition-colors flex items-center gap-1.5">
                Ketrika
                <span className="text-[10px] font-mono px-1 py-0.2 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Agri
                </span>
              </span>
              <span className="text-[10px] font-medium tracking-wider uppercase text-slate-400">
                Market Intelligence
              </span>
            </div>
          </Link>
        </div>

        {/* Navigation Sections */}
        <nav className="p-3 space-y-5 flex-1">
          {NAV_SECTIONS.map((section) => (
            <div key={section.title} className="space-y-1">
              <div className="px-3 text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold mb-1.5">
                {section.title}
              </div>
              <div className="space-y-0.5">
                {section.items.map((item) => {
                  const Icon = item.icon;
                  const isActive =
                    item.href === "/"
                      ? pathname === "/"
                      : pathname.startsWith(item.href);

                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`group relative flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                        isActive
                          ? "bg-emerald-500/15 text-emerald-300 font-semibold shadow-sm border border-emerald-500/25"
                          : "text-slate-400 hover:text-slate-100 hover:bg-white/[0.04] border border-transparent"
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <Icon
                          className={`w-4 h-4 transition-colors ${
                            isActive
                              ? "text-emerald-400"
                              : "text-slate-400 group-hover:text-slate-200"
                          }`}
                        />
                        <span>{item.label}</span>
                      </div>

                      {item.badge && (
                        <span
                          className={`text-[10px] font-mono px-1.5 py-0.2 rounded border ${
                            item.badgeColor || "bg-slate-800 text-slate-300 border-white/10"
                          }`}
                        >
                          {item.badge}
                        </span>
                      )}

                      {/* Active indicator bar */}
                      {isActive && (
                        <span className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r-full bg-emerald-500" />
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </div>

      {/* Infrastructure Heartbeat & User Footer */}
      <div className="p-3 border-t border-white/[0.08] bg-slate-950/80 space-y-2.5">
        {/* Micro System Ticker */}
        <div className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-slate-900/90 border border-white/[0.06] text-[10px] text-slate-400 font-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
            <span className="text-slate-300">Stack 6/6 OK</span>
          </div>
          <Link href="/system" className="hover:text-emerald-400 text-slate-400 transition-colors">
            :8090 / :5434
          </Link>
        </div>

        {/* User Card */}
        <div className="flex items-center justify-between px-2 py-1">
          <div className="flex flex-col min-w-0">
            <span className="text-xs font-semibold text-slate-200 truncate">
              Analyste Marché
            </span>
            <span className="text-[10px] text-slate-400 font-mono truncate">
              admin@ketrika.local
            </span>
          </div>
          <button
            onClick={handleLogout}
            title="Se déconnecter"
            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
