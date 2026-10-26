"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { readThemePreference, resolveTheme, storeThemePreference, THEME_STORAGE_KEY, type Theme } from "@/lib/theme";

type ThemeContextValue = { theme: Theme; setTheme: (theme: Theme) => void; toggleTheme: () => void };
const ThemeContext = createContext<ThemeContextValue | null>(null);

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
}

function preference(): Theme | null {
  try { return readThemePreference(window.localStorage); } catch { return null; }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("light");
  const explicitChoice = useRef(false);
  const setTheme = useCallback((next: Theme) => {
    explicitChoice.current = true;
    applyTheme(next);
    setThemeState(next);
    try { storeThemePreference(window.localStorage, next); } catch { /* Session-only preference. */ }
  }, []);
  const toggleTheme = useCallback(() => {
    setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  }, [setTheme]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const sync = () => {
      const saved = preference();
      explicitChoice.current = saved !== null;
      const next = resolveTheme(saved, media.matches);
      applyTheme(next);
      setThemeState(next);
    };
    const systemChanged = () => {
      if (!explicitChoice.current) {
        const next = resolveTheme(null, media.matches);
        applyTheme(next);
        setThemeState(next);
      }
    };
    const storageChanged = (event: StorageEvent) => {
      if (event.key === THEME_STORAGE_KEY || event.key === null) sync();
    };
    sync();
    media.addEventListener("change", systemChanged);
    window.addEventListener("storage", storageChanged);
    return () => { media.removeEventListener("change", systemChanged); window.removeEventListener("storage", storageChanged); };
  }, []);

  return <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("ThemeProvider is required");
  return value;
}
