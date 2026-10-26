"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, LogOut } from "lucide-react";
import { NAVIGATION_PAGES, PRIMARY_NAVIGATION_GROUPS, findNavigationPage, isNavigationPageActive, type NavigationPage } from "@/lib/navigation";
import { NAVIGATION_ICONS } from "./navigation-icons";
import { BRAND } from "@/lib/brand";

export function Sidebar() {
  const pathname = usePathname();
  const isManagementPage = findNavigationPage(pathname)?.group === "Gestion des données";
  const [managementOpen, setManagementOpen] = useState(isManagementPage);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState("");

  useEffect(() => {
    if (isManagementPage) setManagementOpen(true);
  }, [pathname, isManagementPage]);

  const handleLogout = async () => {
    setLoggingOut(true);
    setLogoutError("");
    try {
      const response = await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" });
      if (!response.ok) throw new Error("Déconnexion refusée");
      window.location.href = "/login";
    } catch {
      setLogoutError("Déconnexion impossible. Votre session reste ouverte.");
      setLoggingOut(false);
    }
  };

  const renderPage = (page: NavigationPage) => {
    const Icon = NAVIGATION_ICONS[page.icon];
    const active = isNavigationPageActive(pathname, page.href);
    return (
      <li key={page.href}>
        <Link href={page.href} prefetch={false} aria-current={active ? "page" : undefined}
          className={`flex min-h-[44px] items-center gap-[12px] rounded-lg border-l-2 px-[12px] py-2 text-sm leading-5 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring motion-reduce:transition-none ${active ? "border-primary bg-foreground/[0.07] font-semibold text-foreground" : "border-transparent text-muted-foreground hover:bg-foreground/[0.04] hover:text-foreground"}`}>
          <Icon aria-hidden="true" strokeWidth={1.7} className={`h-[18px] w-[18px] shrink-0 ${active ? "text-primary-readable" : "text-muted-foreground"}`} />
          <span className="min-w-0 break-words">{page.label}</span>
        </Link>
      </li>
    );
  };

  return (
    <aside aria-labelledby="navigation-title" className="sticky top-0 flex h-dvh w-[256px] max-w-[calc(100vw-64px)] shrink-0 flex-col border-r border-border bg-sidebar text-foreground">
      <div className="px-[20px] pb-5 pt-6">
        <Link href="/" prefetch={false} aria-label={`${BRAND.product}, vue d'ensemble`} className="inline-flex max-w-full items-center gap-[12px] rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring">
          <span aria-hidden="true" className="flex h-[36px] w-[36px] shrink-0 items-center justify-center rounded-lg border border-border bg-foreground/[0.05] text-lg font-semibold text-foreground">I</span>
          <span className="min-w-0"><span className="block text-lg font-semibold tracking-tight text-foreground">{BRAND.product}</span><span className="block text-xs text-muted-foreground">{BRAND.descriptor}</span></span>
        </Link>
      </div>
      <p id="navigation-title" className="sr-only">Navigation {BRAND.product}</p>
      <nav aria-label="Navigation principale" className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-[12px] pb-4">
        <ul className="mb-6 space-y-1">{renderPage(NAVIGATION_PAGES[0])}</ul>
        {PRIMARY_NAVIGATION_GROUPS.map(group => (
          <section key={group} aria-label={group} className="mb-5">
            <h2 className="mb-1 px-3 text-xs font-medium text-muted-foreground">{group}</h2>
            <ul className="space-y-1">{NAVIGATION_PAGES.filter(page => page.group === group).map(renderPage)}</ul>
          </section>
        ))}
        <div className="mt-2 border-t border-border pt-3">
          <button type="button" aria-expanded={managementOpen} aria-controls="management-navigation" onClick={() => setManagementOpen(open => !open)}
            className="flex min-h-[44px] w-full items-center justify-between gap-2 rounded-lg px-[12px] py-2 text-left text-xs font-medium text-muted-foreground hover:bg-foreground/[0.04] hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
            Gestion des données<ChevronDown aria-hidden="true" className={`h-4 w-4 shrink-0 transition-transform motion-reduce:transition-none ${managementOpen ? "rotate-180" : ""}`} />
          </button>
          <ul id="management-navigation" hidden={!managementOpen} className="mt-1 space-y-1">{NAVIGATION_PAGES.filter(page => page.group === "Gestion des données").map(renderPage)}</ul>
        </div>
      </nav>
      <div className="border-t border-border p-[12px]">
        <nav aria-label="Informations"><ul>{NAVIGATION_PAGES.filter(page => page.group === "Informations").map(renderPage)}</ul></nav>
        {logoutError && <p role="alert" className="mb-2 px-3 text-xs leading-5 text-rose-700 dark:text-rose-300">{logoutError}</p>}
        <button type="button" title="Se déconnecter" onClick={handleLogout} disabled={loggingOut} aria-busy={loggingOut}
          className="flex min-h-[44px] w-full items-center gap-[12px] rounded-lg px-[12px] py-2 text-left text-sm text-muted-foreground hover:bg-foreground/[0.04] hover:text-foreground disabled:cursor-wait disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
          <LogOut aria-hidden="true" strokeWidth={1.7} className="h-[18px] w-[18px] shrink-0 text-muted-foreground" /><span className="min-w-0 break-words">{loggingOut ? "Déconnexion…" : "Se déconnecter"}</span>
        </button>
      </div>
    </aside>
  );
}
