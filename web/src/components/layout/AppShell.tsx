"use client";

import React, { Suspense } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { GlobalFilters } from "./GlobalFilters";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLoginPage = pathname === "/login";

  if (isLoginPage) {
    return <main className="min-h-screen bg-background">{children}</main>;
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Suspense fallback={<div className="h-12 bg-card border-b border-border" />}>
          <GlobalFilters />
        </Suspense>
        <main className="flex-1 p-6 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
