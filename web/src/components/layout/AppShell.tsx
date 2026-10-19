"use client";

import React, { Suspense, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { TopHeader } from "./TopHeader";
import { GlobalFilters } from "./GlobalFilters";
import { CommandPalette } from "./CommandPalette";
import { X } from "lucide-react";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLoginPage = pathname === "/login";
  const [isCommandOpen, setIsCommandOpen] = useState(false);
  const [isNavigationOpen, setIsNavigationOpen] = useState(false);

  useEffect(() => { setIsNavigationOpen(false); }, [pathname]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsNavigationOpen(false);
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsCommandOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  if (isLoginPage) {
    return <main className="min-h-screen bg-background">{children}</main>;
  }

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100 selection:bg-emerald-500/20 selection:text-emerald-300 relative">
      {/* Background aurora glow effect */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute -top-40 left-1/3 w-[600px] h-[400px] bg-emerald-500/10 rounded-full blur-[140px]" />
        <div className="absolute top-1/2 -right-40 w-[500px] h-[500px] bg-sky-500/5 rounded-full blur-[160px]" />
      </div>

      {/* Sidebar navigation */}
      {isNavigationOpen && <button aria-label="Fermer le menu" className="fixed inset-0 bg-black/60 z-30 md:hidden" onClick={() => setIsNavigationOpen(false)} />}
      <div id="primary-navigation" className={`${isNavigationOpen ? "block" : "hidden"} fixed inset-y-0 left-0 z-40 md:block md:sticky md:top-0 md:self-start`}
        onClick={event => { if ((event.target as Element).closest("a")) setIsNavigationOpen(false); }}>
        <button aria-label="Fermer la navigation" onClick={() => setIsNavigationOpen(false)} className="absolute right-2 top-2 z-50 p-2 text-slate-200 bg-slate-900 rounded md:hidden"><X className="w-4 h-4" /></button>
        <Sidebar />
      </div>

      {/* Main content wrapper */}
      <div className="flex-1 flex flex-col min-w-0 relative z-10">
        <TopHeader onOpenCommand={() => setIsCommandOpen(true)} navigationOpen={isNavigationOpen} onToggleNavigation={() => setIsNavigationOpen(open => !open)} />
        
        <Suspense fallback={<div className="h-12 bg-slate-950/60 border-b border-white/[0.07]" />}>
          <GlobalFilters />
        </Suspense>

        <main className="flex-1 min-w-0 p-4 md:p-8 overflow-y-auto max-w-[1600px] w-full mx-auto">
          {children}
        </main>
      </div>

      {/* Global Command Palette */}
      <CommandPalette
        isOpen={isCommandOpen}
        onClose={() => setIsCommandOpen(false)}
      />
    </div>
  );
}
