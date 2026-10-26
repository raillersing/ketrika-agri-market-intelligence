"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { ChevronRight, Menu, Search } from "lucide-react";
import { findNavigationPage } from "@/lib/navigation";
import { BRAND } from "@/lib/brand";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

export function TopHeader({ onOpenCommand, onToggleNavigation, navigationOpen }: {
  onOpenCommand: () => void;
  onToggleNavigation: () => void;
  navigationOpen: boolean;
}) {
  const page = findNavigationPage(usePathname());
  return (
    <header className="sticky top-0 z-20 flex min-h-16 items-center justify-between gap-[12px] border-b border-border bg-header px-[12px] py-2 md:px-8">
      <div className="flex min-w-0 items-center gap-3">
        <button type="button" aria-label="Ouvrir la navigation" aria-expanded={navigationOpen} aria-controls="primary-navigation" onClick={onToggleNavigation}
          className="flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-foreground/[0.05] focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring md:hidden"><Menu aria-hidden="true" className="h-[20px] w-[20px]" /></button>
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2 text-sm">
            {page && page.href !== "/" && <><span className="hidden shrink-0 text-muted-foreground lg:inline">{page.group}</span><ChevronRight aria-hidden="true" className="hidden h-3 w-3 shrink-0 text-muted-foreground lg:block" /></>}
            <p title={page?.label} className="truncate font-semibold text-foreground">{page?.label || BRAND.product}</p>
          </div>
          <p className="mt-0.5 hidden text-xs text-muted-foreground md:block">{page?.description || "Veille des marchés vivriers"}</p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-[8px]"><ThemeToggle />
        <button type="button" onClick={onOpenCommand} aria-label="Rechercher une page" aria-haspopup="dialog" aria-keyshortcuts="Control+k Meta+k"
          className="flex h-[44px] w-[44px] shrink-0 items-center justify-center gap-3 rounded-lg border border-border text-sm text-muted-foreground hover:border-border hover:bg-foreground/[0.03] hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring md:w-auto md:px-3">
          <Search aria-hidden="true" className="h-[16px] w-[16px]" /><span className="hidden md:inline">Aller à une page…</span><kbd aria-hidden="true" className="ml-3 hidden rounded border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground lg:inline">Ctrl K</kbd>
        </button>
      </div>
    </header>
  );
}
