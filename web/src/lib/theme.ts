export type Theme = "light" | "dark";
export const THEME_STORAGE_KEY = "irooa.theme";

export function parseTheme(value: unknown): Theme | null {
  return value === "light" || value === "dark" ? value : null;
}

export function resolveTheme(preference: unknown, systemDark: boolean): Theme {
  return parseTheme(preference) || (systemDark ? "dark" : "light");
}

export function readThemePreference(storage: Pick<Storage, "getItem">): Theme | null {
  try { return parseTheme(storage.getItem(THEME_STORAGE_KEY)); } catch { return null; }
}

export function storeThemePreference(storage: Pick<Storage, "setItem">, theme: Theme): boolean {
  try { storage.setItem(THEME_STORAGE_KEY, theme); return true; } catch { return false; }
}

/** Fixed bootstrap: stored values are validated, never interpreted as code. */
export const THEME_INIT_SCRIPT = `(function(){var p=null;try{p=localStorage.getItem('irooa.theme')}catch(e){}var d=p==='dark'||(p!=='light'&&typeof matchMedia==='function'&&matchMedia('(prefers-color-scheme: dark)').matches);var r=document.documentElement;r.classList.toggle('dark',d);r.dataset.theme=d?'dark':'light';r.style.colorScheme=d?'dark':'light'})()`;

export const CHART_PALETTES = {
  light: { text: "#111111", muted: "#5f6673", border: "#e5e7eb", tooltip: "#ffffff", primary: "#1e7a34", band: "rgba(30,122,52,0.10)", area: "rgba(30,122,52,0.18)", forecast: "#ea580c", imputed: "#1d4ed8", warning: "#92400e" },
  dark: { text: "#e2e8f0", muted: "#94a3b8", border: "#334155", tooltip: "#1e293b", primary: "#34d399", band: "rgba(5,150,105,0.10)", area: "rgba(5,150,105,0.20)", forecast: "#fb923c", imputed: "#7dd3fc", warning: "#fbbf24" },
} as const;
