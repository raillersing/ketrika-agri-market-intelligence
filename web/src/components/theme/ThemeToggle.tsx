"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "./ThemeProvider";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const Icon = theme === "dark" ? Moon : Sun;
  return <button type="button" role="switch" aria-label="Mode sombre" aria-checked={theme === "dark"} onClick={toggleTheme}
    title={theme === "dark" ? "Passer en mode clair" : "Passer en mode sombre"}
    className="inline-flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring motion-reduce:transition-none"><Icon aria-hidden="true" className="h-[20px] w-[20px]" /></button>;
}
