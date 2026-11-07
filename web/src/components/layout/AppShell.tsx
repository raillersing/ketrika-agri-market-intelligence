"use client";

import React, { Suspense, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { X } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { TopHeader } from "./TopHeader";
import { GlobalFilters } from "./GlobalFilters";
import { CommandPalette } from "./CommandPalette";
import { QuestOverlay } from "../tutorial/QuestOverlay";
import { BRAND } from "@/lib/brand";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublicPage = pathname === "/login" || pathname === "/about";
  const [isCommandOpen, setIsCommandOpen] = useState(false);
  const [isNavigationOpen, setIsNavigationOpen] = useState(false);
  const navigationRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setIsNavigationOpen(false); setIsCommandOpen(false); }, [pathname]);

  useEffect(() => {
    if (isPublicPage) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsNavigationOpen(false);
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setIsNavigationOpen(false);
        setIsCommandOpen(open => !open);
      }
    };
    const handleResize = () => { if (window.innerWidth >= 768) setIsNavigationOpen(false); };
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("resize", handleResize);
    return () => { window.removeEventListener("keydown", handleKeyDown); window.removeEventListener("resize", handleResize); };
  }, [isPublicPage]);

  useEffect(() => {
    if (!isNavigationOpen) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const target = navigationRef.current?.querySelector<HTMLElement>('[aria-current="page"]') || navigationRef.current?.querySelector<HTMLElement>("button");
    target?.focus();
    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const controls = Array.from(navigationRef.current?.querySelectorAll<HTMLElement>("a[href], button:not([disabled])") || []).filter(element => element.getClientRects().length > 0);
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", trapFocus);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", trapFocus);
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [isNavigationOpen]);

  if (isPublicPage) return <main className="min-h-screen bg-background">{children}</main>;

  return (
    <div className="relative flex min-h-screen bg-background text-foreground">
      <a href="#main-content" className="sr-only z-50 rounded-lg bg-primary-action px-4 py-3 font-medium text-primary-foreground focus:not-sr-only focus:fixed focus:left-4 focus:top-4">Aller au contenu</a>
      {isNavigationOpen && <button type="button" aria-label="Fermer le menu" tabIndex={-1} className="fixed inset-0 z-30 bg-black/60 md:hidden" onClick={() => setIsNavigationOpen(false)} />}
      <div ref={navigationRef} id="primary-navigation" role={isNavigationOpen ? "dialog" : undefined} aria-modal={isNavigationOpen ? true : undefined} aria-label={isNavigationOpen ? `Navigation ${BRAND.product}` : undefined}
        className={`${isNavigationOpen ? "block" : "hidden"} fixed inset-y-0 left-0 z-40 md:sticky md:top-0 md:block md:self-start`}
        onClick={event => { if ((event.target as Element).closest("a")) setIsNavigationOpen(false); }}>
        <button type="button" aria-label="Fermer la navigation" onClick={() => setIsNavigationOpen(false)} className="absolute left-full top-[16px] z-50 ml-[8px] flex h-[44px] w-[44px] items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:bg-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring md:hidden"><X aria-hidden="true" className="h-[20px] w-[20px]" /></button>
        <Sidebar />
      </div>
      <div className="relative flex min-w-0 flex-1 flex-col">
        <TopHeader onOpenCommand={() => { setIsNavigationOpen(false); setIsCommandOpen(true); }} navigationOpen={isNavigationOpen} onToggleNavigation={() => setIsNavigationOpen(open => !open)} />
        <Suspense fallback={<div className="h-12 border-b border-border bg-background/60" />}><GlobalFilters /></Suspense>
        <main id="main-content" tabIndex={-1} className="mx-auto w-full min-w-0 max-w-[1600px] flex-1 p-4 outline-none md:p-8">{children}</main>
      </div>
      <CommandPalette isOpen={isCommandOpen} onClose={() => setIsCommandOpen(false)} />
      <QuestOverlay />
    </div>
  );
}
