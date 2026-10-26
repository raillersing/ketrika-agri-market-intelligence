import { describe, expect, it } from "vitest";
import { NAVIGATION_PAGES, findNavigationPage, isNavigationPageActive, searchNavigationPages } from "./lib/navigation";

describe("navigation shared across menu, header and search", () => {
  it("identifies child routes without matching unrelated path prefixes", () => {
    expect(isNavigationPageActive("/sources/runs/123", "/sources")).toBe(true);
    expect(isNavigationPageActive("/sources-other", "/sources")).toBe(false);
    expect(isNavigationPageActive("/prices", "/")).toBe(false);
    expect(findNavigationPage("/admin/review/123")?.label).toBe("À vérifier");
    expect(findNavigationPage("/not-a-page")).toBeUndefined();
  });
  it("normalizes trailing slash and query without losing route boundaries", () => {
    expect(findNavigationPage("/prices/?product=RICE_WHITE_LOCAL")?.href).toBe("/prices");
    expect(findNavigationPage("/admin/reviewer")).toBeUndefined();
  });
  it("finds economy, accents, aliases and multi-word searches", () => {
    expect(searchNavigationPages("ECONOMIE").map(page => page.href)).toEqual(["/economy"]);
    expect(searchNavigationPages("copilote").map(page => page.href)).toEqual(["/copilot"]);
    expect(searchNavigationPages("Ketrikai").map(page => page.href)).toEqual(["/about"]);
    expect(searchNavigationPages("Irooa").map(page => page.href)).toEqual(["/about"]);
    expect(searchNavigationPages("vue d’ensemble").map(page => page.href)).toEqual(["/"]);
    expect(searchNavigationPages("qualite sources").map(page => page.href)).toEqual(["/sources"]);
    expect(searchNavigationPages("aucune-page-inconnue")).toEqual([]);
  });
  it("has unique reachable destinations and no fabricated filter parameters", () => {
    expect(new Set(NAVIGATION_PAGES.map(page => page.href)).size).toBe(NAVIGATION_PAGES.length);
    expect(NAVIGATION_PAGES.every(page => page.href.startsWith("/") && !page.href.includes("?"))).toBe(true);
    expect(searchNavigationPages("   ")).toEqual(NAVIGATION_PAGES);
  });
});
