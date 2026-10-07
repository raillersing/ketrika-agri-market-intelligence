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
  FileText,
  LayoutDashboard,
  LogOut,
  Map,
  Sparkles,
  TrendingUp,
} from "lucide-react";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  role?: "client" | "admin";
}

const NAV_ITEMS: NavItem[] = [
  { label: "Vue d'ensemble", href: "/", icon: LayoutDashboard },
  { label: "Prix vivriers", href: "/prices", icon: TrendingUp },
  { label: "Carte des marchés", href: "/map", icon: Map },
  { label: "Commerce extérieur", href: "/trade", icon: ArrowLeftRight },
  { label: "Climat & Cultures", href: "/climate", icon: CloudSun },
  { label: "Alertes", href: "/alerts", icon: AlertTriangle },
  { label: "Bulletins", href: "/bulletins", icon: FileText },
  { label: "Copilote analyste", href: "/copilot", icon: Sparkles },
  { label: "Sources & DataOps", href: "/sources", icon: Activity, role: "admin" },
  { label: "File de revue", href: "/admin/review", icon: CheckSquare, role: "admin" },
];

export function Sidebar() {
  const pathname = usePathname();

  const handleLogout = async () => {
    try {
      // Clear cookie and redirect to login
      document.cookie = "ketrika_token=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT";
      window.location.href = "/login";
    } catch {
      window.location.href = "/login";
    }
  };

  return (
    <aside className="w-64 bg-sidebar text-sidebar-foreground border-r border-sidebar-border flex flex-col justify-between shrink-0 h-screen sticky top-0 select-none">
      <div>
        {/* Brand header */}
        <div className="p-6 border-b border-sidebar-border">
          <Link href="/" className="flex flex-col group">
            <div className="flex items-center gap-2">
              <span className="w-7 h-7 rounded-md bg-emerald-600 flex items-center justify-center font-bold text-white text-base shadow-sm">
                K
              </span>
              <span className="text-xl font-bold tracking-tight text-white group-hover:text-emerald-400 transition-colors">
                Ketrika
              </span>
            </div>
            <span className="text-[11px] font-medium tracking-wider uppercase text-emerald-500/90 mt-1 pl-9">
              Agri Market Intelligence
            </span>
          </Link>
        </div>

        {/* Navigation links */}
        <nav className="p-3 space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-sidebar-accent text-emerald-400 font-semibold"
                    : "text-slate-300 hover:bg-sidebar-accent/60 hover:text-white"
                }`}
              >
                <Icon
                  className={`w-4 h-4 ${
                    isActive ? "text-emerald-400" : "text-slate-400"
                  }`}
                />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* User footer & logout */}
      <div className="p-4 border-t border-sidebar-border">
        <div className="flex items-center justify-between">
          <div className="flex flex-col min-w-0">
            <span className="text-xs font-semibold text-slate-200 truncate">
              Analyste Marché
            </span>
            <span className="text-[11px] text-slate-400 truncate">
              admin@ketrika.local
            </span>
          </div>
          <button
            onClick={handleLogout}
            title="Se déconnecter"
            className="p-1.5 rounded text-slate-400 hover:text-rose-400 hover:bg-sidebar-accent transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
