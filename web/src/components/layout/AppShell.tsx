"use client";

import React, { Suspense, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { TopHeader } from "./TopHeader";
import { GlobalFilters } from "./GlobalFilters";
import { CommandPalette } from "./CommandPalette";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLoginPage = pathname === "/login";
  const [isCommandOpen, setIsCommandOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
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
    <div className="flex min-h-screen bg-slate-950 text-slate-100 selection:bg-emerald-500/20 selection:text-emerald-300 relative overflow-x-hidden">
      {/* Background aurora glow effect */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute -top-40 left-1/3 w-[600px] h-[400px] bg-emerald-500/10 rounded-full blur-[140px]" />
        <div className="absolute top-1/2 -right-40 w-[500px] h-[500px] bg-sky-500/5 rounded-full blur-[160px]" />
      </div>

      {/* Sidebar navigation */}
      <Sidebar />

      {/* Main content wrapper */}
      <div className="flex-1 flex flex-col min-w-0 relative z-10">
        <TopHeader onOpenCommand={() => setIsCommandOpen(true)} />
        
        <Suspense fallback={<div className="h-12 bg-slate-950/60 border-b border-white/[0.07]" />}>
          <GlobalFilters />
        </Suspense>

        <main className="flex-1 p-6 md:p-8 overflow-y-auto max-w-[1600px] w-full mx-auto">
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
