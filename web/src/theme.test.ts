import { runInNewContext } from "node:vm";
import { describe, expect, it } from "vitest";
import { CHART_PALETTES, parseTheme, readThemePreference, resolveTheme, storeThemePreference, THEME_INIT_SCRIPT, THEME_STORAGE_KEY } from "./lib/theme";

function bootstrap(saved: string | null, systemDark: boolean, blocked = false) {
  const root = { dataset: {} as Record<string, string>, style: { colorScheme: "" }, classList: { toggle: (_name: string, dark: boolean) => { root.dataset.darkClass = String(dark); } } };
  runInNewContext(THEME_INIT_SCRIPT, { document: { documentElement: root }, localStorage: { getItem: () => { if (blocked) throw new Error("storage denied"); return saved; } }, matchMedia: () => ({ matches: systemDark }) });
  return root;
}

describe("persistent light and dark themes", () => {
  it("uses explicit choices before system preferences and rejects unknown values", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
    expect(resolveTheme(null, true)).toBe("dark");
    expect(resolveTheme("invalid", false)).toBe("light");
    expect(parseTheme("<script>arbitrary</script>")).toBeNull();
  });
  it("continues when browser storage is blocked", () => {
    expect(readThemePreference({ getItem: () => { throw new Error("denied"); } })).toBeNull();
    expect(storeThemePreference({ setItem: () => { throw new Error("denied"); } }, "dark")).toBe(false);
    expect(bootstrap(null, true, true).dataset.theme).toBe("dark");
  });
  it("writes only the theme preference and reads valid saved values", () => {
    const values = new Map<string, string>();
    expect(storeThemePreference({ setItem: (key, value) => { values.set(key, value); } }, "dark")).toBe(true);
    expect([...values.entries()]).toEqual([[THEME_STORAGE_KEY, "dark"]]);
    expect(readThemePreference({ getItem: key => values.get(key) || null })).toBe("dark");
  });
  it("initializes class, data attribute and native controls before hydration", () => {
    for (const [saved, system, expected] of [["dark", false, "dark"], ["light", true, "light"], [null, true, "dark"], ["invalid", false, "light"]] as const) {
      const root = bootstrap(saved, system);
      expect(root.dataset.theme).toBe(expected);
      expect(root.dataset.darkClass).toBe(String(expected === "dark"));
      expect(root.style.colorScheme).toBe(expected);
    }
  });
  it("uses the reference palette and keeps forecast and imputation colors distinct", () => {
    expect(CHART_PALETTES.light.text).toBe("#111111");
    expect(CHART_PALETTES.light.primary).toBe("#1e7a34");
    expect(CHART_PALETTES.dark.tooltip).toBe("#1e293b");
    expect(CHART_PALETTES.light.forecast).not.toBe(CHART_PALETTES.light.imputed);
  });
});
